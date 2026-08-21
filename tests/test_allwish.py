from downloader.allwish import AllWishExtractor, generate_vrf, rc4_crypt
from downloader.extractor import get_extractor_for_url
from downloader.utils import HttpClient


def test_allwish_match() -> None:
    client = HttpClient()
    extractor = AllWishExtractor(client)
    url = "https://all-wish.me/watch/world-is-dancing-mof9c/ep-8"
    assert extractor.match(url) is True
    assert extractor.match("https://anikototv.to/anime/test") is False
    assert extractor.match("https://animesuge.cz/anime/test") is False


def test_get_extractor_for_allwish() -> None:
    client = HttpClient()
    url = "https://all-wish.me/watch/world-is-dancing-mof9c/ep-8"
    extractor = get_extractor_for_url(url, client)
    assert extractor is not None
    assert isinstance(extractor, AllWishExtractor)


def test_allwish_vrf_and_rc4() -> None:
    # Test RC4 symmetry
    data = b"8801"
    key = "simple-hash"
    encrypted = rc4_crypt(key, data)
    decrypted = rc4_crypt(key, encrypted)
    assert decrypted == data

    # Test VRF output
    vrf = generate_vrf("8801")
    assert isinstance(vrf, str)
    assert len(vrf) > 0


def test_allwish_subtitle_selection() -> None:
    client = HttpClient()
    extractor = AllWishExtractor(client)

    tracks = [
        {"file": "http://example.com/es.vtt", "label": "Spanish", "lang": "es"},
        {"file": "http://example.com/en_cr.vtt", "label": "English (CR)", "lang": "en"},
        {"file": "http://example.com/en.vtt", "label": "English", "lang": "en"},
    ]

    all_subs = extractor._find_subtitles({"tracks": tracks})
    assert len(all_subs) == 3

    # English selection should prioritize English (CR)
    best_en = extractor._select_best_subtitle(all_subs, "en", "http://referer.com")
    assert len(best_en) == 1
    assert best_en[0]["label"] == "English (CR)"

    # Spanish selection
    best_es = extractor._select_best_subtitle(all_subs, "es", "http://referer.com")
    assert len(best_es) == 1
    assert best_es[0]["label"] == "Spanish"


def test_allwish_live_resolving() -> None:
    """Live integration test resolving World Is Dancing Ep 8 on all-wish.me."""
    client = HttpClient()
    extractor = AllWishExtractor(client)
    url = "https://all-wish.me/watch/world-is-dancing-mof9c/ep-8"

    details = extractor.get_anime_details(url)
    assert "World Is Dancing" in details["title"]
    assert len(details["episodes"]) > 0

    ep8 = None
    for ep in details["episodes"]:
        if ep["num"] == "8" or ep["slug"] == "8":
            ep8 = ep
            break
    assert ep8 is not None

    servers = extractor.get_episode_servers(ep8)
    assert len(servers) > 0

    ep_data = extractor.get_episode_data(ep8, lang="english")
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
