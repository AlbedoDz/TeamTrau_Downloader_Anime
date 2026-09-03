"""Multi-threaded HLS Fragment Downloader module for fast parallel segment fetching."""

import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

from downloader.core import get_local_tool_path
from downloader.utils import HttpClient, console


class MultiThreadedHLSDownloader:
    """Fast concurrent HLS segment downloader with automatic remuxing."""

    def __init__(self, http_client: HttpClient, max_workers: int = 8):
        self.http = http_client
        self.max_workers = max_workers

    def download_stream(self, m3u8_url: str, dest_path: str, referer: str | None = None) -> bool:
        """Download HLS stream fragments in parallel and remux to destination MP4."""
        console.print(
            f"[info]Multi-threaded HLS Downloader ({self.max_workers} workers): "
            f"{m3u8_url[:80]}[/info]"
        )

        try:
            res = self.http.get(m3u8_url, referer=referer)
            if res.status_code != 200 or not res.text:
                console.print(f"[warning]HLS manifest HTTP {res.status_code}[/warning]")
                return False

            lines = res.text.splitlines()
            seg_urls = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith("#"):
                    seg_urls.append(urljoin(m3u8_url, line))

            if not seg_urls:
                console.print("[warning]No HLS fragments found in playlist[/warning]")
                return False

            console.print(f"[info]Downloading {len(seg_urls)} fragments in parallel...[/info]")
            temp_ts_path = dest_path + ".parallel.ts"
            os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)

            with tempfile.TemporaryDirectory() as temp_dir:
                frag_files = [None] * len(seg_urls)

                def download_fragment(idx: int, frag_url: str) -> bool:
                    frag_file = os.path.join(temp_dir, f"seg_{idx:05d}.ts")
                    for attempt in range(5):
                        try:
                            if attempt > 0:
                                import time

                                time.sleep(0.2 * attempt)
                            f_res = self.http.get(
                                frag_url, referer=referer, retries=2, delay=0.5, rate_limit=False
                            )
                            if f_res.status_code == 200 and f_res.content:
                                with open(frag_file, "wb") as f:
                                    f.write(f_res.content)
                                frag_files[idx] = frag_file
                                return True
                        except Exception:
                            pass
                    return False

                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = [
                        executor.submit(download_fragment, idx, url)
                        for idx, url in enumerate(seg_urls)
                    ]
                    for future in as_completed(futures):
                        if not future.result():
                            console.print(
                                "[warning]Fragment download failed after retries[/warning]"
                            )

                # Concatenate all downloaded fragments in exact sequential order
                with open(temp_ts_path, "wb", buffering=1024 * 1024) as outfile:
                    for frag_file in frag_files:
                        if frag_file and os.path.exists(frag_file):
                            with open(frag_file, "rb", buffering=256 * 1024) as infile:
                                while chunk := infile.read(256 * 1024):
                                    outfile.write(chunk)

            if not os.path.exists(temp_ts_path) or os.path.getsize(temp_ts_path) == 0:
                console.print("[error]Parallel HLS segment assembly empty[/error]")
                return False

            # Remux TS to MP4 using local/system ffmpeg
            ffmpeg_path = get_local_tool_path("ffmpeg") or "ffmpeg"
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

            if remux_res.returncode == 0 and os.path.exists(dest_path):
                console.print(f"[success]Parallel HLS download complete: {dest_path}[/success]")
                return True
            else:
                if os.path.exists(dest_path):
                    os.remove(dest_path)
                return False

        except Exception as e:
            console.print(f"[warning]Multi-threaded HLS Downloader error: {e}[/warning]")
            return False
