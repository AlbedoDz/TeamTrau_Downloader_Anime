from downloader.allwish import AllWishExtractor
from downloader.anikoto import AnikotoExtractor
from downloader.animecube import AnimeCubeExtractor
from downloader.animesuge import AnimeSugeExtractor
from downloader.core import BatchDownloader
from downloader.extractor import BaseExtractor, get_extractor_for_url, register_extractor
from downloader.utils import HttpClient

__all__ = [
    "AllWishExtractor",
    "AnikotoExtractor",
    "AnimeCubeExtractor",
    "AnimeSugeExtractor",
    "BaseExtractor",
    "BatchDownloader",
    "HttpClient",
    "get_extractor_for_url",
    "register_extractor",
]
