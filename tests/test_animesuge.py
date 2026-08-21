from downloader.animesuge import AnimeSugeExtractor, generate_vrf, rc4_crypt
from downloader.extractor import get_extractor_for_url
from downloader.utils import HttpClient


def test_animesuge_match() -> None:
    client = HttpClient()
    extractor = AnimeSugeExtractor(client)
    url = "https://animesuge.cz/anime/world-is-dancing-wt8rp/ep-4"
    assert extractor.match(url) is True
    assert extractor.match("https://anikototv.to/anime/test") is False
    assert extractor.match("https://all-wish.me/watch/test") is False


def test_get_extractor_for_animesuge() -> None:
    client = HttpClient()
    url = "https://animesuge.cz/anime/world-is-dancing-wt8rp/ep-4"
    extractor = get_extractor_for_url(url, client)
    assert extractor is not None
    assert isinstance(extractor, AnimeSugeExtractor)


def test_animesuge_vrf_and_rc4() -> None:
    data = b"8821"
    key = "simple-hash"
    encrypted = rc4_crypt(key, data)
    decrypted = rc4_crypt(key, encrypted)
    assert decrypted == data

    vrf = generate_vrf("8821")
    assert isinstance(vrf, str)
    assert len(vrf) > 0


def test_animesuge_live_resolving() -> None:
    """Live integration test resolving World Is Dancing Ep 4 on animesuge.cz."""
    client = HttpClient()
    extractor = AnimeSugeExtractor(client)
    url = "https://animesuge.cz/anime/world-is-dancing-wt8rp/ep-4"

    details = extractor.get_anime_details(url)
    assert "World Is Dancing" in details["title"]
    assert len(details["episodes"]) > 0

    ep4 = None
    for ep in details["episodes"]:
        if ep["num"] == "4" or ep["slug"] == "4":
            ep4 = ep
            break
    assert ep4 is not None

    servers = extractor.get_episode_servers(ep4)
    assert len(servers) > 0

    ep_data = extractor.get_episode_data(ep4, lang="english")
    assert ep_data["video_url"] is not None
    assert ".m3u8" in ep_data["video_url"] or ".mp4" in ep_data["video_url"]

    from downloader.utils import get_safe_referer

    # Verify stream returns HTTP 200
    safe_ref = get_safe_referer(ep_data.get("player_url") or url)
    parsed = extractor.http.get(
        ep_data["video_url"],
        referer=safe_ref,
        headers={"Origin": "https://megaplay.buzz"},
    )
    assert parsed.status_code == 200
