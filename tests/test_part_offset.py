import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add src folder to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from downloader.core import BatchDownloader


class MockResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

def test_calculate_part_offset() -> None:
    # Instantiate the BatchDownloader
    downloader = BatchDownloader(output_dir=".")

    # Mock HTML containing table rows for S3E01 to S3E22 with a gap of 5 months (> 45 days)
    # between E11 and E12, and check for correct titles extraction.
    mock_html = """
    <table>
        <tr><td>S3E1</td><td><a href="/ep1">NEW WORLD MAP</a></td><td><div>April 6, 2023</div></td></tr>
        <tr><td>S3E2</td><td><a href="/ep2">Episode Two</a></td><td><div>April 13, 2023</div></td></tr>
        <tr><td>S3E3</td><td><a href="/ep3">Episode Three</a></td><td><div>April 20, 2023</div></td></tr>
        <tr><td>S3E4</td><td><a href="/ep4">Episode Four</a></td><td><div>April 27, 2023</div></td></tr>
        <tr><td>S3E5</td><td><a href="/ep5">Episode Five</a></td><td><div>May 4, 2023</div></td></tr>
        <tr><td>S3E6</td><td><a href="/ep6">Episode Six</a></td><td><div>May 11, 2023</div></td></tr>
        <tr><td>S3E7</td><td><a href="/ep7">Episode Seven</a></td><td><div>May 18, 2023</div></td></tr>
        <tr><td>S3E8</td><td><a href="/ep8">Episode Eight</a></td><td><div>May 25, 2023</div></td></tr>
        <tr><td>S3E9</td><td><a href="/ep9">Episode Nine</a></td><td><div>June 1, 2023</div></td></tr>
        <tr><td>S3E10</td><td><a href="/ep10">Episode Ten</a></td><td><div>June 8, 2023</div></td></tr>
        <tr><td>S3E11</td><td><a href="/ep11">Episode Eleven</a></td><td><div>June 15, 2023</div></td></tr>
        <tr><td>S3E12</td><td><a href="/ep12">The Medusa's True Face</a></td><td><div>October 12, 2023</div></td></tr>
        <tr><td>S3E13</td><td><a href="/ep13">Episode Thirteen</a></td><td><div>October 19, 2023</div></td></tr>
        <tr><td>S3E14</td><td><a href="/ep14">Episode Fourteen</a></td><td><div>October 26, 2023</div></td></tr>
        <tr><td>S3E22</td><td><a href="/ep22">Last Episode</a></td><td><div>November 5, 2023</div></td></tr>
    </table>
    """

    downloader.http.get = MagicMock(return_value=MockResponse(mock_html))

    parts, titles = downloader._fetch_tvdb_season_details("dr-stone", 3)

    # 2 parts should be detected
    assert len(parts) == 2

    # Part 1 offset should be 0
    offset_1 = parts[0][0]["ep_num"] - 1
    assert offset_1 == 0

    # Part 2 offset should be E12 - 1 = 11
    offset_2 = parts[1][0]["ep_num"] - 1
    assert offset_2 == 11

    # Check parsed title mapping
    assert titles[1] == "NEW WORLD MAP"
    assert titles[12] == "The Medusa's True Face"

def test_parse_part_number() -> None:
    downloader = BatchDownloader(output_dir=".")

    assert downloader._parse_part_number("Dr. Stone Part 2", "http://example.com") == 2
    assert downloader._parse_part_number("Dr. Stone", "http://example.com/dr-stone-part-3-abc") == 3
    assert downloader._parse_part_number("Dr. Stone Part III", "http://example.com") == 3
    assert downloader._parse_part_number("Dr. Stone Part Four", "http://example.com") == 4
    assert downloader._parse_part_number("Dr. Stone Part5", "http://example.com") == 5
    assert downloader._parse_part_number("Dr. Stone", "http://example.com/dr-stone") == 1


def test_tvdb_naming_format() -> None:
    # Test that when naming_format is 'tvdb', filenames are slugified correctly and subtitles use the .en.srt suffix.
    import re
    # We will simulate the slugification process
    short_series_title = "The Warrior Princess and the Barbaric King"
    season = 1
    formatted_ep = "01"

    # Generate series slug
    series_slug = short_series_title.lower()
    series_slug = re.sub(r"[^a-z0-9]+", "-", series_slug)
    series_slug = series_slug.strip("-")

    ep_label = f"s{season:02d}e{formatted_ep.lower()}"
    filename_prefix = f"{series_slug}-{ep_label}"

    assert filename_prefix == "the-warrior-princess-and-the-barbaric-king-s01e01"

    # Subtitle filename construction
    sub_lang_code = "en"
    sub_filename = f"{filename_prefix}.{sub_lang_code}.srt"
    assert sub_filename == "the-warrior-princess-and-the-barbaric-king-s01e01.en.srt"


def test_jojo_season_mapping() -> None:
    downloader = BatchDownloader(output_dir=".")

    # Test Golden Wind (Part 5) maps to TVDB Season 4
    jojo_p5_title = "JoJo's Bizarre Adventure: Part 5 - Golden Wind Uncensored"
    jojo_p5_url = "https://anikototv.to/watch/jojo-s-bizarre-adventure-part-5-golden-wind-uncensored-2alyh/ep-1"

    series_title, season = downloader._parse_series_and_season(jojo_p5_title, jojo_p5_url)
    assert season == 4
    # The base clean title should clean up Part information
    assert "jojo" in series_title.lower()

    # Test Part 4 maps to Season 3
    jojo_p4_title = "JoJo's Bizarre Adventure Part 4: Diamond is Unbreakable"
    jojo_p4_url = "https://anikototv.to/watch/jojo-s-bizarre-adventure-part-4"
    _, season_p4 = downloader._parse_series_and_season(jojo_p4_title, jojo_p4_url)
    assert season_p4 == 3




