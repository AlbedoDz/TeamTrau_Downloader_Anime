from downloader.core import parse_episode_range
from downloader.utils import clean_filename, vtt_to_srt


def test_clean_filename():
    """Verify that file name sanitization behaves correctly."""
    assert clean_filename("Kono Subarashii Sekai: 3") == "Kono Subarashii Sekai 3"
    assert clean_filename("Anime/Movie? Yes*") == "AnimeMovie Yes"
    assert clean_filename("   Trailing spaces   ") == "Trailing spaces"


def test_vtt_to_srt_conversion():
    """Verify that WebVTT content is parsed and converted to SRT format successfully."""
    vtt_data = """WEBVTT

1
00:01.000 --> 00:03.500
Hello World!

2
00:04.123 --> 00:05.999
<i>This is a subtitle.</i>
"""
    expected_srt = """1
00:00:01,000 --> 00:00:03,500
Hello World!

2
00:00:04,123 --> 00:00:05,999
This is a subtitle."""
    assert vtt_to_srt(vtt_data) == expected_srt


def test_parse_episode_range():
    """Verify that episode ranges parse correctly."""
    episodes = [
        {"num": "1", "slug": "ep-1"},
        {"num": "2", "slug": "ep-2"},
        {"num": "3", "slug": "ep-3"},
        {"num": "4", "slug": "ep-4"},
        {"num": "5", "slug": "ep-5"},
    ]

    # Test range format '1-3'
    res = parse_episode_range("1-3", episodes)
    assert len(res) == 3
    assert [e["num"] for e in res] == ["1", "2", "3"]

    # Test discrete comma separated
    res = parse_episode_range("1,3,5", episodes)
    assert len(res) == 3
    assert [e["num"] for e in res] == ["1", "3", "5"]

    # Test combined format
    res = parse_episode_range("1-2,4", episodes)
    assert len(res) == 3
    assert [e["num"] for e in res] == ["1", "2", "4"]

    # Test 'all' format
    res = parse_episode_range("all", episodes)
    assert len(res) == 5


def test_sonarr_helpers():
    """Verify that series title and episode formatting for Sonarr behave as expected."""
    from downloader.core import BatchDownloader

    downloader = BatchDownloader()

    # 1. Parse Series and Season Title Tests
    title, season = downloader._parse_series_and_season(
        "Rent-a-Girlfriend Season 5",
        "https://anikototv.to/watch/rent-a-girlfriend-season-5-kdefb/ep-3",
    )
    assert title == "Rent-a-Girlfriend"
    assert season == 5

    title, season = downloader._parse_series_and_season(
        "The Warrior Princess and the Barbaric King",
        "https://anikototv.to/watch/the-warrior-princess-and-the-barbaric-king-snxwm/ep-4",
    )
    assert title == "The Warrior Princess and the Barbaric King"
    assert season == 1

    title, season = downloader._parse_series_and_season(
        "Kono Subarashii Sekai S3", "https://anikototv.to/watch/kono-subarashii-sekai-s3/ep-1"
    )
    assert title == "Kono Subarashii Sekai"
    assert season == 3

    # 2. Episode Formatting Tests
    assert downloader._format_episode_num("3") == "03"
    assert downloader._format_episode_num("ep-12") == "12"
    assert downloader._format_episode_num("12-13") == "12-e13"
    assert downloader._format_episode_num("ep-12-13") == "12-e13"


def test_subtitle_selection():
    """Verify that only the single best English subtitle track is selected."""
    from downloader.anikoto import AnikotoExtractor
    from downloader.utils import HttpClient

    extractor = AnikotoExtractor(HttpClient())

    # Test case 1: Multiple language tracks, including English
    tracks = [
        {"url": "http://ar.vtt", "label": "AR", "lang": "en"},
        {"url": "http://de.vtt", "label": "DE", "lang": "en"},
        {"url": "http://en.vtt", "label": "EN", "lang": "en"},
        {"url": "http://vi.vtt", "label": "VI", "lang": "en"},
    ]
    selected = extractor._select_best_subtitle(tracks, "en", "http://referer")
    assert len(selected) == 1
    assert selected[0]["url"] == "http://en.vtt"
    assert selected[0]["label"] == "EN"

    # Test case 2: English CR and English Forced
    tracks_cr = [
        {"url": "http://forced.vtt", "label": "English (Force)", "lang": "en"},
        {"url": "http://cr.vtt", "label": "English (CR)", "lang": "en"},
        {"url": "http://normal.vtt", "label": "English", "lang": "en"},
    ]
    selected_cr = extractor._select_best_subtitle(tracks_cr, "en", "http://referer")
    assert len(selected_cr) == 1
    assert selected_cr[0]["url"] == "http://cr.vtt"

    # Test case 3: English and English Forced (no CR)
    tracks_no_cr = [
        {"url": "http://forced.vtt", "label": "English (Force)", "lang": "en"},
        {"url": "http://normal.vtt", "label": "English", "lang": "en"},
    ]
    selected_no_cr = extractor._select_best_subtitle(tracks_no_cr, "en", "http://referer")
    assert len(selected_no_cr) == 1
    assert selected_no_cr[0]["url"] == "http://normal.vtt"


def test_extract_hashes_from_url():
    """Verify that extract_hashes_from_url correctly parses anime and episode hashes."""
    from downloader.core import extract_hashes_from_url

    url = "https://s2.cinewave2.site/anime/c9041cfd2a40932691855abd98fd219a/4956fbf55f8bf3eda410d1b6c790f2f0/master.m3u8"
    hashes = extract_hashes_from_url(url)
    assert hashes == (
        "c9041cfd2a40932691855abd98fd219a",
        "4956fbf55f8bf3eda410d1b6c790f2f0",
    )

    bad_url = "https://s2.cinewave2.site/anime/short/hashes/master.m3u8"
    assert extract_hashes_from_url(bad_url) is None
    assert extract_hashes_from_url("") is None


def test_shorten_title_safe():
    """Verify that shorten_title_safe behaves correctly under various lengths."""
    from downloader.core import shorten_title_safe

    # Short title should not be modified
    assert shorten_title_safe("Short Title", 40) == "Short Title"

    # Long title should be truncated at word boundary and suffixed with hash
    long_title = "This is an extremely long title that exceeds the limit"
    short_val = shorten_title_safe(long_title, 30)
    assert len(short_val) <= 38
    assert short_val.startswith("This is an extremely long")
    assert "[" in short_val
    assert "]" in short_val
