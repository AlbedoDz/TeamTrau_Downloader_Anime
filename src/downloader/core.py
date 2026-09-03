import os
import random
import re
import shutil
import subprocess
import sys
import time
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from downloader.extractor import get_extractor_for_url
from downloader.utils import (
    HttpClient,
    classify_spanish_variant,
    clean_filename,
    clean_folder_name,
    console,
    get_chrome_cookies_temp_file,
    get_safe_referer,
    vtt_to_srt,
)


class DNSError(Exception):
    """Exception raised when a DNS resolution/host unreachable error occurs."""

    pass


def get_local_tool_path(name: str) -> str | None:
    """Get path to a tool (yt-dlp or ffmpeg) in the local project directory if it exists."""
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if name == "yt-dlp":
        local_path = os.path.join(root_dir, "yt-dlp", "yt-dlp.exe")
        if os.path.exists(local_path):
            return local_path
    elif name == "ffmpeg":
        local_path = os.path.join(root_dir, "ffmpeg", "ffmpeg.exe")
        if os.path.exists(local_path):
            return local_path
    return None


def get_local_ffmpeg_dir() -> str | None:
    """Get path to the local ffmpeg directory if it contains ffmpeg.exe."""
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ffmpeg_dir = os.path.join(root_dir, "ffmpeg")
    if os.path.exists(os.path.join(ffmpeg_dir, "ffmpeg.exe")):
        return ffmpeg_dir
    return None


def is_ffmpeg_installed() -> bool:
    """Check if ffmpeg is available in system PATH or locally."""
    if get_local_tool_path("ffmpeg"):
        return True
    return shutil.which("ffmpeg") is not None


def extract_hashes_from_url(url: str) -> tuple[str, str] | None:
    """Extract anime and episode hashes (32-character hex) from stream/subtitle URLs."""
    if not url:
        return None
    m = re.search(r"/anime/([a-fA-F0-9]{32})/([a-fA-F0-9]{32})/", url)
    if m:
        return m.group(1), m.group(2)
    return None


def resolve_sub_lang_tag(track_label: str, default_lang: str) -> str:
    """Resolve standard ISO/IETF subtitle language sub-tag for player auto-detection.

    Examples:
        - Spanish (Latin America) / Spanish (- Español (LA)) -> es-LA
        - Spanish (Spain) / Spanish (- Español (ES)) -> es-ES
        - Spanish (General) -> es
        - English -> en
        - Vietnamese -> vi
    """
    lbl = (track_label or "").lower()

    # Spanish check via unified classifier
    sp_var = classify_spanish_variant(lbl, default_lang)
    if sp_var:
        return sp_var

    # English check
    if any(kw in lbl for kw in ["english", "eng"]):
        return "en"

    # Vietnamese check
    if any(kw in lbl for kw in ["vietnamese", "tieng viet", "vi"]):
        return "vi"

    # Fallback mapping based on default_lang
    def_lower = default_lang.lower()
    if def_lower in ("es-la", "es-419", "latin america", "latam"):
        return "es-LA"
    if def_lower in ("es-es", "spain", "castellano", "esp"):
        return "es-ES"
    if def_lower in ("es", "spanish", "espanol", "español", "spa"):
        return "es"
    if def_lower in ("en", "english"):
        return "en"
    if def_lower in ("vi", "vietnamese"):
        return "vi"

    return def_lower


def get_target_lang_candidate_tags(target_lang: str) -> list[str]:
    """Get list of matching filename language tags for a given target language."""
    t_lower = target_lang.lower().strip()
    if t_lower in ("es-es", "esp", "spain", "castellano"):
        return ["es-ES"]
    if t_lower in (
        "es",
        "spa",
        "spanish",
        "espanol",
        "español",
        "es-la",
        "latam",
        "latin america",
    ):
        return ["es-LA", "es-419", "es"]
    if t_lower in ("en", "eng", "english"):
        return ["en", "en-US", "en-GB"]
    if t_lower in ("vi", "viet", "vietnamese"):
        return ["vi"]
    tag = resolve_sub_lang_tag("", target_lang)
    return [tag] if tag else []


def shorten_title_safe(title: str, max_len: int = 40) -> str:
    """Shorten a title safely using word boundaries and an MD5 suffix if it exceeds max_len."""
    if len(title) <= max_len:
        return title

    # Try to truncate at a word boundary
    truncated = title[:max_len].rsplit(" ", 1)[0].strip()
    if len(truncated) < max_len // 2:
        # Fallback to direct truncation if rsplit cut too much
        truncated = title[:max_len].strip()

    import hashlib

    h = hashlib.md5(title.encode("utf-8")).hexdigest()[:6]
    return f"{truncated} [{h}]"


def parse_episode_range(range_str: str, episodes_list: list[dict]) -> list[dict]:
    """Parse episode range strings (e.g. 'all', '1-5', '3,5,10-12', 'SP', 'OVA') and select matching items."""
    range_str = range_str.strip().lower()
    if range_str == "all" or not range_str:
        return episodes_list

    selected = []
    # Split by comma for multiple parts
    parts = range_str.split(",")

    for part in parts:
        part = part.strip().lower()
        if not part:
            continue

        if "-" in part and not part.startswith("ep-"):
            try:
                start_str, end_str = part.split("-", 1)
                start = int(start_str.strip())
                end = int(end_str.strip())
                for idx, ep in enumerate(episodes_list):
                    num_match = re.search(r"\d+", str(ep.get("num", "")))
                    val = int(num_match.group(0)) if num_match else (idx + 1)
                    if start <= val <= end and ep not in selected:
                        selected.append(ep)
                continue
            except ValueError:
                pass

        # Check direct tag matching for special episodes like 'sp', 'ova', etc.
        matched_by_tag = False
        for ep in episodes_list:
            ep_num = str(ep.get("num", "")).lower()
            ep_disp = str(ep.get("display_num", "")).lower()
            ep_slug = str(ep.get("slug", "")).lower()
            if part in [ep_num, ep_disp] or ep_slug.endswith(f"-ep-{part}"):
                if ep not in selected:
                    selected.append(ep)
                matched_by_tag = True

        if matched_by_tag:
            continue

        try:
            val = int(part)
            for idx, ep in enumerate(episodes_list):
                num_match = re.search(r"\d+", str(ep.get("num", "")))
                val_ep = int(num_match.group(0)) if num_match else (idx + 1)
                if val == val_ep and ep not in selected:
                    selected.append(ep)
        except ValueError:
            console.print(
                f"[warning]Skipping invalid episode part: {part}[/warning]", style="yellow"
            )

    # Sort selected episodes in the order they appear in the original list
    ep_slug_order = {ep["slug"]: idx for idx, ep in enumerate(episodes_list)}
    selected.sort(key=lambda ep: ep_slug_order.get(ep["slug"], 9999))

    return selected


class BatchDownloader:
    def __init__(
        self,
        output_dir: str = ".",
        delay_range: tuple = (3.0, 7.0),
        exclude_servers: list[str] | None = None,
        server_priority: list[str] | None = None,
        interactive: bool = False,
        only_server: str | None = None,
        proxy: str | None = None,
        use_browser_sniffer: bool = False,
        progress_callback=None,
        log_callback=None,
    ):
        self.output_dir = output_dir
        self.delay_range = delay_range
        self.exclude_servers = exclude_servers or []
        self.server_priority = server_priority or []
        self.interactive = interactive
        self.only_server = only_server
        self.proxy = proxy
        self.use_browser_sniffer = use_browser_sniffer
        self.progress_callback = progress_callback
        self.log_callback = log_callback

        # Load Chrome cookies for WAF/CDN bypass and determine browser type for impersonation
        cookies_info = get_chrome_cookies_temp_file()
        impersonate_target = "chrome120"
        self.cookies_path = None

        if cookies_info:
            self.cookies_path, browser_name = cookies_info
            if browser_name == "firefox":
                impersonate_target = "firefox"

        self.http = HttpClient(
            impersonate=impersonate_target,
            delay_range=delay_range,
            proxy=proxy,
        )
        if self.cookies_path:
            self.http.load_cookies_from_file(self.cookies_path)

    def emit_log(self, level: str, category: str, message: str) -> None:
        """Helper to emit logs to both console and GUI log_callback."""
        if self.log_callback:
            try:
                self.log_callback(level, category, message)
            except Exception:
                pass
        try:
            console.print(f"[{category.upper()}] {message}")
        except Exception:
            pass

    def cleanup(self):
        """Clean up temporary cookies files."""
        if self.cookies_path and os.path.exists(self.cookies_path):
            try:
                os.remove(self.cookies_path)
                console.print("[info]Cleaned up temporary cookies file.[/info]")
            except Exception as e:
                console.print(
                    f"[warning]Failed to clean up temporary cookies file: {e}[/warning]",
                    style="yellow",
                )
            self.cookies_path = None

    def download_file_chunked(self, url: str, dest_path: str, referer: str | None = None) -> bool:
        """Download a direct file using chunked HTTP requests with a progress bar."""
        headers = {
            "User-Agent": self.http.session.headers.get("User-Agent", "Mozilla/5.0"),
        }
        if referer:
            headers["Referer"] = referer

        try:
            # Perform stream request
            response = self.http.session.get(url, headers=headers, stream=True, timeout=30)
            if response.status_code != 200:
                console.print(
                    f"[error]Failed to download file (HTTP {response.status_code})[/error]",
                    style="red",
                )
                return False

            total_size = int(response.headers.get("content-length", 0))

            with Progress(
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("Downloading...", total=total_size)
                start_dl_time = time.time()
                downloaded_so_far = 0

                with open(dest_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded_so_far += len(chunk)
                            elapsed = time.time() - start_dl_time
                            spd = downloaded_so_far / elapsed if elapsed > 0 else 0.0
                            eta_sec = (
                                int((total_size - downloaded_so_far) / spd)
                                if total_size > 0 and spd > 0
                                else 0
                            )
                            if self.progress_callback:
                                try:
                                    self.progress_callback(1, 1, downloaded_so_far, spd, eta_sec)
                                except Exception:
                                    pass
                            progress.update(task, advance=len(chunk))
            return True
        except Exception as e:
            console.print(f"[error]Error during file download: {e}[/error]", style="red")
            if os.path.exists(dest_path):
                os.remove(dest_path)
            return False

    def download_hls_stream(self, m3u8_url: str, dest_path: str, referer: str) -> bool:
        """Download HLS (.m3u8) video playlist natively (stripping PNG headers if present) and remux using ffmpeg, falling back to yt-dlp/ffmpeg."""
        from urllib.parse import urljoin

        yt_dlp_path = get_local_tool_path("yt-dlp")
        ffmpeg_dir = get_local_ffmpeg_dir()
        ffmpeg_path = get_local_tool_path("ffmpeg") or "ffmpeg"
        ua = self.http.session.headers.get("User-Agent", "Mozilla/5.0")
        safe_referer = get_safe_referer(referer)

        dns_keywords = [
            "Could not resolve host",
            "curl: (6)",
            "Failed to resolve",
            "getaddrinfo failed",
            "Errno 11004",
        ]

        # Try native HLS downloader first to handle custom masquerading (like PNG headers)
        try:
            try:
                m3u8_res = self.http.get(m3u8_url, referer=safe_referer, retries=1)
                if m3u8_res.status_code == 403:
                    raise ValueError("HTTP 403 Forbidden")
                if m3u8_res.status_code != 200:
                    raise ValueError(f"HTTP {m3u8_res.status_code}")
            except Exception as e:
                if "403" in str(e):
                    raise
                # Fallback: try fetching with the full referer URL
                try:
                    m3u8_res = self.http.get(m3u8_url, referer=referer, retries=1)
                    if m3u8_res.status_code != 200:
                        raise ValueError(f"HTTP {m3u8_res.status_code}")
                except Exception as fe:
                    err_msg = str(fe)
                    if any(k in err_msg for k in dns_keywords):
                        raise DNSError(f"DNS error fetching manifest: {err_msg}") from fe
                    raise

            if m3u8_res.status_code == 200 and m3u8_res.text:
                text_clean = m3u8_res.text.strip()
                if not (
                    text_clean.startswith("#EXT")
                    or "#EXTINF" in text_clean
                    or "#EXT-X-STREAM-INF" in text_clean
                ):
                    raise ValueError("Response text is not a valid HLS m3u8 playlist")
                if "#EXT-X-KEY" in text_clean or "#EXT-X-SESSION-KEY" in text_clean:
                    raise ValueError("HLS stream is encrypted (AES-128)")
                lines = m3u8_res.text.split("\n")
                seg_urls = []
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        seg_urls.append(urljoin(m3u8_url, line))

                if seg_urls:
                    console.print(
                        f"[info]Downloading HLS stream natively ({len(seg_urls)} fragments)...[/info]"
                    )
                    temp_ts_path = dest_path + ".temp.ts"
                    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)

                    import tempfile
                    import threading
                    from concurrent.futures import ThreadPoolExecutor, as_completed

                    success = True
                    dns_failed_event = threading.Event()
                    png_header = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\xdacd\xf8\xcfP\x0f\x00\x03\x86\x01\x80Z4}k\x00\x00\x00\x00IEND\xae\x42\x60\x82"

                    with tempfile.TemporaryDirectory() as temp_dir:
                        parsed_ref = urlparse(safe_referer)
                        player_origin = (
                            f"{parsed_ref.scheme}://{parsed_ref.netloc}"
                            if parsed_ref.scheme and parsed_ref.netloc
                            else ""
                        )

                        def download_segment(idx, seg_url):
                            if dns_failed_event.is_set():
                                return idx, False, ("Cancelled due to DNS error", True)

                            segment_headers = {"Referer": safe_referer, "User-Agent": ua}
                            if player_origin:
                                segment_headers["Origin"] = player_origin

                            max_seg_retries = 5
                            last_seg_err = None

                            for attempt in range(max_seg_retries):
                                if dns_failed_event.is_set():
                                    return idx, False, ("Cancelled due to DNS error", True)
                                try:
                                    if attempt == 0:
                                        time.sleep(random.uniform(0.10, 0.25))
                                    else:
                                        time.sleep(random.uniform(2.0, 4.5) * attempt)

                                    if dns_failed_event.is_set():
                                        return idx, False, ("Cancelled due to DNS error", True)

                                    res = self.http.get(
                                        seg_url,
                                        headers=segment_headers,
                                        retries=3,
                                        delay=2.0,
                                        rate_limit=False,
                                    )
                                    if res.status_code != 200 or not res.content:
                                        raise ValueError(f"HTTP {res.status_code}")

                                    segment_data = res.content
                                    if segment_data.startswith(png_header):
                                        segment_data = segment_data[len(png_header) :]
                                    part_path = os.path.join(temp_dir, f"part_{idx:05d}.ts")
                                    with open(part_path, "wb") as pf:
                                        pf.write(segment_data)
                                    return idx, True, part_path
                                except Exception as e:
                                    last_seg_err = e
                                    err_msg = str(e)
                                    is_dns = any(k in err_msg for k in dns_keywords)
                                    if is_dns:
                                        dns_failed_event.set()
                                        return idx, False, (err_msg, True)

                            return idx, False, (str(last_seg_err), False)

                        max_workers = 4
                        with ThreadPoolExecutor(max_workers=max_workers) as executor:
                            futures = {
                                executor.submit(download_segment, i, url): i
                                for i, url in enumerate(seg_urls)
                            }

                            with Progress(
                                TextColumn("[bold blue]{task.description}"),
                                BarColumn(),
                                DownloadColumn(),
                                TimeRemainingColumn(),
                                console=console,
                            ) as progress:
                                task = progress.add_task("Downloading HLS...", total=len(seg_urls))
                                start_time = time.time()
                                downloaded_bytes_total = 0
                                completed_count = 0

                                for future in as_completed(futures):
                                    idx, ok, info = future.result()
                                    if not ok:
                                        err_msg, is_dns = (
                                            info if isinstance(info, tuple) else (str(info), False)
                                        )
                                        console.print(
                                            f"\n[error]Failed to download fragment {idx + 1}/{len(seg_urls)}: {err_msg}[/error]",
                                            style="red",
                                        )
                                        success = False
                                        if is_dns:
                                            dns_failed_event.set()
                                        for f in futures:
                                            f.cancel()
                                        break

                                    completed_count += 1
                                    if isinstance(info, str) and os.path.exists(info):
                                        downloaded_bytes_total += os.path.getsize(info)

                                    elapsed = time.time() - start_time
                                    speed = downloaded_bytes_total / elapsed if elapsed > 0 else 0.0
                                    rem_segs = len(seg_urls) - completed_count
                                    eta = (
                                        int(
                                            rem_segs
                                            * (downloaded_bytes_total / completed_count)
                                            / speed
                                        )
                                        if completed_count > 0 and speed > 0
                                        else 0
                                    )

                                    if self.progress_callback:
                                        try:
                                            self.progress_callback(
                                                completed_count,
                                                len(seg_urls),
                                                downloaded_bytes_total,
                                                speed,
                                                eta,
                                            )
                                        except Exception:
                                            pass

                                    progress.update(task, advance=1)

                        if dns_failed_event.is_set():
                            raise DNSError("DNS resolution failed for HLS segment host")

                        if success:
                            console.print("[info]Assembling HLS fragments...[/info]")
                            with open(temp_ts_path, "wb") as ts_f:
                                for i in range(len(seg_urls)):
                                    part_path = os.path.join(temp_dir, f"part_{i:05d}.ts")
                                    if os.path.exists(part_path):
                                        with open(part_path, "rb") as pf:
                                            ts_f.write(pf.read())

                    if success:
                        remux_cmd = [
                            ffmpeg_path,
                            "-y",
                            "-i",
                            temp_ts_path,
                            "-c",
                            "copy",
                            "-bsf:a",
                            "aac_adtstoasc",
                            "-movflags",
                            "+faststart",
                            dest_path,
                        ]

                        remux_res = subprocess.run(
                            remux_cmd,
                            capture_output=True,
                            text=True,
                            encoding="utf-8",
                            errors="replace",
                            check=False,
                        )

                        if os.path.exists(temp_ts_path):
                            os.remove(temp_ts_path)

                        if remux_res.returncode == 0:
                            return True
                        else:
                            console.print(
                                f"[warning]ffmpeg remuxing failed (code {remux_res.returncode}): {remux_res.stderr}[/warning]",
                                style="yellow",
                            )
                            if os.path.exists(dest_path):
                                os.remove(dest_path)
                            raise ValueError(
                                f"ffmpeg remuxing failed with code {remux_res.returncode}"
                            )
                    else:
                        if os.path.exists(temp_ts_path):
                            os.remove(temp_ts_path)
                        raise ValueError("Native HLS download failed")
        except DNSError:
            raise
        except Exception as e:
            err_msg = str(e)
            if any(k in err_msg for k in dns_keywords):
                raise DNSError(f"DNS error in HLS stream: {err_msg}") from e
            if "403" in err_msg or "Forbidden" in err_msg:
                # WAF block: skip fallbacks and fail fast to try next server
                raise
            console.print(
                f"[warning]Native HLS downloader error or bypass: {e}. Trying fallback...[/warning]",
                style="yellow",
            )

        # 1. Try downloading with yt-dlp if available
        if yt_dlp_path:
            console.print("[info]Downloading video stream via yt-dlp (max 720p)...[/info]")
            parsed_ref = urlparse(safe_referer)
            segment_origin = (
                f"{parsed_ref.scheme}://{parsed_ref.netloc}"
                if parsed_ref.scheme and parsed_ref.netloc
                else ""
            )
            cmd = [
                yt_dlp_path,
                m3u8_url,
                "--add-header",
                f"Referer:{safe_referer}",
                "--add-header",
                f"User-Agent:{ua}",
            ]
            if segment_origin:
                cmd.extend(["--add-header", f"Origin:{segment_origin}"])
            cmd.extend(
                [
                    "--extractor-args",
                    "generic:impersonate",
                    "-f",
                    "best[height<=720]/best",
                    "-o",
                    dest_path,
                    "--no-playlist",
                    "--concurrent-fragments",
                    "2",
                    "--fragment-retries",
                    "15",
                    "--retry-sleep",
                    "fragment:exp=2:20",
                ]
            )
            if ffmpeg_dir:
                cmd.extend(["--ffmpeg-location", ffmpeg_dir])
            if self.cookies_path:
                cmd.extend(["--cookies", self.cookies_path])
            if self.proxy:
                cmd.extend(["--proxy", self.proxy])

            try:
                # Run yt-dlp and allow it to display its progress bar directly to console
                process = subprocess.run(cmd, check=False)
                if process.returncode == 0:
                    return True

                # Check for Windows file lock renaming issues and attempt manual recovery
                temp_mp4 = dest_path + ".temp.mp4"
                temp_part = dest_path + ".part"
                recovered = False
                for temp_file in [temp_mp4, temp_part]:
                    if os.path.exists(temp_file) and os.path.getsize(temp_file) > 5 * 1024 * 1024:
                        console.print(
                            f"[warning]yt-dlp failed with return code {process.returncode} but left a valid temp file: {os.path.basename(temp_file)}. Attempting manual recovery...[/warning]",
                            style="yellow",
                        )
                        time.sleep(2.0)  # Wait for locks to release
                        try:
                            if os.path.exists(dest_path):
                                os.remove(dest_path)
                            shutil.move(temp_file, dest_path)
                            console.print(
                                "[success]Manual recovery successful! File renamed and verified.[/success]"
                            )
                            recovered = True
                            break
                        except Exception as re:
                            console.print(
                                f"[error]Manual recovery failed for {temp_file}: {re}[/error]",
                                style="red",
                            )
                if recovered:
                    return True

                console.print(
                    f"[warning]yt-dlp failed with return code {process.returncode}. Trying fallback...[/warning]",
                    style="yellow",
                )
            except Exception as e:
                console.print(
                    f"[warning]yt-dlp execution failed: {e}. Trying fallback...[/warning]",
                    style="yellow",
                )

        # 2. Fall back to raw ffmpeg
        if not is_ffmpeg_installed():
            console.print(
                "[error]ffmpeg is not installed or not in system PATH. "
                "Cannot download HLS video streams.[/error]",
                style="red",
            )
            return False

        # Format custom headers string for ffmpeg
        ffmpeg_headers = f"Referer: {safe_referer}\r\nUser-Agent: {ua}\r\n"

        cmd = [
            ffmpeg_path,
            "-y",
        ]
        if self.proxy:
            cmd.extend(["-http_proxy", self.proxy])
        cmd.extend(
            [
                "-headers",
                ffmpeg_headers,
                "-i",
                m3u8_url,
                "-c",
                "copy",
                "-bsf:a",
                "aac_adtstoasc",
                dest_path,
            ]
        )

        console.print("[info]Downloading video stream via raw ffmpeg...[/info]")

        try:
            # Start ffmpeg process, hide log output unless there is an error
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                encoding="utf-8",
                errors="ignore",
            )

            # Show a spinner while downloading
            with Progress(
                SpinnerColumn(spinner_name="line"),
                TextColumn("[bold green]Downloading stream with ffmpeg..."),
                console=console,
            ) as progress:
                progress.add_task("ffmpeg")
                while process.poll() is None:
                    # Let it run and sleep slightly to not hog CPU
                    time.sleep(0.5)

            _stdout, stderr = process.communicate()
            if process.returncode != 0:
                console.print(
                    f"[error]ffmpeg failed with return code {process.returncode}[/error]",
                    style="red",
                )
                console.print(f"[dim]{stderr}[/dim]")
                if os.path.exists(dest_path):
                    os.remove(dest_path)
                return False

            return True
        except Exception as e:
            console.print(f"[error]ffmpeg execution failed: {e}[/error]", style="red")
            if os.path.exists(dest_path):
                os.remove(dest_path)
            return False

    def download_anime(
        self,
        anime_url: str,
        episode_range: str,
        lang: str,
        sub_only: bool = False,
        video_only: bool = False,
        tvdb_id: str | None = None,
        naming_format: str = "simple",
    ):
        """Scrape anime page and download selected subtitles and videos."""
        extractor = get_extractor_for_url(anime_url, self.http)
        if not extractor:
            console.print(f"[error]No extractor found for URL: {anime_url}[/error]", style="red")
            sys.exit(1)

        # Get details
        details = extractor.get_anime_details(anime_url)
        anime_title = details["title"]
        episodes = details["episodes"]

        if not episodes:
            console.print(
                f"[warning]No episodes found for anime: {anime_title}[/warning]", style="yellow"
            )
            return

        selected_episodes = parse_episode_range(episode_range, episodes)
        if not selected_episodes:
            console.print(
                f"[warning]No episodes matched range '{episode_range}'[/warning]", style="yellow"
            )
            return

        console.print(f"[info]Selected {len(selected_episodes)} episodes to download[/info]")

        # Parse series title and season
        series_title, season = self._parse_series_and_season(anime_title, anime_url)

        # Sync with TheTVDB
        tvdb_title = None
        token = None
        tvdb_api_key = os.environ.get("TVDB_API_KEY")
        if not tvdb_api_key:
            try:
                root_dir = os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
                env_path = os.path.join(root_dir, ".env")
                if os.path.exists(env_path):
                    with open(env_path, encoding="utf-8") as env_f:
                        for line in env_f:
                            if line.strip().startswith("TVDB_API_KEY="):
                                tvdb_api_key = line.strip().split("=", 1)[1].strip()
                                break
            except Exception:
                pass

        auto_search = False
        if tvdb_id and tvdb_id.lower() == "auto":
            auto_search = True
            tvdb_id = None
            console.print("[info]TVDB ID set to auto. Performing automatic search...[/info]")

            # Extract candidate search names from title and description
            candidates = [series_title]
            desc_lines = [
                line.strip() for line in details.get("description", "").split("\n") if line.strip()
            ]
            for line in desc_lines[:3]:
                if ";" in line:
                    for part in line.split(";"):
                        part_clean = part.strip()
                        if part_clean and len(part_clean) < 100:
                            candidates.append(part_clean)
                elif len(line) < 100 and not any(
                    stop in line.lower()
                    for stop in ["pg-13", "hd", "tv-14", "r -", "g-", "years ago", "synopsis"]
                ):
                    candidates.append(line)

            # Deduplicate candidates while keeping order
            seen = set()
            unique_candidates = []
            for c in candidates:
                c_clean = c.lower().strip()
                if c_clean not in seen:
                    seen.add(c_clean)
                    unique_candidates.append(c)

            # Try searching with each candidate
            for cand in unique_candidates:
                console.print(f"[info]Searching TVDB with candidate: '{cand}'...[/info]")
                tvdb_id = self._search_thetvdb_slug(cand)
                if tvdb_id:
                    break

            if not tvdb_id:
                console.print(
                    "[warning]Could not find any matching TVDB entry automatically.[/warning]",
                    style="yellow",
                )
                try:
                    user_input = input(
                        "Would you like to enter a TVDB ID/slug manually? (press Enter to use default): "
                    ).strip()
                    if user_input:
                        tvdb_id = user_input
                except Exception:
                    pass

        if tvdb_id:
            token = None
            if tvdb_api_key:
                try:
                    login_url = "https://api4.thetvdb.com/v4/login"
                    login_res = self.http.post_json(login_url, json_data={"apikey": tvdb_api_key})
                    token = login_res.get("data", {}).get("token")
                except Exception as api_err:
                    console.print(
                        f"[warning]Failed to login to TheTVDB API: {api_err}[/warning]",
                        style="yellow",
                    )

            # Fetch metadata from API, TVMaze, or Scrape
            tvdb_title, tvdb_year, tvdb_desc = self._get_tvdb_metadata(tvdb_id, token)

            if tvdb_title:
                verified = True
                if auto_search:
                    verified = self._verify_and_compare_metadata(
                        anime_title=anime_title,
                        anime_year=details.get("year"),
                        anime_desc=details.get("description", ""),
                        tvdb_title=tvdb_title,
                        tvdb_year=tvdb_year,
                        tvdb_desc=tvdb_desc,
                    )

                if verified:
                    console.print(f"[success]Using series title: '{tvdb_title}'[/success]")
                    series_title = tvdb_title
                else:
                    console.print(
                        "[info]Verification rejected. Continuing with default title.[/info]"
                    )
            else:
                console.print(
                    f"[warning]Could not resolve metadata for TVDB ID '{tvdb_id}'[/warning]",
                    style="yellow",
                )

        # Limit series title length to prevent Windows MAX_PATH (260 character limit) errors
        short_series_title = shorten_title_safe(series_title, max_len=80)
        clean_series_title = clean_folder_name(short_series_title)

        # Sonarr-compliant Season Folder Format: "Season 01" instead of "season-1"
        season_folder = f"Season {season:02d}"
        anime_dir = os.path.join(self.output_dir, clean_series_title, season_folder)
        os.makedirs(anime_dir, exist_ok=True)

        console.print(f"[info]Output directory: {anime_dir}[/info]")

        # Check if the title/URL has Part X (e.g. Part 2) and calculate offset/titles from TVDB
        episode_offset = 0
        part_num = self._parse_part_number(anime_title, anime_url)
        tvdb_titles = {}

        if tvdb_id:
            tvdb_slug = self._resolve_tvdb_slug(tvdb_id, tvdb_title, token)
            if tvdb_slug:
                if part_num > 1 or naming_format == "tvdb":
                    parts, tvdb_titles = self._fetch_tvdb_season_details(tvdb_slug, season)
                    if part_num > 1:
                        if len(parts) >= part_num:
                            target_part = parts[part_num - 1]
                            episode_offset = target_part[0]["ep_num"] - 1
                            console.print(
                                f"[success]Aligned TVDB Season {season} Part {part_num} offset to: +{episode_offset}[/success]"
                            )
                        else:
                            console.print(
                                f"[warning]Only detected {len(parts)} parts in TVDB season, but requested Part {part_num}. No offset applied.[/warning]",
                                style="yellow",
                            )

        successful_subs = 0
        successful_vids = 0
        skipped_subs = 0
        skipped_vids = 0
        failed_downloads = []

        # Loop through episodes
        for idx, ep in enumerate(selected_episodes):
            ep_num = ep["num"]
            formatted_ep = self._format_episode_num(ep_num, offset=episode_offset)

            # Determine extra title to append to filename prefix
            ep_title_suffix = ""
            if naming_format == "anikoto":
                raw_title = ep.get("clean_text") or ""
                clean_title_part = re.sub(r"^\d+\s*", "", raw_title).strip()
                if clean_title_part:
                    ep_title_suffix = f" - {clean_title_part}"
            elif naming_format == "tvdb" and tvdb_titles:
                try:
                    m_single_num = re.search(r"(\d+)", formatted_ep)
                    if m_single_num:
                        tvdb_ep_num = int(m_single_num.group(1))
                        raw_title = tvdb_titles.get(tvdb_ep_num) or ""
                        if raw_title:
                            ep_title_suffix = f" - {raw_title.strip()}"
                except Exception:
                    pass

            # Format filename prefix. If naming_format == "tvdb", follow Sonarr slug format: {lowercase-slug}-s{season:02d}e{formatted_ep}
            if naming_format == "tvdb":
                # Create slug from short_series_title
                series_slug = short_series_title.lower()
                # Replace non-alphanumeric with dashes
                series_slug = re.sub(r"[^a-z0-9]+", "-", series_slug)
                series_slug = series_slug.strip("-")

                # Check for SXXEYY format
                ep_label = f"s{season:02d}e{formatted_ep.lower()}"
                filename_prefix = clean_filename(f"{series_slug}-{ep_label}")
            else:
                filename_prefix = clean_filename(
                    f"{short_series_title} - S{season:02d}E{formatted_ep}{ep_title_suffix}"
                )

            ep_label = f"S{season:02d}E{formatted_ep}"
            self.emit_log(
                "info",
                "m3u8_stream",
                f"Đang xử lý {series_title} - {ep_label} ({idx + 1}/{len(selected_episodes)})",
            )
            console.print(
                f"\n[bold magenta]=== Processing {series_title} - {ep_label} "
                f"({idx + 1}/{len(selected_episodes)}) ===[/bold magenta]"
            )

            # 1. Determine if we need subtitles and video
            need_sub = not video_only
            need_video = not sub_only

            sub_success = not need_sub
            vid_success = not need_video

            sub_skipped_this_ep = False
            video_skipped_this_ep = False

            # Check if subtitle already exists for the requested language
            sub_lang_code = resolve_sub_lang_tag("", lang)
            candidate_tags = get_target_lang_candidate_tags(lang)
            existing_sub_found = False
            sub_filename_default = f"{filename_prefix}.{sub_lang_code}.srt"

            for ext_chk in ("srt", "vtt"):
                for tag_chk in candidate_tags:
                    check_path = os.path.join(anime_dir, f"{filename_prefix}.{tag_chk}.{ext_chk}")
                    if os.path.exists(check_path) and os.path.getsize(check_path) > 100:
                        existing_sub_found = True
                        sub_filename_default = f"{filename_prefix}.{tag_chk}.{ext_chk}"
                        break
                if existing_sub_found:
                    break

            if need_sub and existing_sub_found:
                console.print(
                    f"[success]Subtitle already exists and is valid: {sub_filename_default} (Skipping)[/success]"
                )
                skipped_subs += 1
                sub_success = True
                sub_skipped_this_ep = True

            # Check if video already exists
            video_filename = f"{filename_prefix}.mp4"
            video_path = os.path.join(anime_dir, video_filename)
            if (
                need_video
                and os.path.exists(video_path)
                and os.path.getsize(video_path) > 5 * 1024 * 1024
            ):
                console.print(
                    f"[success]Video already exists and is valid: {video_filename} (Skipping)[/success]"
                )
                skipped_vids += 1
                vid_success = True
                video_skipped_this_ep = True

            if not (sub_success and vid_success):
                # Fetch available servers
                servers = []
                if hasattr(extractor, "get_episode_servers"):
                    servers = extractor.get_episode_servers(ep)

                if not servers:
                    servers = [None]
                else:
                    # Apply single server target filter
                    if self.only_server:
                        original_len = len(servers)
                        servers = [
                            s
                            for s in servers
                            if self.only_server.lower() in s.get("name", "").lower()
                        ]
                        if len(servers) < original_len:
                            console.print(
                                f"[info]Restricted to {len(servers)} servers matching '{self.only_server}'.[/info]"
                            )
                        if not servers:
                            console.print(
                                f"[warning]No servers found matching '{self.only_server}'. Restoring original list.[/warning]",
                                style="yellow",
                            )
                            # Fetch original servers back
                            if hasattr(extractor, "get_episode_servers"):
                                servers = extractor.get_episode_servers(ep)
                            else:
                                servers = [None]

                    # Apply server exclusions
                    if self.exclude_servers:
                        original_len = len(servers)
                        servers = [
                            s
                            for s in servers
                            if not any(
                                ex.lower() in s.get("name", "").lower()
                                for ex in self.exclude_servers
                            )
                        ]
                        if len(servers) < original_len:
                            console.print(
                                f"[info]Excluded {original_len - len(servers)} servers based on exclude list.[/info]"
                            )

                    def get_pref_index(name: str) -> int:
                        # Use custom priority if specified, otherwise prioritize high-speed, stable servers first
                        prefs = (
                            self.server_priority
                            if self.server_priority
                            else [
                                "mega",
                                "hd",
                                "vidstream",
                                "vidcloud",
                                "megacloud",
                                "vidplay",
                                "rapidcloud",
                            ]
                        )
                        name_lower = name.lower()
                        for idx_pref, pref in enumerate(prefs):
                            if pref in name_lower:
                                return idx_pref
                        return len(prefs)

                    def get_type_priority(t: str) -> int:
                        # Priority 0: Soft sub / separate tracks
                        if t == "sub":
                            return 0
                        # Priority 2: Hard sub (embedded video sub tracks)
                        if t == "hsub":
                            return 2
                        # Priority 1: Default/fallback/other
                        return 1

                    servers.sort(
                        key=lambda s: (
                            get_type_priority(s.get("type", "sub")),
                            get_pref_index(s.get("name", "")),
                        )
                    )

                # Direct prioritized server resolution (Lazy On-Demand)
                valid_servers_data = []
                if self.interactive:
                    console.print(
                        "[info]Pre-resolving servers to verify anime and episode matching...[/info]"
                    )
                    resolved_servers_data = []
                    for server in servers:
                        server_name = server["name"] if server else "Default"
                        try:
                            ep_data = extractor.get_episode_data(ep, lang, server_info=server)
                            hashes = extract_hashes_from_url(ep_data.get("video_url"))
                            resolved_servers_data.append(
                                {"server": server, "ep_data": ep_data, "hashes": hashes}
                            )
                        except Exception as e:
                            console.print(f"[dim]Failed to resolve server {server_name}: {e}[/dim]")

                    if resolved_servers_data:
                        from rich.prompt import IntPrompt
                        from rich.table import Table

                        table = Table(
                            title=f"\n[bold cyan]Available Servers for Ep {ep['num']}[/bold cyan]"
                        )
                        table.add_column("Index", justify="center", style="cyan", no_wrap=True)
                        table.add_column("Server Name", style="magenta")
                        table.add_column("Has Video?", justify="center", style="green")
                        table.add_column("Has Soft Sub?", justify="center", style="yellow")

                        for idx_s, item in enumerate(resolved_servers_data):
                            s = item["server"]
                            ep_d = item["ep_data"]
                            table.add_row(
                                str(idx_s + 1),
                                s["name"] if s else "Default",
                                "Yes" if ep_d.get("video_url") else "No",
                                "Yes" if ep_d.get("subtitles") else "No",
                            )
                        console.print(table)

                        choice = IntPrompt.ask(
                            "Select server to download",
                            choices=[str(i + 1) for i in range(len(resolved_servers_data))],
                            default=1,
                        )
                        selected_item = resolved_servers_data[choice - 1]
                        valid_servers_data = [(selected_item["server"], selected_item["ep_data"])]
                else:
                    # Headless / GUI Mode: Directly iterate through sorted preferred servers
                    valid_servers_data = [(s, None) for s in servers]

                # Try servers one by one until we get what we need
                for s_idx, (server, cached_ep_data) in enumerate(valid_servers_data):
                    server_name = server["name"] if server else "Default"
                    console.print(
                        f"[info]Trying server {s_idx + 1}/{len(valid_servers_data)}: {server_name}[/info]"
                    )

                    ep_data = cached_ep_data
                    if ep_data is None:
                        try:
                            ep_data = extractor.get_episode_data(ep, lang, server_info=server)
                        except Exception as re_err:
                            console.print(f"[dim]Resolution failed: {re_err}. Trying next...[/dim]")
                            continue

                    if not ep_data or not (ep_data.get("video_url") or ep_data.get("subtitles")):
                        continue

                    # Handle Subtitles
                    if need_sub and not sub_success:
                        sub_tracks = ep_data.get("subtitles", [])
                        if not sub_tracks:
                            # Fallback logic for Spanish subtitles if not found
                            if lang.lower() in (
                                "es",
                                "spanish",
                                "espanol",
                                "español",
                                "spa",
                                "es-la",
                                "latam",
                            ):
                                console.print(
                                    f"[warning]Spanish subtitles not found on server {server_name}. Falling back to English.[/warning]",
                                    style="yellow",
                                )
                                try:
                                    fallback_data = extractor.get_episode_data(
                                        ep, "en", server_info=server
                                    )
                                    sub_tracks = fallback_data.get("subtitles", [])
                                except Exception as fe:
                                    console.print(
                                        f"[dim]Fallback to English subtitles failed: {fe}[/dim]"
                                    )

                        if not sub_tracks:
                            console.print(
                                f"[warning]No subtitles found matching language: {lang} on server {server_name}[/warning]",
                                style="yellow",
                            )
                        else:
                            for track in sub_tracks:
                                sub_url = track["url"]
                                sub_label = clean_filename(track["label"])
                                label_suffix = f" - {sub_label}" if len(sub_tracks) > 1 else ""
                                ext = (
                                    "srt"
                                    if sub_url.lower().endswith(".srt") or ".vtt" in sub_url.lower()
                                    else "vtt"
                                )
                                # Determine actual language tag from label for automatic media player recognition (es-LA, es-ES, es, en, vi)
                                actual_lang_tag = resolve_sub_lang_tag(track.get("label", ""), lang)
                                sub_lang_suffix = f".{actual_lang_tag}"

                                if label_suffix:
                                    sub_filename = (
                                        f"{filename_prefix}{label_suffix}{sub_lang_suffix}.{ext}"
                                    )
                                else:
                                    sub_filename = f"{filename_prefix}{sub_lang_suffix}.{ext}"

                                if ".vtt" in sub_url.lower() and ext == "vtt":
                                    sub_filename = sub_filename[:-4] + ".srt"
                                sub_path = os.path.join(anime_dir, sub_filename)

                                if os.path.exists(sub_path) and os.path.getsize(sub_path) > 100:
                                    console.print(
                                        f"[success]Subtitle already exists and is valid: {sub_filename} (Skipping)[/success]"
                                    )
                                    skipped_subs += 1
                                    sub_success = True
                                    break

                                max_sub_retries = 3
                                current_sub_success = False
                                file_missing = False
                                for sub_attempt in range(max_sub_retries):
                                    console.print(
                                        f"[info]Downloading subtitle (Attempt {sub_attempt + 1}/{max_sub_retries}): {sub_filename}[/info]"
                                    )
                                    try:
                                        # Dual-referer strategy: Try safe origin-only referrer first, fallback to full referrer
                                        full_ref = track.get("referer") or anime_url
                                        safe_sub_ref = get_safe_referer(full_ref)
                                        sub_res = None
                                        try:
                                            sub_res = self.http.get(sub_url, referer=safe_sub_ref)
                                            if sub_res.status_code == 404:
                                                file_missing = True
                                                raise ValueError("HTTP 404 Not Found")
                                            if (
                                                sub_res.status_code != 200
                                                or not sub_res.text.strip()
                                            ):
                                                sub_res = None
                                        except Exception as e:
                                            if "404" in str(e):
                                                file_missing = True
                                                raise
                                            pass

                                        if sub_res is None:
                                            try:
                                                sub_res = self.http.get(sub_url, referer=full_ref)
                                                if sub_res.status_code != 200:
                                                    raise ValueError(f"HTTP {sub_res.status_code}")
                                            except Exception as e:
                                                raise ValueError(
                                                    f"HTTP {sub_res.status_code}"
                                                    if sub_res
                                                    else str(e)
                                                ) from e

                                        sub_text = sub_res.text
                                        if ".vtt" in sub_url.lower():
                                            sub_text = vtt_to_srt(sub_text)
                                        with open(sub_path, "w", encoding="utf-8") as f:
                                            f.write(sub_text)
                                        if (
                                            os.path.exists(sub_path)
                                            and os.path.getsize(sub_path) > 100
                                        ):
                                            console.print(
                                                f"[success]Subtitle saved and verified: {sub_filename}[/success]"
                                            )
                                            successful_subs += 1
                                            current_sub_success = True
                                            break
                                        else:
                                            raise ValueError("Saved subtitle file is empty")
                                    except Exception as e:
                                        console.print(
                                            f"[warning]Subtitle download attempt {sub_attempt + 1} failed: {e}[/warning]",
                                            style="yellow",
                                        )
                                        if os.path.exists(sub_path):
                                            try:
                                                os.remove(sub_path)
                                            except Exception:
                                                pass
                                        if file_missing:
                                            break
                                        time.sleep(1)
                                if current_sub_success:
                                    sub_success = True
                                    break

                    # Handle Video
                    if need_video and not vid_success:
                        video_url = ep_data.get("video_url")
                        player_url = ep_data.get("player_url")
                        if not video_url:
                            console.print(
                                f"[warning]No video stream URL resolved for server {server_name}[/warning]",
                                style="yellow",
                            )
                        else:
                            max_vid_retries = 3
                            current_vid_success = False
                            for vid_attempt in range(max_vid_retries):
                                console.print(
                                    f"[info]Downloading video (Attempt {vid_attempt + 1}/{max_vid_retries}) to: {video_filename}[/info]"
                                )
                                success = False
                                try:
                                    if ".m3u8" in video_url.lower():
                                        success = self.download_hls_stream(
                                            video_url, video_path, referer=player_url or anime_url
                                        )
                                    else:
                                        success = self.download_file_chunked(
                                            video_url, video_path, referer=player_url or anime_url
                                        )
                                except DNSError as de:
                                    console.print(
                                        f"[warning]DNS resolution failed on server {server_name}: {de}. Skipping this server immediately.[/warning]",
                                        style="yellow",
                                    )
                                    break
                                except Exception as e:
                                    console.print(
                                        f"[warning]Video download failed on server {server_name}: {e}. Skipping this server immediately.[/warning]",
                                        style="yellow",
                                    )
                                    break
                                if (
                                    success
                                    and os.path.exists(video_path)
                                    and os.path.getsize(video_path) > 5 * 1024 * 1024
                                ):
                                    console.print(
                                        f"[success]Video downloaded and verified: {video_filename}[/success]"
                                    )
                                    successful_vids += 1
                                    current_vid_success = True
                                    break
                                else:
                                    console.print(
                                        f"[warning]Video download or validation failed on attempt {vid_attempt + 1}[/warning]",
                                        style="yellow",
                                    )
                                    if os.path.exists(video_path):
                                        try:
                                            os.remove(video_path)
                                        except Exception:
                                            pass
                                    time.sleep(2)
                            if current_vid_success:
                                vid_success = True

                    # If all required resources for this episode are satisfied, we can stop trying servers
                    if sub_success and vid_success:
                        break

                # If after checking all servers we still failed to get required files
                if not (sub_success and vid_success):
                    missing_parts = []
                    if not sub_success:
                        missing_parts.append("Subtitle")
                    if not vid_success:
                        missing_parts.append("Video")
                    failed_downloads.append(
                        (
                            ep_label,
                            " & ".join(missing_parts),
                            "All available servers failed or were empty",
                        )
                    )

            # Delay between episode scraping/download sessions to avoid rate limits
            if idx < len(selected_episodes) - 1:
                # If we skipped both download tasks, we can use a shorter delay
                if (video_only or sub_skipped_this_ep) and (sub_only or video_skipped_this_ep):
                    sleep_delay = 1.0
                else:
                    sleep_delay = random.uniform(*self.delay_range)
                console.print(f"[dim]Sleeping for {sleep_delay:.1f}s between episodes...[/dim]")
                time.sleep(sleep_delay)

        # Finish summary
        console.print("\n[bold green]=== Download Batch Completed ===[/bold green]")
        console.print("[success]Total items processed:[/success]")
        if not video_only:
            console.print(f"  - Subtitles downloaded: {successful_subs} file(s)")
            if skipped_subs > 0:
                console.print(f"  - Subtitles skipped (already existed): {skipped_subs} file(s)")
        if not sub_only:
            console.print(f"  - Videos downloaded: {successful_vids} file(s)")
            if skipped_vids > 0:
                console.print(f"  - Videos skipped (already existed): {skipped_vids} file(s)")

        if failed_downloads:
            console.print("\n[bold red]=== Failed Downloads Summary ===[/bold red]")
            for ep_lbl, item_type, reason in failed_downloads:
                console.print(f"  - [red]{ep_lbl} ({item_type}): {reason}[/red]")

    def _parse_series_and_season(self, title: str, url: str) -> tuple[str, int]:
        """Parse the base series title and season number from the raw title or URL."""
        season = 1

        # 1. Check URL slug
        parsed_url = urlparse(url)
        slug = parsed_url.path.split("/")[-1] if parsed_url.path else ""

        # Check for named seasons of popular shows or general known mappings
        slug_lower = slug.lower()
        title_lower = title.lower()
        if "stone-wars" in slug_lower or "stone wars" in title_lower:
            season = 2
        elif "new-world" in slug_lower or "new world" in title_lower:
            season = 3
        elif "science-future" in slug_lower or "science future" in title_lower:
            season = 4
        else:
            # Check ordinal season like "3rd-season" in URL or "3rd Season" in title
            m_url_ord = re.search(r"(\d+)(?:st|nd|rd|th)?[-_]?season", slug, re.IGNORECASE)
            m_title_ord = re.search(
                r"(\d+)(?:st|nd|rd|th)?\s*(?:season|series|ss)", title, re.IGNORECASE
            )
            if m_url_ord:
                season = int(m_url_ord.group(1))
            elif m_title_ord:
                season = int(m_title_ord.group(1))
            else:
                m_url = re.search(r"season[-_]?(\d+)", slug, re.IGNORECASE)
                if m_url:
                    season = int(m_url.group(1))
                else:
                    # 2. Check title text
                    m_title = re.search(
                        r"(?:season|series|ss)\s*[-_]?\s*(\d+)", title, re.IGNORECASE
                    )
                    if m_title:
                        season = int(m_title.group(1))
                    m_s = re.search(r"\bS(\d+)\b", title, re.IGNORECASE)
                    if m_s:
                        season = int(m_s.group(1))

        # Special handling for JoJo's Bizarre Adventure parts to match TVDB Season mapping
        if "jojo" in slug_lower or "jojo" in title_lower:
            m_part = re.search(r"part[-_\s]*(\d+)", slug + " " + title, re.IGNORECASE)
            if m_part:
                part_num = int(m_part.group(1))
                # TVDB Mapping:
                # Part 1 (Phantom Blood) & Part 2 (Battle Tendency) -> Season 1 (2012)
                # Part 3 (Stardust Crusaders) -> Season 2
                # Part 4 (Diamond is Unbreakable) -> Season 3
                # Part 5 (Golden Wind) -> Season 4
                # Part 6 (Stone Ocean) -> Season 5
                if part_num in (1, 2):
                    season = 1
                elif part_num == 3:
                    season = 2
                elif part_num == 4:
                    season = 3
                elif part_num == 5:
                    season = 4
                elif part_num == 6:
                    season = 5

        # Clean up the series title to get only the series base name
        clean_title = title
        # Remove ordinal season e.g. "3rd Season", "3rd-season"
        clean_title = re.sub(
            r"\s*\d+(?:st|nd|rd|th)?\s*(?:season|series|ss)", "", clean_title, flags=re.IGNORECASE
        )
        # Remove Season X
        clean_title = re.sub(
            r"\s*(?:season|series|ss)\s*[-_]?\s*\d+", "", clean_title, flags=re.IGNORECASE
        )
        # Remove S0X/SX
        clean_title = re.sub(r"\s*\bS\d+\b", "", clean_title, flags=re.IGNORECASE)
        # Remove trailing colons/dashes/whitespace
        clean_title = re.sub(r"\s*[:\-]\s*$", "", clean_title)
        clean_title = clean_title.strip()

        if not clean_title:
            clean_title = title

        return clean_title, season

    def _format_episode_num(self, ep_num_str: str, offset: int = 0) -> str:
        """Format episode string to follow Sonarr's Prefixed Range or 2-digit zero-padding."""
        clean_ep = re.sub(r"^[^\d]+", "", ep_num_str)

        # Check range format like 12-13
        m_range = re.search(r"(\d+)\s*[-_]\s*(\d+)", clean_ep)
        if m_range:
            ep1 = int(m_range.group(1)) + offset
            ep2 = int(m_range.group(2)) + offset
            return f"{ep1:02d}-e{ep2:02d}"

        # Single episode
        m_single = re.search(r"(\d+)", clean_ep)
        if m_single:
            ep_val = int(m_single.group(1)) + offset
            return f"{ep_val:02d}"

        return ep_num_str

    def _search_thetvdb_slug(self, title: str) -> str | None:
        import urllib.parse

        # Clean title - remove common anime metadata, part labels, season info, and release types
        clean_title = title
        clean_title = re.sub(r"\s*:\s*.*", "", clean_title)  # Remove subtitles/colons

        # 1. Strip Release Formats & Season Type Tags (OVA, ONA, Movie, Specials, SP, Spin-off, etc.)
        clean_title = re.sub(
            r"\b(?:ova|ona|movie|specials?|sp|spin[-_]?off|special\s+episodes?)\b",
            "",
            clean_title,
            flags=re.IGNORECASE,
        )

        # 2. Strip Seasonal Timelines (Winter, Spring, Summer, Autumn, Fall Season)
        clean_title = re.sub(
            r"\b(?:winter|spring|summer|autumn|fall)\s*(?:season)?\b",
            "",
            clean_title,
            flags=re.IGNORECASE,
        )

        # 3. Strip Story Progressions & Arc details (Canon, Filler, Recap, Arc)
        clean_title = re.sub(
            r"\b(?:canon|filler|recap|arc)\b", "", clean_title, flags=re.IGNORECASE
        )

        # 4. Strip Episode Component Tags (OP, ED, Preview, Opening, Ending)
        clean_title = re.sub(
            r"\b(?:op|ed|preview|opening|ending)\b", "", clean_title, flags=re.IGNORECASE
        )

        # 5. Strip common Genre Tags if appended (Isekai, Harem, Moe, Mecha, etc. to prevent search pollutant)
        clean_title = re.sub(
            r"\b(?:shounen|shoujo|seinen|josei|isekai|mecha|slice\s+of\s+life|moe|harem|ecchi|yuri|yaoi|gore|cyberpunk|steampunk|dystopia|psychological|thriller|iyashikei|sports|music|idol|historical|fantasy|sci[-_]?fi|supernatural|romance|comedy|parody|drama|adventure|action)\b",
            "",
            clean_title,
            flags=re.IGNORECASE,
        )

        # 6. Standard cleanup
        clean_title = re.sub(
            r"\s*\b(?:uncensored|censored|uncut|bd|tv|sub|dub)\b.*",
            "",
            clean_title,
            flags=re.IGNORECASE,
        )
        clean_title = re.sub(
            r"\s*(?:season|series|ss|part)\s*[-_]?\s*\d+", "", clean_title, flags=re.IGNORECASE
        )
        clean_title = re.sub(r"\s*\bS\d+\b", "", clean_title, flags=re.IGNORECASE)
        clean_title = re.sub(r"[\[\({][^\]\)}]*[\]\)}]", "", clean_title)  # Remove bracketed info
        clean_title = re.sub(r"\s*[:\-]\s*$", "", clean_title)
        clean_title = re.sub(r"\s+", " ", clean_title)
        clean_title = clean_title.strip()

        # Candidate search strings (original and simplified)
        search_queries = [clean_title]
        # If it contains Japanese particles or apostrophes, try a query without them
        clean_alt = clean_title.replace("'s", "s").replace("'", "")
        if clean_alt != clean_title:
            search_queries.append(clean_alt)

        for query_str in search_queries:
            query = f"{query_str} thetvdb"
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            try:
                res = self.http.get(url, headers=headers)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, "html.parser")
                    for a in soup.find_all("a"):
                        href = a.get("href", "")
                        decoded_href = urllib.parse.unquote(href)
                        if "/series/" in decoded_href:
                            m = re.search(r"thetvdb\.com/series/([^/&\s%?]+)", decoded_href)
                            if m:
                                slug = m.group(1)
                                return slug
            except Exception as e:
                console.print(
                    f"[warning]DuckDuckGo search for TVDB failed: {e}[/warning]", style="yellow"
                )
        return None

    def _get_tvdb_metadata(
        self, tvdb_id: str, token: str | None = None
    ) -> tuple[str | None, int | None, str]:
        """Retrieve title, year, and description from TVDB via API or HTML scrape."""
        title, year, description = None, None, ""

        # 1. Try API if authenticated
        if token:
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
            try:
                eng_series_url = f"https://api4.thetvdb.com/v4/series/{tvdb_id}/translations/eng"
                eng_res = self.http.get_json(eng_series_url, headers=headers)
                data = eng_res.get("data", {})
                if data.get("name"):
                    title = data["name"]
                    description = data.get("overview", "")
            except Exception:
                pass

            if not title:
                try:
                    series_url = f"https://api4.thetvdb.com/v4/series/{tvdb_id}"
                    series_res = self.http.get_json(series_url, headers=headers)
                    data = series_res.get("data", {})
                    title = data.get("name")
                    description = data.get("overview", "")
                except Exception:
                    pass
            if title:
                try:
                    first_aired = data.get("firstAired")
                    if first_aired:
                        m_yr = re.search(r"\b(19\d{2}|20\d{2})\b", first_aired)
                        if m_yr:
                            year = int(m_yr.group(1))
                except Exception:
                    pass

        # 2. Try TVMaze fallback if numeric
        if not title and tvdb_id.isdigit():
            try:
                tvmaze_url = f"https://api.tvmaze.com/lookup/shows?thetvdb={tvdb_id}"
                res = self.http.get_json(tvmaze_url)
                if res.get("name"):
                    title = re.sub(r"\s*:\s*.*", "", res["name"])
                    title = re.sub(r"\s*\(Season\s*\d+\)", "", title, flags=re.IGNORECASE)
                    description = res.get("summary", "")
                    description = re.sub(r"<[^>]+>", "", description)
                    premiered = res.get("premiered")
                    if premiered:
                        m_yr = re.search(r"\b(19\d{2}|20\d{2})\b", premiered)
                        if m_yr:
                            year = int(m_yr.group(1))
            except Exception:
                pass

        # 3. Direct HTML Scrape
        if not title:
            try:
                scrape_url = f"https://thetvdb.com/series/{tvdb_id}"
                soup = self.http.get_soup(scrape_url)

                eng_el = soup.find(
                    "div", class_="change_translation_text", attrs={"data-language": "eng"}
                )
                if eng_el:
                    if eng_el.get("data-title"):
                        title = eng_el["data-title"].strip()
                    p_el = eng_el.find("p")
                    if p_el:
                        description = p_el.text.strip()

                if not title:
                    title_el = soup.select_one(
                        "h1#series_title, #series_title, h1.title, .thumbnail-title"
                    )
                    if title_el:
                        title = title_el.text.strip()
                        title = re.sub(r"\s*\(Season\s*\d+\)", "", title, flags=re.IGNORECASE)

                aired_label = soup.find("strong", string=lambda s: s and "First Aired" in s)
                if aired_label:
                    sibling = aired_label.find_next_sibling("span")
                    if sibling:
                        m_yr = re.search(r"\b(19\d{2}|20\d{2})\b", sibling.text)
                        if m_yr:
                            year = int(m_yr.group(1))
            except Exception:
                pass

        return title, year, description

    def _verify_and_compare_metadata(
        self,
        anime_title: str,
        anime_year: int | None,
        anime_desc: str,
        tvdb_title: str,
        tvdb_year: int | None,
        tvdb_desc: str,
    ) -> bool:
        """Verify match quality by comparing names, years, and descriptions."""
        # Calculate Title similarity (token overlap)
        words1 = set(re.findall(r"\w+", anime_title.lower()))
        words2 = set(re.findall(r"\w+", tvdb_title.lower()))
        title_sim = (
            len(words1.intersection(words2)) / min(len(words1), len(words2))
            if words1 and words2
            else 0.0
        )

        # Calculate Year match
        year_match = 0.5
        if anime_year and tvdb_year:
            year_match = 1.0 if abs(anime_year - tvdb_year) <= 1 else 0.0

        # Calculate Description keyword match
        desc_words1 = set([w for w in re.findall(r"\w+", anime_desc.lower()) if len(w) >= 4])
        desc_words2 = set([w for w in re.findall(r"\w+", tvdb_desc.lower()) if len(w) >= 4])
        desc_sim = (
            len(desc_words1.intersection(desc_words2)) / min(len(desc_words1), len(desc_words2))
            if desc_words1 and desc_words2
            else 0.5
        )

        # Weighted confidence score
        confidence = (title_sim * 0.5) + (year_match * 0.3) + (desc_sim * 0.2)

        console.print("[info]Metadata comparison results:[/info]")
        console.print(f"  - Title Similarity: {title_sim:.2f}")
        console.print(
            f"  - Year Match: {year_match:.2f} (AniKoto: {anime_year or 'N/A'}, TVDB: {tvdb_year or 'N/A'})"
        )
        console.print(f"  - Description Match: {desc_sim:.2f}")
        console.print(f"  - Overall Confidence Score: [bold]{confidence:.2f}[/bold]")

        if confidence >= 0.70:
            console.print("[success]Verification passed! Confidence score is high.[/success]")
            return True

        console.print(
            "[warning]WARNING: Confidence score is low! Metadata might not match.[/warning]",
            style="yellow",
        )
        console.print("\n[bold yellow]--- DATA COMPARISON ---[/bold yellow]")
        console.print(f"[bold]AniKoto Title:[/bold] {anime_title}")
        console.print(f"[bold]TVDB Title   :[/bold] {tvdb_title}")
        console.print(f"[bold]AniKoto Year :[/bold] {anime_year or 'N/A'}")
        console.print(f"[bold]TVDB Year    :[/bold] {tvdb_year or 'N/A'}")
        console.print(f"[bold]AniKoto Desc :[/bold] {anime_desc[:120]}...")
        console.print(f"[bold]TVDB Desc    :[/bold] {tvdb_desc[:120]}...")
        console.print("[bold yellow]-----------------------[/bold yellow]\n")

        try:
            res = input("Do you want to proceed with this TVDB match? (Y/n): ").strip().lower()
            return res in ("", "y", "yes")
        except Exception:
            return True

    def _resolve_tvdb_slug(
        self, tvdb_id: str, tvdb_title: str | None = None, token: str | None = None
    ) -> str | None:
        """Resolve numeric TVDB ID or slug to TVDB series slug."""
        if not tvdb_id:
            return None
        if not tvdb_id.isdigit():
            return tvdb_id

        # Numeric ID, resolve using token
        if token:
            try:
                headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
                series_url = f"https://api4.thetvdb.com/v4/series/{tvdb_id}"
                series_res = self.http.get_json(series_url, headers=headers)
                slug = series_res.get("data", {}).get("slug")
                if slug:
                    return slug
            except Exception:
                pass

        # Fallback to TVMaze name + search
        title_to_search = tvdb_title
        if not title_to_search:
            try:
                tvmaze_url = f"https://api.tvmaze.com/lookup/shows?thetvdb={tvdb_id}"
                res = self.http.get_json(tvmaze_url)
                if res.get("name"):
                    title_to_search = res["name"]
            except Exception:
                pass

        if title_to_search:
            return self._search_thetvdb_slug(title_to_search)
        return None

    def _fetch_tvdb_season_details(
        self, tvdb_slug: str, season: int
    ) -> tuple[list[list[dict]], dict[int, str]]:
        """Fetch TVDB season page, group episodes by date gap > 45 days, and extract episode titles."""
        from datetime import datetime

        season_url = f"https://thetvdb.com/series/{tvdb_slug}/seasons/official/{season}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        parts = []
        titles = {}
        try:
            res = self.http.get(season_url, headers=headers)
            if res.status_code != 200:
                console.print(
                    f"[warning]Failed to fetch TVDB season page: HTTP {res.status_code}[/warning]",
                    style="yellow",
                )
                return parts, titles

            soup = BeautifulSoup(res.text, "html.parser")
            episodes = []
            for row in soup.select("tr"):
                cells = row.find_all("td")
                if len(cells) >= 2:
                    txt = cells[0].text.strip()
                    m_ep = re.search(r"S(\d+)E(\d+)", txt, re.IGNORECASE)
                    if m_ep:
                        ep_num = int(m_ep.group(2))
                        ep_title = cells[1].text.strip()
                        m_date = re.search(
                            r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b",
                            row.get_text(separator=" "),
                        )
                        date_val = None
                        if m_date:
                            date_val = datetime.strptime(m_date.group(0), "%B %d, %Y")
                        episodes.append({"ep_num": ep_num, "date": date_val, "title": ep_title})
                        titles[ep_num] = ep_title

            if not episodes:
                return parts, titles

            episodes.sort(key=lambda e: e["ep_num"])

            current_part = [episodes[0]]
            for i in range(1, len(episodes)):
                ep1 = episodes[i - 1]
                ep2 = episodes[i]
                has_gap = False
                if ep1["date"] and ep2["date"]:
                    delta = (ep2["date"] - ep1["date"]).days
                    if delta > 45:
                        has_gap = True
                if has_gap:
                    parts.append(current_part)
                    current_part = [ep2]
                else:
                    current_part.append(ep2)
            if current_part:
                parts.append(current_part)

        except Exception as e:
            console.print(
                f"[warning]Error fetching TVDB season details: {e}[/warning]", style="yellow"
            )

        return parts, titles

    def _parse_part_number(self, title: str, url: str) -> int:
        """Parse part number from title or URL supporting digit, English word, and Roman numeral formats."""
        for text in (title, url):
            if not text:
                continue
            # 1. Matches digits: e.g., Part 2, Part-3, Part_4, Part12
            m_digit = re.search(r"\bpart[-_\s]*(\d+)\b", text, re.IGNORECASE)
            if m_digit:
                val = int(m_digit.group(1))
                console.print(f"[info]Detected part number from '{text}': Part {val}[/info]")
                return val

            # 2. Matches Roman numerals: e.g., Part II, Part-IV, Part_IX
            m_roman = re.search(r"\bpart[-_\s]*([ivxldcm]+)\b", text, re.IGNORECASE)
            if m_roman:
                roman = m_roman.group(1).upper()
                roman_map = {
                    "I": 1,
                    "II": 2,
                    "III": 3,
                    "IV": 4,
                    "V": 5,
                    "VI": 6,
                    "VII": 7,
                    "VIII": 8,
                    "IX": 9,
                    "X": 10,
                }
                if roman in roman_map:
                    val = roman_map[roman]
                    console.print(
                        f"[info]Detected part number (Roman) from '{text}': Part {val}[/info]"
                    )
                    return val

            # 3. Matches written words: e.g., Part One, Part-Two, Part_Three
            m_word = re.search(
                r"\bpart[-_\s]*(one|two|three|four|five|six|seven|eight|nine|ten)\b",
                text,
                re.IGNORECASE,
            )
            if m_word:
                word = m_word.group(1).lower()
                word_map = {
                    "one": 1,
                    "two": 2,
                    "three": 3,
                    "four": 4,
                    "five": 5,
                    "six": 6,
                    "seven": 7,
                    "eight": 8,
                    "nine": 9,
                    "ten": 10,
                }
                if word in word_map:
                    val = word_map[word]
                    console.print(
                        f"[info]Detected part number (Word) from '{text}': Part {val}[/info]"
                    )
                    return val

        return 1
