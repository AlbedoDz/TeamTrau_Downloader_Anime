"""Unit tests for BrowserNetworkSniffer and MultiThreadedHLSDownloader modules."""

from downloader.browser_sniffer import BrowserNetworkSniffer
from downloader.hls_downloader import MultiThreadedHLSDownloader
from downloader.utils import HttpClient


def test_browser_sniffer_init():
    sniffer = BrowserNetworkSniffer(headless=True, timeout_sec=15.0)
    assert sniffer.headless is True
    assert sniffer.timeout_sec == 15.0


def test_hls_downloader_init():
    http = HttpClient()
    downloader = MultiThreadedHLSDownloader(http_client=http, max_workers=8)
    assert downloader.max_workers == 8
