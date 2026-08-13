"""Playwright Headless Browser Network Traffic Sniffer module for capturing m3u8/subtitles."""

import re
import time

from downloader.utils import console


class BrowserNetworkSniffer:
    """Headless browser network sniffer to capture streaming video and subtitle URLs."""

    def __init__(self, headless: bool = True, timeout_sec: float = 30.0):
        self.headless = headless
        self.timeout_sec = timeout_sec

    def sniff_stream_urls(self, url: str) -> dict:
        """Launch headless browser, load page, and intercept media/subtitle network responses."""
        captured = {
            "video_url": None,
            "subtitles": [],
            "headers": {},
        }

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            console.print(
                "[warning]Playwright is not installed. Browser sniffer unavailable.[/warning]",
                style="yellow",
            )
            return captured

        console.print(
            f"[info]Launching Browser Sniffer (Headless={self.headless}) for: {url}[/info]"
        )

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 720},
            )
            page = context.new_page()

            def handle_response(response):
                try:
                    res_url = response.url
                    headers = response.request.headers

                    # Detect video m3u8/mp4 streams
                    if not captured["video_url"]:
                        if ".m3u8" in res_url or ".mp4" in res_url or "master.m3u8" in res_url:
                            if "ad_url" not in res_url and "vmap" not in res_url:
                                captured["video_url"] = res_url
                                captured["headers"] = {
                                    "User-Agent": headers.get("user-agent", ""),
                                    "Referer": headers.get("referer", url),
                                    "Origin": headers.get("origin", ""),
                                }
                                console.print(
                                    f"[success]Captured video stream: {res_url[:75]}[/success]"
                                )

                    # Detect VTT/SRT subtitles
                    if ".vtt" in res_url or ".srt" in res_url or "subtitle" in res_url:
                        if not any(s["url"] == res_url for s in captured["subtitles"]):
                            lang = "en"
                            m_lang = re.search(r"\b(en|vi|es|fr|de|ja)\b", res_url.lower())
                            if m_lang:
                                lang = m_lang.group(1)
                            captured["subtitles"].append(
                                {
                                    "url": res_url,
                                    "label": f"Language ({lang})",
                                    "lang": lang,
                                    "referer": url,
                                }
                            )
                            console.print(
                                f"[success]Sniffer captured subtitle: {res_url[:80]}[/success]"
                            )
                except Exception:
                    pass

            page.on("response", handle_response)

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_sec * 1000)
                # Wait for player initialization
                time.sleep(4.0)

                # Try clicking play button if present
                play_btn = page.query_selector("button.play-btn, .vjs-big-play-button, #player")
                if play_btn:
                    try:
                        play_btn.click()
                        time.sleep(3.0)
                    except Exception:
                        pass
            except Exception as e:
                console.print(
                    f"[warning]Browser navigation timeout or notice: {e}[/warning]",
                    style="yellow",
                )

            browser.close()

        return captured
