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


def test_select_best_subtitle_lat_vs_esp() -> None:
    """Verify Spanish (- Spanish[LAT]) is preferred over Spanish (- Spanish[ESP])."""
    extractor = AnikotoExtractor(MockHttpClient())

    tracks = [
        {
            "url": "http://example.com/es_esp.vtt",
            "label": "Spanish (- Spanish[ESP])",
            "lang": "en",
        },
        {
            "url": "http://example.com/es_lat.vtt",
            "label": "Spanish (- Spanish[LAT])",
            "lang": "en",
        },
    ]

    # When "es" is requested, Spanish[LAT] should be selected and Spanish[ESP] skipped
    res = extractor._select_best_subtitle(tracks, "es", "http://referer.com")
    assert len(res) == 1
    assert res[0]["label"] == "Spanish (- Spanish[LAT])"
    assert res[0]["url"] == "http://example.com/es_lat.vtt"

    # When only Spanish[ESP] is available and "es" is requested, it should be skipped
    tracks_only_esp = [
        {
            "url": "http://example.com/es_esp.vtt",
            "label": "Spanish (- Spanish[ESP])",
            "lang": "en",
        },
    ]
    res_esp = extractor._select_best_subtitle(tracks_only_esp, "es", "http://referer.com")
    assert len(res_esp) == 0

    # When "es-es" is explicitly requested, Spanish[ESP] should be matched
    res_explicit_esp = extractor._select_best_subtitle(
        tracks_only_esp, "es-es", "http://referer.com"
    )
    assert len(res_explicit_esp) == 1
    assert res_explicit_esp[0]["label"] == "Spanish (- Spanish[ESP])"


def test_select_best_subtitle_espanol_la() -> None:
    """Verify Spanish (- Español (LA)) is recognized as Latin American Spanish."""
    extractor = AnikotoExtractor(MockHttpClient())

    tracks = [
        {
            "url": "http://example.com/es_la.vtt",
            "label": "Spanish (- Español (LA))",
            "lang": "en",
        },
        {
            "url": "http://example.com/es_esp.vtt",
            "label": "Spanish (- Español (ES))",
            "lang": "en",
        },
    ]

    res = extractor._select_best_subtitle(tracks, "es", "http://referer.com")
    assert len(res) == 1
    assert res[0]["label"] == "Spanish (- Español (LA))"
    assert res[0]["url"] == "http://example.com/es_la.vtt"


def test_resolve_sub_lang_tag_es_la() -> None:
    """Verify resolve_sub_lang_tag resolves Spanish (Latin America) to es-LA."""
    from downloader.core import resolve_sub_lang_tag

    assert resolve_sub_lang_tag("Spanish (Latin America CR)", "es") == "es-LA"
    assert resolve_sub_lang_tag("Spanish (- Spanish[LAT])", "es") == "es-LA"
    assert resolve_sub_lang_tag("Spanish (- Español (LA))", "es") == "es-LA"
    assert resolve_sub_lang_tag("Spanish (- Spanish[ESP])", "es") == "es-ES"
    assert resolve_sub_lang_tag("Spanish (- Español (ES))", "es") == "es-ES"
    assert resolve_sub_lang_tag("Spanish (Spain)", "es") == "es-ES"
    assert resolve_sub_lang_tag("Spanish", "es") == "es"
    assert resolve_sub_lang_tag("", "es-la") == "es-LA"
    assert resolve_sub_lang_tag("", "es-es") == "es-ES"


def test_get_target_lang_candidate_tags() -> None:
    """Verify get_target_lang_candidate_tags isolates tags per requested language."""
    from downloader.core import get_target_lang_candidate_tags

    # Spanish (Latin America / general) should only match Spanish tags, not English
    es_tags = get_target_lang_candidate_tags("es")
    assert "es-LA" in es_tags
    assert "en" not in es_tags
    assert "vi" not in es_tags

    # English should only match English tags
    en_tags = get_target_lang_candidate_tags("en")
    assert "en" in en_tags
    assert "es-LA" not in en_tags


def test_classify_spanish_variant() -> None:
    """Verify classify_spanish_variant accurately categorizes Spanish variants."""
    from downloader.utils import classify_spanish_variant

    # Latin American variants -> es-LA
    assert classify_spanish_variant("Spanish (- Español (LA))") == "es-LA"
    assert classify_spanish_variant("Spanish (- Spanish[LAT])") == "es-LA"
    assert classify_spanish_variant("Spanish (Latin America CR)") == "es-LA"
    assert classify_spanish_variant("Spanish (Latam)") == "es-LA"
    assert classify_spanish_variant("Español (Latinoamérica)") == "es-LA"
    assert classify_spanish_variant("Spanish [ES-419]") == "es-LA"
    assert classify_spanish_variant("Spanish (LA)") == "es-LA"
    assert classify_spanish_variant("", "es-la") == "es-LA"
    assert classify_spanish_variant("", "es-419") == "es-LA"

    # Spain / European variants -> es-ES
    assert classify_spanish_variant("Spanish (- Español (ES))") == "es-ES"
    assert classify_spanish_variant("Spanish (- Spanish[ESP])") == "es-ES"
    assert classify_spanish_variant("Spanish (Spain)") == "es-ES"
    assert classify_spanish_variant("Castellano") == "es-ES"
    assert classify_spanish_variant("", "es-es") == "es-ES"

    # Neutral / General -> es
    assert classify_spanish_variant("Spanish") == "es"
    assert classify_spanish_variant("Spanish (CR)") == "es"
    assert classify_spanish_variant("Español") == "es"

    # Non-Spanish -> None
    assert classify_spanish_variant("Portuguese (Brazilian)") is None
    assert classify_spanish_variant("English (US)") is None
    assert classify_spanish_variant("Vietnamese") is None
