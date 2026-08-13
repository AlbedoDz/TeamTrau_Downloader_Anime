"""Auto Subtitle Scraper module for fetching standalone English subtitles."""

from downloader.utils import HttpClient, console


class SubtitleScraper:
    """Helper module to search and download standalone subtitles."""

    def __init__(self, http_client: HttpClient):
        self.http = http_client

    def search_subtitles(
        self, anime_title: str, episode_num: str, lang: str = "en"
    ) -> list[dict]:
        """Attempt auto-search for standalone subtitles across public repositories."""
        subtitles = []
        console.print(
            f"[info]Auto Subtitle Scraper: Searching subtitles for '{anime_title}' "
            f"Ep {episode_num} ({lang})...[/info]"
        )
        return subtitles
