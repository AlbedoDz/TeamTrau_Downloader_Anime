from downloader.animecube import AnimeCubeExtractor
from downloader.extractor import get_extractor_for_url
from downloader.utils import HttpClient


def test_animecube_match():
    client = HttpClient()
    extractor = AnimeCubeExtractor(client)
    url = (
        "https://animecube.live/anime/the-demon-hunter"
        "?from=home&season=tab-1&episode=the-demon-hunter-tab-1-ep-1"
    )
    assert extractor.match(url) is True
    assert extractor.match("https://anikototv.to/anime/test") is False


def test_get_extractor_for_animecube():
    client = HttpClient()
    url = "https://animecube.live/anime/the-demon-hunter"
    extractor = get_extractor_for_url(url, client)
    assert extractor is not None
    assert isinstance(extractor, AnimeCubeExtractor)


def test_animecube_details_and_episode_data():
    client = HttpClient()
    extractor = AnimeCubeExtractor(client)
    url = (
        "https://animecube.live/anime/the-demon-hunter"
        "?from=home&season=tab-1&episode=the-demon-hunter-tab-1-ep-1"
    )

    details = extractor.get_anime_details(url)
    assert details["title"] == "The Demon Hunter"
    assert len(details["episodes"]) > 0

    ep1 = details["episodes"][0]
    assert ep1["num"] == "1"
    assert "the-demon-hunter" in ep1["slug"]

    ep_data = extractor.get_episode_data(ep1, lang="english")
    assert "video_url" in ep_data
    assert "subtitles" in ep_data
    if ep_data["video_url"]:
        assert "dailymotion.com" in ep_data["video_url"] or "http" in ep_data["video_url"]
