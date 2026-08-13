from downloader.anikoto import AnikotoExtractor


class MockHttpClient:
    pass


def test_select_best_subtitle_spanish() -> None:
    """Verify Spanish subtitle selection and prioritization."""
    extractor = AnikotoExtractor(MockHttpClient())

    tracks = [
        {
            "url": "http://example.com/pt.vtt",
            "label": "Portuguese (Brazilian CR)",
            "lang": "en",
        },
        {
            "url": "http://example.com/es_la.vtt",
            "label": "Spanish (Latin America CR)",
            "lang": "en",
        },
        {"url": "http://example.com/es.vtt", "label": "Spanish (CR)", "lang": "en"},
    ]

    # Selecting Spanish should prioritize Latin American Spanish and ignore Portuguese
    res = extractor._select_best_subtitle(tracks, "es", "http://referer.com")
    assert len(res) == 1
    assert res[0]["label"] == "Spanish (Latin America CR)"
    assert res[0]["url"] == "http://example.com/es_la.vtt"


def test_select_best_subtitle_spanish_spain() -> None:
    """Verify standard Spanish and CR priority order."""
    extractor = AnikotoExtractor(MockHttpClient())

    tracks = [
        {"url": "http://example.com/es_sp.vtt", "label": "Spanish (Spain)", "lang": "en"},
        {"url": "http://example.com/es_cr.vtt", "label": "Spanish (CR)", "lang": "en"},
    ]

    # Priority: CR (1) > Spain (2)
    res = extractor._select_best_subtitle(tracks, "Spanish", "http://referer.com")
    assert len(res) == 1
    assert res[0]["label"] == "Spanish (CR)"
