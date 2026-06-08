import os
import random
import re
import shutil
import subprocess
import sys
import time
from urllib.parse import urlparse

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
    """Parse episode range strings (e.g. 'all', '1-5', '3,5,10-12') and select matching items."""
    range_str = range_str.strip().lower()
    if range_str == "all" or not range_str:
        return episodes_list

    selected = []
    # Split by comma for multiple parts
    parts = range_str.split(",")

    for part in parts:
        part = part.strip()
        if "-" in part:
            try:
                start_str, end_str = part.split("-")
                start = int(start_str.strip())
                end = int(end_str.strip())
            except ValueError:
                console.print(
                    f"[warning]Skipping invalid range part: {part}[/warning]", style="yellow"
                )
                continue

            for idx, ep in enumerate(episodes_list):
                # Attempt to extract digit from slug (e.g. ep-1 -> 1)
                num_match = re.search(r"\d+", ep["num"])
                val = int(num_match.group(0)) if num_match else (idx + 1)
                if start <= val <= end:
                    if ep not in selected:
                        selected.append(ep)
        else:
            try:
                val = int(part)
            except ValueError:
                console.print(
                    f"[warning]Skipping invalid episode part: {part}[/warning]", style="yellow"
                )
                continue

            for idx, ep in enumerate(episodes_list):
                num_match = re.search(r"\d+", ep["num"])
                val_ep = int(num_match.group(0)) if num_match else (idx + 1)
                if val == val_ep:
                    if ep not in selected:
                        selected.append(ep)

    # Sort selected episodes in the order they appear in the original list
    ep_slug_order = {ep["slug"]: idx for idx, ep in enumerate(episodes_list)}
    selected.sort(key=lambda ep: ep_slug_order.get(ep["slug"], 9999))

    return selected


class BatchDownloader:
    def __init__(self, output_dir: str = ".", delay_range: tuple = (3.0, 7.0)):
        self.output_dir = output_dir
        self.delay_range = delay_range
        self.http = HttpClient(delay_range=delay_range)

        # Load Chrome cookies for WAF/CDN bypass
        self.cookies_path = get_chrome_cookies_temp_file()
        if self.cookies_path:
            self.http.load_cookies_from_file(self.cookies_path)

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

                with open(dest_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
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
                m3u8_res = self.http.get(m3u8_url, referer=safe_referer)
            except Exception as e:
                err_msg = str(e)
                if any(k in err_msg for k in dns_keywords):
                    raise DNSError(f"DNS error fetching manifest: {err_msg}") from e
                raise

            if m3u8_res.status_code == 200 and m3u8_res.text:
                if "#EXT-X-KEY" in m3u8_res.text or "#EXT-X-SESSION-KEY" in m3u8_res.text:
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

                        def download_segment(idx, seg_url):
                            if dns_failed_event.is_set():
                                return idx, False, ("Cancelled due to DNS error", True)
                            try:
                                # Apply optimized local delay for CDN segments
                                time.sleep(random.uniform(0.1, 0.3))
                                if dns_failed_event.is_set():
                                    return idx, False, ("Cancelled due to DNS error", True)
                                res = self.http.get(
                                    seg_url, referer=safe_referer, retries=3, rate_limit=False
                                )
                                if res.status_code != 200 or not res.content:
                                    return idx, False, (f"HTTP {res.status_code}", False)
                                segment_data = res.content
                                if segment_data.startswith(png_header):
                                    segment_data = segment_data[len(png_header) :]
                                part_path = os.path.join(temp_dir, f"part_{idx:05d}.ts")
                                with open(part_path, "wb") as pf:
                                    pf.write(segment_data)
                                return idx, True, part_path
                            except Exception as e:
                                err_msg = str(e)
                                is_dns = any(k in err_msg for k in dns_keywords)
                                if is_dns:
                                    dns_failed_event.set()
                                return idx, False, (err_msg, is_dns)

                        max_workers = 8
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
                            remux_cmd, capture_output=True, text=True, check=False
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
            console.print(
                f"[warning]Native HLS downloader error or bypass: {e}. Trying fallback...[/warning]",
                style="yellow",
            )

        # 1. Try downloading with yt-dlp if available
        if yt_dlp_path:
            console.print("[info]Downloading video stream via yt-dlp (max 720p)...[/info]")
            cmd = [
                yt_dlp_path,
                m3u8_url,
                "--add-header",
                f"Referer:{safe_referer}",
                "--add-header",
                f"User-Agent:{ua}",
                "--extractor-args",
                "generic:impersonate",
                "-f",
                "best[height<=720]/best",
                "-o",
                dest_path,
                "--no-playlist",
                "--concurrent-fragments",
                "5",
            ]
            if ffmpeg_dir:
                cmd.extend(["--ffmpeg-location", ffmpeg_dir])
            if self.cookies_path:
                cmd.extend(["--cookies", self.cookies_path])

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
            "-headers",
            ffmpeg_headers,
            "-allowed_segment_extensions",
            "ALL",
            "-i",
            m3u8_url,
            "-c",
            "copy",
            "-bsf:a",
            "aac_adtstoasc",
            dest_path,
        ]

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

        # Limit series title length to prevent Windows MAX_PATH (260 character limit) errors
        short_series_title = shorten_title_safe(series_title, max_len=80)
        clean_series_title = clean_folder_name(short_series_title)
        season_folder = f"season-{season}"
        anime_dir = os.path.join(self.output_dir, clean_series_title, season_folder)
        os.makedirs(anime_dir, exist_ok=True)

        console.print(f"[info]Output directory: {anime_dir}[/info]")

        successful_subs = 0
        successful_vids = 0
        skipped_subs = 0
        skipped_vids = 0
        failed_downloads = []

        # Loop through episodes
        for idx, ep in enumerate(selected_episodes):
            ep_num = ep["num"]
            formatted_ep = self._format_episode_num(ep_num)

            # Format filename prefix as {series-cleantitle}-s{season:00}e{episode:00}
            filename_prefix = clean_filename(f"{short_series_title}-s{season:02d}e{formatted_ep}")
            ep_label = f"s{season:02d}e{formatted_ep}"
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

            # Check if subtitle already exists
            sub_filename_default = f"{filename_prefix}.srt"
            sub_path_default = os.path.join(anime_dir, sub_filename_default)
            if (
                need_sub
                and os.path.exists(sub_path_default)
                and os.path.getsize(sub_path_default) > 100
            ):
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

                    def get_pref_index(name: str) -> int:
                        prefs = ["vidstream", "vidcloud", "hd", "megacloud", "rapidcloud"]
                        name_lower = name.lower()
                        for idx_pref, pref in enumerate(prefs):
                            if pref in name_lower:
                                return idx_pref
                        return len(prefs)

                    if sub_only:
                        servers = [s for s in servers if s.get("type") == "sub"]

                    servers.sort(
                        key=lambda s: (
                            0 if s.get("type") == "sub" else 1,
                            get_pref_index(s.get("name", "")),
                        )
                    )

                # Pre-resolve stream sources to verify correctness (consensus check)
                resolved_servers_data = []
                hash_counts = {}

                console.print(
                    "[info]Pre-resolving servers to verify anime and episode matching...[/info]"
                )
                for server in servers:
                    server_name = server["name"] if server else "Default"
                    try:
                        ep_data = extractor.get_episode_data(ep, lang, server_info=server)
                        video_url = ep_data.get("video_url")
                        hashes = extract_hashes_from_url(video_url)
                        if not hashes:
                            subtitles = ep_data.get("subtitles", [])
                            if subtitles:
                                hashes = extract_hashes_from_url(subtitles[0].get("url"))

                        resolved_servers_data.append(
                            {
                                "server": server,
                                "ep_data": ep_data,
                                "hashes": hashes,
                            }
                        )

                        if hashes:
                            hash_counts[hashes] = hash_counts.get(hashes, 0) + 1
                    except Exception as e:
                        console.print(f"[dim]Failed to resolve server {server_name}: {e}[/dim]")

                # Find consensus hash (majority vote)
                consensus_hash = None
                if hash_counts:
                    sorted_hashes = sorted(hash_counts.items(), key=lambda x: x[1], reverse=True)
                    if len(sorted_hashes) == 1 or sorted_hashes[0][1] > sorted_hashes[1][1]:
                        consensus_hash = sorted_hashes[0][0]

                # Filter resolved servers by consensus
                valid_servers_data = []
                for item in resolved_servers_data:
                    server = item["server"]
                    server_name = server["name"] if server else "Default"
                    ep_data = item["ep_data"]
                    hashes = item["hashes"]

                    if consensus_hash and hashes and hashes != consensus_hash:
                        console.print(
                            f"[warning]Skipping server {server_name}: resolved media hash ({hashes[0][:8]}) "
                            f"does not match consensus family ({consensus_hash[0][:8]}).[/warning]",
                            style="yellow",
                        )
                        continue
                    valid_servers_data.append((server, ep_data))

                if not valid_servers_data and resolved_servers_data:
                    # Fallback to resolved servers if everything got filtered out
                    valid_servers_data = [
                        (item["server"], item["ep_data"]) for item in resolved_servers_data
                    ]

                # Try servers one by one until we get what we need
                for s_idx, (server, ep_data) in enumerate(valid_servers_data):
                    server_name = server["name"] if server else "Default"
                    console.print(
                        f"[info]Trying server {s_idx + 1}/{len(valid_servers_data)}: {server_name}[/info]"
                    )

                    # Handle Subtitles
                    if need_sub and not sub_success:
                        sub_tracks = ep_data.get("subtitles", [])
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
                                sub_filename = f"{filename_prefix}{label_suffix}.{ext}"
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
                                for sub_attempt in range(max_sub_retries):
                                    console.print(
                                        f"[info]Downloading subtitle (Attempt {sub_attempt + 1}/{max_sub_retries}): {sub_filename}[/info]"
                                    )
                                    try:
                                        sub_res = self.http.get(sub_url, referer=track["referer"])
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

        m_url = re.search(r"season[-_]?(\d+)", slug, re.IGNORECASE)
        if m_url:
            season = int(m_url.group(1))
        else:
            # 2. Check title text
            m_title = re.search(r"(?:season|series|ss)\s*[-_]?\s*(\d+)", title, re.IGNORECASE)
            if m_title:
                season = int(m_title.group(1))
            else:
                m_s = re.search(r"\bS(\d+)\b", title, re.IGNORECASE)
                if m_s:
                    season = int(m_s.group(1))

        # Clean up the series title to get only the series base name
        clean_title = title
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

    def _format_episode_num(self, ep_num_str: str) -> str:
        """Format episode string to follow Sonarr's Prefixed Range or 2-digit zero-padding."""
        clean_ep = re.sub(r"^[^\d]+", "", ep_num_str)

        # Check range format like 12-13
        m_range = re.search(r"(\d+)\s*[-_]\s*(\d+)", clean_ep)
        if m_range:
            return f"{int(m_range.group(1)):02d}-e{int(m_range.group(2)):02d}"

        # Single episode
        m_single = re.search(r"(\d+)", clean_ep)
        if m_single:
            return f"{int(m_single.group(1)):02d}"

        return ep_num_str
