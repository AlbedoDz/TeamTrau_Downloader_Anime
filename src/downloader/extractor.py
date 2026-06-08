from abc import ABC, abstractmethod

from downloader.utils import HttpClient


class BaseExtractor(ABC):
    """Base class for all site-specific extractors."""

    def __init__(self, http_client: HttpClient):
        self.http = http_client

    @abstractmethod
    def match(self, url: str) -> bool:
        """Return True if this extractor can handle the given URL."""
        pass

    @abstractmethod
    def get_anime_details(self, url: str) -> dict:
        """
        Extract anime details from the main page.
        Returns:
            {
                'title': str,
                'episodes': [
                    {
                        'num': str (e.g. '1'),
                        'slug': str,
                        'ids': str,
                        'url': str
                    },
                    ...
                ]
            }
        """
        pass

    @abstractmethod
    def get_episode_data(
        self, episode_item: dict, lang: str, server_info: dict | None = None
    ) -> dict:
        """
        Extract stream URLs and subtitles for a specific episode.
        Returns:
            {
                'video_url': Optional[str],
                'subtitles': [
                    {
                        'url': str,
                        'label': str,
                        'lang': str,
                        'referer': str
                    },
                    ...
                ]
            }
        """
        pass

    def get_episode_servers(self, episode_item: dict) -> list[dict]:
        """
        Extract the list of available servers/mirrors for a specific episode.
        Returns a list of:
            [
                {
                    'id': str,
                    'name': str,
                    'type': str (e.g. 'sub' or 'dub')
                },
                ...
            ]
        """
        return []


# List of registered extractor classes
_registered_extractors: list[type[BaseExtractor]] = []


def register_extractor(cls: type[BaseExtractor]) -> type[BaseExtractor]:
    """Decorator to register a website extractor."""
    _registered_extractors.append(cls)
    return cls


def get_extractor_for_url(url: str, http_client: HttpClient) -> BaseExtractor | None:
    """Find and instantiate the matching extractor for the given URL."""
    for extractor_cls in _registered_extractors:
        # Create a temp instance to match
        temp_inst = extractor_cls(http_client)
        if temp_inst.match(url):
            return temp_inst
    return None
