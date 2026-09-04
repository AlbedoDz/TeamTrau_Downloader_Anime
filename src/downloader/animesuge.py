import base64
import re
import urllib.parse
from typing import TypedDict
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from downloader.extractor import BaseExtractor, register_extractor
from downloader.utils import (
    HttpClient,
    classify_spanish_variant,
    console,
    get_safe_referer,
)


class SubtitleItem(TypedDict):
    url: str
    label: str
    lang: str
    referer: str


class VideoSourceItem(TypedDict):
    url: str
    type: str


class ServerItem(TypedDict):
    id: str
    name: str
    type: str


class EpisodeItem(TypedDict):
    num: str
    slug: str
    ids: str
    clean_text: str
    url: str


class AnimeDetails(TypedDict):
    title: str
    episodes: list[EpisodeItem]
    description: str
    year: int | None


class EpisodeData(TypedDict):
    video_url: str | None
    subtitles: list[SubtitleItem]
    player_url: str | None


def rc4_crypt(key: str, data: bytes) -> bytes:
    """RC4 stream cipher encryption/decryption."""
    s_box = list(range(256))
    j = 0
    out = bytearray()
    key_bytes = key.encode("utf-8")
    for i in range(256):
        j = (j + s_box[i] + key_bytes[i % len(key_bytes)]) % 256
        s_box[i], s_box[j] = s_box[j], s_box[i]
    i = j = 0
    for byte in data:
        i = (i + 1) % 256
        j = (j + s_box[i]) % 256
        s_box[i], s_box[j] = s_box[j], s_box[i]
        out.append(byte ^ s_box[(s_box[i] + s_box[j]) % 256])
    return bytes(out)


def generate_vrf(text: str, key: str = "simple-hash") -> str:
    """Generate VRF token using RC4 encryption and base64 encoding."""
    encrypted = rc4_crypt(key, text.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


@register_extractor
class AnimeSugeExtractor(BaseExtractor):
    """Extractor for animesuge.cz streaming site."""

    def __init__(self, http_client: HttpClient) -> None:
        super().__init__(http_client)
        self.base_url = "https://animesuge.cz/"

    def match(self, url: str) -> bool:
        """Match URLs containing animesuge.cz or animesuge domains."""
        parsed = urlparse(url)
        return "animesuge" in parsed.netloc

    def get_anime_details(self, url: str) -> AnimeDetails:
        """Return anime title and episode list by static fetch and VRF calculation."""
        console.print(f"[info]Fetching anime page: {url}[/info]")

        try:
            res = self.http.get(url)
            if res.status_code != 200:
                console.print(
                    f"[error]Failed to fetch watch page (HTTP {res.status_code})[/error]",
                    style="red",
                )
                return {
                    "title": "Unknown Anime",
                    "episodes": [],
                    "description": "",
                    "year": None,
                }

            soup = BeautifulSoup(res.text, "html.parser")
            h1 = soup.find("h1", class_="title")
            title = h1.text.strip() if h1 else "Unknown Anime"
            console.print(f"[success]Title: {title}[/success]")

            description = ""
            desc_el = soup.select_one(".content")
            if desc_el:
                description = desc_el.text.strip()

            year: int | None = None
            for div in soup.select("div"):
                txt = div.text.strip()
                if txt.startswith("Premiered:") or txt.startswith("Aired:"):
                    m_yr = re.search(r"\b(19\d{2}|20\d{2})\b", txt)
                    if m_yr:
                        year = int(m_yr.group(1))
                        break

            # Extract anime ID from watch-page element or mangaId var
            anime_id: str | None = None
            watch_page = soup.find(id="watch-page")
            if watch_page and watch_page.get("data-id"):
                anime_id = str(watch_page.get("data-id"))

            if not anime_id:
                m_id = re.search(r"mangaId\s*=\s*(\d+)", res.text)
                if m_id:
                    anime_id = m_id.group(1)

            if not anime_id:
                console.print("[error]Could not find anime ID in page source.[/error]", style="red")
                return {
                    "title": title,
                    "episodes": [],
                    "description": description,
                    "year": year,
                }

            vrf = generate_vrf(anime_id)
            quoted_vrf = urllib.parse.quote(vrf)

            # Fetch the dynamic episode list HTML
            ep_list_url = urljoin(self.base_url, f"ajax/episode/list/{anime_id}?vrf={quoted_vrf}")
            headers = {"X-Requested-With": "XMLHttpRequest"}
            console.print("[dim]Fetching dynamic episode list...[/dim]")
            ep_list_json = self.http.get_json(ep_list_url, headers=headers, referer=url)
            episodes_html = ep_list_json.get("result", "")

            # Parse episode elements
            ep_soup = BeautifulSoup(episodes_html, "html.parser")
            els = ep_soup.select("a[data-ids]")
            console.print(f"[dim]Found {len(els)} episode elements.[/dim]")

            episodes: list[EpisodeItem] = []
            seen_slugs: set[str] = set()
            for idx, el in enumerate(els):
                data_ids = el.get("data-ids") or ""
                if not data_ids:
                    continue

                data_slug = el.get("data-slug") or el.get("data-id") or str(idx + 1)
                if data_slug in seen_slugs:
                    continue
                seen_slugs.add(data_slug)

                href = el.get("href") or ""
                ep_url = urljoin(url, href) if href else url
                clean_text = self._clean_ep_text(el.text or "", data_slug)

                episodes.append(
                    {
                        "num": str(data_slug),
                        "slug": str(data_slug),
                        "ids": str(data_ids),
                        "clean_text": clean_text,
                        "url": ep_url,
                    }
                )

        except Exception as e:
            console.print(f"[error]Failed to parse anime details: {e}[/error]", style="red")
            return {
                "title": "Unknown Anime",
                "episodes": [],
                "description": "",
                "year": None,
            }

        console.print(f"[success]Found {len(episodes)} episodes.[/success]")
        return {
            "title": title,
            "episodes": episodes,
            "description": description,
            "year": year,
        }

    def get_episode_servers(self, episode_item: dict) -> list[dict]:
        """Fetch and parse available streaming servers for the episode."""
        ep_url = episode_item["url"]
        ep_ids = episode_item["ids"]
        ep_num = episode_item["num"]

        quoted_ids = urllib.parse.quote(ep_ids)
        servers_list_url = urljoin(self.base_url, f"ajax/server/list?servers={quoted_ids}")
        headers = {"X-Requested-With": "XMLHttpRequest"}

        try:
            servers_json = self.http.get_json(servers_list_url, headers=headers, referer=ep_url)
            servers_html = servers_json.get("result", "")
        except Exception as e:
            console.print(
                f"[error]Failed to fetch server list for Ep {ep_num}: {e}[/error]",
                style="red",
            )
            return []

        soup = BeautifulSoup(servers_html, "html.parser")
        servers: list[dict] = []

        type_divs = soup.select(".servers .type, .server-type")
        if type_divs:
            for div in type_divs:
                t_type = div.get("data-type") or "sub"
                for item in div.select(".server[data-link-id], li[data-link-id]"):
                    link_id = item.get("data-link-id")
                    if not link_id:
                        continue
                    name = item.get_text().strip()
                    servers.append(
                        {
                            "id": link_id,
                            "name": f"{name} ({t_type.upper()})",
                            "type": t_type,
                        }
                    )
        else:
            for item in soup.select(".server[data-link-id], li[data-link-id]"):
                link_id = item.get("data-link-id")
                if not link_id:
                    continue
                name = item.get_text().strip()
                servers.append(
                    {
                        "id": link_id,
                        "name": name,
                        "type": "sub",
                    }
                )
        return servers

    def get_episode_data(
        self, episode_item: dict, lang: str, server_info: dict | None = None
    ) -> dict:
        """Resolve player embed, HLS stream, and subtitles for a specific episode."""
        ep_url = episode_item["url"]
        ep_num = episode_item["num"]

        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }

        if server_info:
            link_id = server_info["id"]
            server_name = server_info["name"]
            console.print(f"[info]Resolving server: {server_name} (ID: {link_id})[/info]")
        else:
            console.print(f"[info]Resolving servers for Ep {ep_num}...[/info]")
            servers = self.get_episode_servers(episode_item)
            if not servers:
                console.print(
                    f"[warning]No servers found for Ep {ep_num}[/warning]",
                    style="yellow",
                )
                return {"video_url": None, "subtitles": [], "player_url": None}

            selected_srv = servers[0]
            for pref in ["HD-1", "Mega", "Vidstream", "MegaCloud", "RapidCloud"]:
                for srv in servers:
                    if pref.lower() in srv["name"].lower():
                        selected_srv = srv
                        break
                if selected_srv != servers[0]:
                    break

            link_id = selected_srv["id"]
            server_name = selected_srv["name"]
            console.print(f"[info]Selected server: {server_name} (ID: {link_id})[/info]")

        # Fetch player embed URL
        player_info_url = urljoin(self.base_url, f"ajax/server?get={link_id}")
        try:
            player_json = self.http.get_json(player_info_url, headers=headers, referer=ep_url)
            player_res = player_json.get("result")
            player_url = None
            if isinstance(player_res, dict):
                player_url = player_res.get("url")
            elif isinstance(player_res, str):
                player_url = player_res
        except Exception as e:
            console.print(
                f"[error]Failed to get player URL for Ep {ep_num}: {e}[/error]",
                style="red",
            )
            return {"video_url": None, "subtitles": [], "player_url": None}

        if not player_url:
            console.print("[warning]Missing player embed URL.[/warning]", style="yellow")
            return {"video_url": None, "subtitles": [], "player_url": None}

        console.print(f"[info]Player embed URL: {player_url}[/info]")

        # Parse player embed page to extract data-id
        real_id: str | None = None
        try:
            embed_res = self.http.get(player_url, referer=ep_url)
            embed_soup = BeautifulSoup(embed_res.text, "html.parser")
            player_div = embed_soup.find(id="megaplay-player") or embed_soup.find(class_="fix-area")
            if player_div and player_div.get("data-id"):
                real_id = str(player_div.get("data-id"))
        except Exception as e:
            console.print(f"[dim]Failed to parse embed page: {e}[/dim]")

        # Build stream sources API endpoint
        parsed = urlparse(player_url)
        if real_id:
            api_url = f"{parsed.scheme}://{parsed.netloc}/stream/getSources?id={real_id}"
            fallback_api_url = (
                f"{parsed.scheme}://{parsed.netloc}/stream/getSourcesNew?id={real_id}&id={real_id}"
            )
        else:
            api_url = self._build_sources_api_url(player_url)
            fallback_api_url = None

        if not api_url:
            console.print("[warning]Could not resolve sources API URL.[/warning]", style="yellow")
            return {"video_url": None, "subtitles": [], "player_url": player_url}

        console.print(f"[info]Fetching player sources: {api_url}[/info]")
        api_headers = {"X-Requested-With": "XMLHttpRequest", "Referer": player_url}
        sources_json: dict = {}
        try:
            sources_json = self.http.get_json(api_url, headers=api_headers)
        except Exception as e:
            if fallback_api_url:
                console.print(
                    f"[warning]Failed to fetch from {api_url}: {e}. Trying fallback...[/warning]",
                    style="yellow",
                )
                try:
                    sources_json = self.http.get_json(fallback_api_url, headers=api_headers)
                except Exception as fe:
                    console.print(
                        f"[error]Failed to fetch stream sources (fallback): {fe}[/error]",
                        style="red",
                    )
                    return {"video_url": None, "subtitles": [], "player_url": player_url}
            else:
                console.print(f"[error]Failed to fetch stream sources: {e}[/error]", style="red")
                return {"video_url": None, "subtitles": [], "player_url": player_url}

        # Parse subtitles and video sources
        all_tracks = self._find_subtitles(sources_json)
        all_videos = self._find_video_sources(sources_json)

        matched_subs = self._select_best_subtitle(all_tracks, lang, player_url)

        if not matched_subs and all_tracks:
            avail_langs = sorted(list({t.get("label", t.get("lang", "unknown")) for t in all_tracks if t.get("label") or t.get("lang")}))
            console.print(
                f"[warning]Ep {ep_num}: Subtitle for requested language '{lang}' not available. Skipping subtitle download. (Available tracks: {', '.join(avail_langs)})[/warning]",
                style="yellow",
            )

        video_url: str | None = None
        if all_videos:
            hls = [v for v in all_videos if v.get("type") == "hls"]
            if hls:
                video_url = self._get_720p_playlist_url(hls[0]["url"], player_url)
            else:
                video_url = all_videos[0].get("url")

        console.print(
            f"[success]Ep {ep_num}: video={'yes' if video_url else 'no'}, "
            f"subtitles={len(matched_subs)}[/success]"
        )
        return {
            "video_url": video_url,
            "subtitles": matched_subs,
            "player_url": player_url,
        }

    def _clean_ep_text(self, raw: str, ep_num: str) -> str:
        """Strip badges, episode numbers and status text."""
        text = re.sub(r"\s+", " ", raw).strip()
        text = re.sub(
            r"(EN \(\d+\)|No Sub|Error|Scanning\.\.\.)$", "", text, flags=re.IGNORECASE
        ).strip()
        try:
            n = int(re.search(r"\d+", ep_num).group(0)) if re.search(r"\d+", ep_num) else None
            if n is not None:
                text = re.sub(
                    rf"^(?:episode?\.?[\s\-:]*)?\b0*{n}\b[\s\-:]*", "", text, flags=re.IGNORECASE
                ).strip()
        except Exception:
            pass
        return text

    def _build_sources_api_url(self, player_url: str) -> str | None:
        """Convert a player embed URL into a getSources API endpoint."""
        parsed = urlparse(player_url)
        path = parsed.path

        m = re.search(r"/stream/s-\d+/(\d+)", path)
        if m:
            return f"{parsed.scheme}://{parsed.netloc}/stream/getSources?id={m.group(1)}"

        if "getSources" in path or "sources" in path:
            return player_url

        m = re.search(r"(/embed-[^/]+/e-[^/]+/)([^/?#]+)", path)
        if m:
            return f"{parsed.scheme}://{parsed.netloc}{m.group(1)}getSources?id={m.group(2)}"

        return None

    def _find_subtitles(self, obj: object) -> list[dict]:
        """Recursively find subtitle track objects in an API response."""
        tracks: list[dict] = []
        if not obj or not isinstance(obj, (dict, list)):
            return tracks
        if isinstance(obj, list):
            for item in obj:
                tracks.extend(self._find_subtitles(item))
            return tracks
        for k, v in obj.items():
            k_lower = k.lower()
            if k_lower in ("tracks", "subtitles", "subs", "captions") and isinstance(v, list):
                for t in v:
                    if isinstance(t, dict):
                        u = t.get("file") or t.get("url") or t.get("src")
                        if u and isinstance(u, str):
                            tracks.append(
                                {
                                    "url": u,
                                    "label": str(
                                        t.get("label")
                                        or t.get("name")
                                        or t.get("language")
                                        or "Sub"
                                    ),
                                    "lang": str(t.get("lang") or t.get("language") or "en"),
                                }
                            )
            elif isinstance(v, str) and (
                v.endswith(".vtt") or v.endswith(".srt") or "lostproject.club" in v
            ):
                if v.startswith("http"):
                    lbl = "Sub"
                    if obj.get("label") or obj.get("name") or obj.get("language"):
                        lbl = str(obj.get("label") or obj.get("name") or obj.get("language"))
                    else:
                        m = re.search(r"/([a-zA-Z0-9_-]+)\.(vtt|srt)", v)
                        if m:
                            lbl = m.group(1).upper()
                    tracks.append({"url": v, "label": lbl, "lang": lbl.lower()})
            elif isinstance(v, (dict, list)):
                tracks.extend(self._find_subtitles(v))
        return tracks

    def _find_video_sources(self, obj: object) -> list[dict]:
        """Recursively find video stream URLs in an API response."""
        vids: list[dict] = []
        if not obj or not isinstance(obj, (dict, list)):
            return vids
        if isinstance(obj, list):
            for item in obj:
                vids.extend(self._find_video_sources(item))
            return vids
        for k, v in obj.items():
            k_lower = k.lower()
            if k_lower == "sources" and isinstance(v, list):
                for s in v:
                    if isinstance(s, dict):
                        u = s.get("file") or s.get("url") or s.get("src")
                        if u and isinstance(u, str):
                            vids.append(
                                {
                                    "url": u,
                                    "type": str(
                                        s.get("type") or ("hls" if ".m3u8" in u else "mp4")
                                    ),
                                }
                            )
            elif isinstance(v, str) and (".m3u8" in v or ".mp4" in v):
                if v.startswith("http"):
                    vids.append({"url": v, "type": "hls" if ".m3u8" in v else "mp4"})
            elif isinstance(v, (dict, list)):
                vids.extend(self._find_video_sources(v))
        return vids

    def _select_best_subtitle(
        self, tracks: list[dict], target_lang: str, referer: str
    ) -> list[SubtitleItem]:
        """Filter tracks by language and return the best matching subtitle track."""
        target_lower = target_lang.lower()
        matched: list[dict] = []

        for t in tracks:
            lbl = str(t.get("label", "")).strip().lower()
            code = str(t.get("lang", "")).strip().lower()

            if target_lower in ("en", "eng", "english"):
                non_english_indicators = [
                    "vietnamese",
                    "tieng viet",
                    "vi",
                    "spanish",
                    "espanol",
                    "es",
                    "french",
                    "francais",
                    "fr",
                    "german",
                    "deutsch",
                    "de",
                    "italian",
                    "italiano",
                    "it",
                    "portuguese",
                    "portugues",
                    "pt",
                    "arabic",
                    "ar",
                    "turkish",
                    "tr",
                    "russian",
                    "ru",
                    "chinese",
                    "zh",
                    "ch",
                    "indonesian",
                    "id",
                    "thai",
                    "th",
                    "korean",
                    "ko",
                    "japanese",
                    "ja",
                    "malay",
                    "ms",
                    "ma",
                    "tagalog",
                    "tl",
                    "hindi",
                    "hi",
                ]
                if lbl in non_english_indicators or code in non_english_indicators:
                    continue
                if any(len(ind) > 2 and ind in lbl for ind in non_english_indicators):
                    continue

                english_keywords = ["english", "eng", "en", "forced", "force", "cr"]
                if (
                    lbl in english_keywords
                    or code in english_keywords
                    or any(kw in lbl for kw in ["english", "forced", "force", "cr"])
                    or lbl in ("sub", "srt", "vtt")
                ):
                    matched.append(t)

            elif target_lower in ("es-es", "esp", "spain", "castellano"):
                var = classify_spanish_variant(lbl, code)
                if var == "es-ES":
                    matched.append(t)

            elif target_lower in (
                "es",
                "spa",
                "spanish",
                "espanol",
                "español",
                "es-la",
                "latam",
                "latin america",
            ):
                var = classify_spanish_variant(lbl, code)
                if var in ("es-LA", "es"):
                    matched.append(t)

            else:
                if target_lower in lbl or target_lower in code:
                    matched.append(t)
                elif target_lower == "vi" and ("viet" in lbl or lbl == "vi"):
                    matched.append(t)

        if not matched:
            return []

        if target_lower in ("en", "eng", "english"):

            def get_priority(track: dict) -> int:
                label_val = str(track.get("label", "")).strip().lower()
                if "cr" in label_val:
                    return 0
                if "english" in label_val or "eng" in label_val or label_val == "en":
                    if "force" not in label_val:
                        return 1
                if "force" in label_val or "forced" in label_val:
                    return 2
                return 3

            matched.sort(key=get_priority)

        elif target_lower in (
            "es",
            "spa",
            "spanish",
            "espanol",
            "español",
            "es-la",
            "latam",
            "latin america",
            "es-es",
            "esp",
            "spain",
            "castellano",
        ):

            def get_priority_es(track: dict) -> int:
                label_val = str(track.get("label", "")).strip().lower()
                c = str(track.get("lang", "")).strip().lower()
                var = classify_spanish_variant(label_val, c)
                if var == "es-LA":
                    return 0
                if "cr" in label_val:
                    return 1
                return 2

            matched.sort(key=get_priority_es)

        selected = matched[0]
        return [
            {
                "url": str(selected["url"]),
                "label": str(selected["label"]),
                "lang": str(selected["lang"]),
                "referer": referer,
            }
        ]

    def _get_720p_playlist_url(self, master_url: str, player_url: str) -> str:
        """Select 720p (or highest available) stream from a master m3u8 playlist."""
        if ".m3u8" not in master_url.lower():
            return master_url
        try:
            parsed_player = urlparse(player_url)
            origin = f"{parsed_player.scheme}://{parsed_player.netloc}"
            extra_headers = {"Origin": origin}
            safe_referer = get_safe_referer(player_url)
            res = None
            try:
                res = self.http.get(
                    master_url, referer=safe_referer, retries=1, headers=extra_headers
                )
                if res.status_code == 403:
                    raise ValueError("HTTP 403 Forbidden")
                if res.status_code != 200 or not res.text.strip():
                    res = None
            except Exception:
                pass

            if res is None:
                try:
                    res = self.http.get(
                        master_url, referer=player_url, retries=1, headers=extra_headers
                    )
                except Exception:
                    pass

            if res is None or res.status_code != 200 or not res.text:
                return master_url

            lines = res.text.split("\n")
            url_720p = ""
            highest_url = ""
            highest_res = 0
            for idx, line in enumerate(lines):
                line = line.strip()
                if line.startswith("#EXT-X-STREAM-INF"):
                    res_match = re.search(r"RESOLUTION=(\d+)x(\d+)", line, re.IGNORECASE)
                    next_line = lines[idx + 1].strip() if idx + 1 < len(lines) else ""
                    if next_line and not next_line.startswith("#"):
                        absolute_url = urljoin(master_url, next_line)
                        if res_match:
                            height = int(res_match.group(2))
                            if height == 720:
                                url_720p = absolute_url
                            if height > highest_res:
                                highest_res = height
                                highest_url = absolute_url
            return url_720p or highest_url or master_url
        except Exception as e:
            console.print(f"[dim]Failed to resolve 720p playlist: {e}[/dim]")
            return master_url
