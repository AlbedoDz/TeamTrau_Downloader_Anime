import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from downloader.extractor import BaseExtractor, register_extractor
from downloader.utils import classify_spanish_variant, console, get_safe_referer


@register_extractor
class AnikotoExtractor(BaseExtractor):
    """Extractor for anikototv.to.

    Episode list is fully JS-rendered; we use Playwright (headless Chromium)
    to wait for `#w-episodes` to populate, then extract `data-ids` / `data-slug`
    from each episode <a> element.  All subsequent server-resolution calls are
    done with the lightweight curl_cffi HTTP client.
    """

    def __init__(self, http_client):
        super().__init__(http_client)
        self.base_url = "https://anikototv.to/"

    def match(self, url: str) -> bool:
        """Match URLs containing anikototv.to."""
        parsed = urlparse(url)
        return "anikototv.to" in parsed.netloc

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def get_anime_details(self, url: str) -> dict:
        """Return anime title + episode list by fetching statically and generating vrf tokens."""
        # Normalize and prepare fallback candidate URLs (e.g. strip /ep-1 if 404)
        candidate_urls = [url]
        no_ep_url = re.sub(r"/ep-[\w-]+/?$", "", url)
        if no_ep_url != url and no_ep_url not in candidate_urls:
            candidate_urls.append(no_ep_url)

        if "/watch/" in url:
            anime_variant = no_ep_url.replace("/watch/", "/anime/")
            if anime_variant not in candidate_urls:
                candidate_urls.append(anime_variant)
        elif "/anime/" in url:
            watch_variant = no_ep_url.replace("/anime/", "/watch/")
            if watch_variant not in candidate_urls:
                candidate_urls.append(watch_variant)

        res = None
        for cand_url in candidate_urls:
            console.print(f"[info]Fetching anime page (static fetch): {cand_url}[/info]")
            try:
                r = self.http.get(cand_url)
                if r.status_code == 200 and r.text:
                    res = r
                    url = cand_url
                    break
            except Exception as fe:
                console.print(f"[dim]Failed candidate fetch {cand_url}: {fe}[/dim]")

        if not res or res.status_code != 200:
            console.print(
                f"[error]Failed to fetch watch page (HTTP {res.status_code if res else '404'})[/error]",
                style="red",
            )
            return {"title": "Unknown Anime", "episodes": [], "description": "", "year": None}

        try:
            soup = BeautifulSoup(res.text, "html.parser")
            h1 = soup.find("h1", class_="title")
            title = h1.text.strip() if h1 else "Unknown Anime"
            console.print(f"[success]Title: {title}[/success]")

            description = ""
            desc_el = soup.select_one(".content")
            if desc_el:
                description = desc_el.text.strip()

            year = None
            for div in soup.select("div"):
                txt = div.text.strip()
                if txt.startswith("Premiered:") or txt.startswith("Aired:"):
                    m_yr = re.search(r"\b(19\d{2}|20\d{2})\b", txt)
                    if m_yr:
                        year = int(m_yr.group(1))
                        break

            # Extract anime ID (mangaId or data-id) from page source
            m_id = re.search(r'(?:mangaId|animeId|manga_id)\s*=\s*["\']?(\d+)', res.text)
            anime_id = None
            if m_id:
                anime_id = m_id.group(1)
            else:
                for el in soup.select("[data-id], [data-anime-id]"):
                    val = el.get("data-id") or el.get("data-anime-id")
                    if val and str(val).isdigit():
                        anime_id = str(val)
                        break

            if not anime_id:
                console.print("[error]Could not find anime ID in page source.[/error]", style="red")
                return {"title": title, "episodes": [], "description": description, "year": year}

            # Generate VRF token using RC4 simple-hash algorithm
            def rc4(key: str, data: bytes) -> bytes:
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
                    k = s_box[(s_box[i] + s_box[j]) % 256]
                    out.append(byte ^ k)
                return bytes(out)

            def vrf_encrypt(text: str) -> str:
                encrypted = rc4("simple-hash", text.encode("utf-8"))
                import base64

                return base64.b64encode(encrypted).decode("utf-8")

            import urllib.parse

            vrf = vrf_encrypt(anime_id)
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

            episodes = []
            seen_slugs = set()
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
                        "num": data_slug,
                        "slug": data_slug,
                        "ids": data_ids,
                        "clean_text": clean_text,
                        "url": ep_url,
                    }
                )

        except Exception as e:
            console.print(f"[error]Failed to parse anime details: {e}[/error]", style="red")
            return {"title": "Unknown Anime", "episodes": [], "description": "", "year": None}

        console.print(f"[success]Found {len(episodes)} episodes.[/success]")
        return {"title": title, "episodes": episodes, "description": description, "year": year}

    def get_episode_servers(self, episode_item: dict) -> list[dict]:
        """Fetch and parse all available servers for the episode."""
        ep_url = episode_item["url"]
        ep_ids = episode_item["ids"]
        ep_num = episode_item["num"]

        servers_list_url = urljoin(self.base_url, f"/ajax/server/list?servers={ep_ids}")
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
        type_divs = soup.select(".servers .type")
        servers = []
        if type_divs:
            for div in type_divs:
                t_type = div.get("data-type") or "sub"
                for li in div.select("li[data-link-id]"):
                    link_id = li.get("data-link-id")
                    name = li.get_text().strip()
                    servers.append(
                        {
                            "id": link_id,
                            "name": f"{name} ({t_type.upper()})",
                            "type": t_type,
                        }
                    )

        # Sort servers: sub first, then prefer HD-1 and Vidstream
        def server_priority(s: dict) -> int:
            name = s.get("name", "").lower()
            t = s.get("type", "sub")
            score = 0 if t == "sub" else 100
            if "hd-1" in name:
                score += 1
            elif "vidstream" in name:
                score += 2
            elif "megacloud" in name:
                score += 3
            else:
                score += 10
            return score

        servers.sort(key=server_priority)
        return servers

    def get_episode_data(
        self, episode_item: dict, lang: str, server_info: dict | None = None
    ) -> dict:
        """Resolve player, HLS stream, and subtitles for a specific episode."""
        ep_url = episode_item["url"]
        ep_ids = episode_item["ids"]
        ep_num = episode_item["num"]

        headers = {"X-Requested-With": "XMLHttpRequest"}

        if server_info:
            link_id = server_info["id"]
            server_name = server_info["name"]
            console.print(f"[info]Resolving server: {server_name} (ID: {link_id})[/info]")
        else:
            console.print(f"[info]Resolving servers for Ep {ep_num}...[/info]")

            # 1. Fetch server list HTML
            servers_list_url = urljoin(self.base_url, f"/ajax/server/list?servers={ep_ids}")
            try:
                servers_json = self.http.get_json(servers_list_url, headers=headers, referer=ep_url)
                servers_html = servers_json.get("result", "")
            except Exception as e:
                console.print(
                    f"[error]Failed to fetch server list for Ep {ep_num}: {e}[/error]",
                    style="red",
                )
                return {"video_url": None, "subtitles": []}

            # 2. Select preferred server
            soup = BeautifulSoup(servers_html, "html.parser")
            server_lis = soup.select("li[data-link-id]")
            if not server_lis:
                console.print(
                    f"[warning]No servers found for Ep {ep_num}[/warning]", style="yellow"
                )
                return {"video_url": None, "subtitles": []}

            selected_li = None
            for pref in ["HD-1", "Vidstream", "MegaCloud", "RapidCloud"]:
                for li in server_lis:
                    if pref.lower() in li.get_text().lower():
                        selected_li = li
                        break
                if selected_li:
                    break
            if not selected_li:
                selected_li = server_lis[0]

            link_id = selected_li.get("data-link-id")
            server_name = selected_li.get_text().strip()
            console.print(f"[info]Selected server: {server_name} (ID: {link_id})[/info]")

        # 3. Fetch player embed URL
        player_info_url = urljoin(self.base_url, f"/ajax/server?get={link_id}")
        try:
            player_json = self.http.get_json(player_info_url, headers=headers, referer=ep_url)
            player_url = player_json.get("result")
            if isinstance(player_url, dict):
                player_url = player_url.get("url")
        except Exception as e:
            console.print(
                f"[error]Failed to get player URL for Ep {ep_num}: {e}[/error]",
                style="red",
            )
            return {"video_url": None, "subtitles": []}

        console.print(f"[info]Player embed URL: {player_url}[/info]")

        # Fetch player page HTML to check for data-id (used by Megaplay/Megacloud to hide actual media ID)
        real_id = None
        is_new_api = False
        if "megaplay.buzz" in player_url or "vidwish.live" in player_url:
            is_new_api = True

        try:
            embed_res = self.http.get(player_url, referer=ep_url)
            embed_soup = BeautifulSoup(embed_res.text, "html.parser")
            player_div = embed_soup.find(id="megaplay-player") or embed_soup.find(class_="fix-area")
            if player_div and player_div.get("data-id"):
                real_id = player_div.get("data-id")
        except Exception as e:
            console.print(f"[dim]Failed to fetch/parse embed page: {e}[/dim]")

        # 4. Build sources API URL from player URL
        if real_id:
            parsed = urlparse(player_url)
            if is_new_api:
                # Try the standard getSources endpoint first (it's the current working one), fallback to getSourcesNew if needed
                api_url = f"{parsed.scheme}://{parsed.netloc}/stream/getSources?id={real_id}"
                fallback_api_url = f"{parsed.scheme}://{parsed.netloc}/stream/getSourcesNew?id={real_id}&id={real_id}"
            else:
                api_url = f"{parsed.scheme}://{parsed.netloc}/stream/getSources?id={real_id}"
                fallback_api_url = None
        else:
            if is_new_api:
                console.print(
                    "[warning]Megaplay player page empty or missing player div. Skipping this server.[/warning]",
                    style="yellow",
                )
                return {"video_url": None, "subtitles": []}
            api_url = self._build_sources_api_url(player_url)
            fallback_api_url = None

        if not api_url:
            console.print("[warning]Could not resolve sources API URL.[/warning]", style="yellow")
            return {"video_url": None, "subtitles": []}

        # 5. Fetch sources JSON
        console.print(f"[info]Fetching player sources: {api_url}[/info]")
        api_headers = {"X-Requested-With": "XMLHttpRequest", "Referer": player_url}
        try:
            sources_json = self.http.get_json(api_url, headers=api_headers)
        except Exception as e:
            if fallback_api_url:
                console.print(
                    f"[warning]Failed to fetch from {api_url}: {e}. Trying fallback...[/warning]",
                    style="yellow",
                )
                console.print(
                    f"[info]Fetching player sources (fallback): {fallback_api_url}[/info]"
                )
                try:
                    sources_json = self.http.get_json(fallback_api_url, headers=api_headers)
                except Exception as fe:
                    console.print(
                        f"[error]Failed to fetch stream sources (fallback): {fe}[/error]",
                        style="red",
                    )
                    return {"video_url": None, "subtitles": []}
            else:
                console.print(f"[error]Failed to fetch stream sources: {e}[/error]", style="red")
                return {"video_url": None, "subtitles": []}

        # 6. Parse subtitles and video sources
        all_tracks = self._find_subtitles(sources_json)
        all_videos = self._find_video_sources(sources_json)

        # Filter and select exactly one best subtitle track for requested language
        matched_subs = self._select_best_subtitle(all_tracks, lang, player_url)

        if not matched_subs and all_tracks:
            avail_langs = sorted(list({t.get("label", t.get("lang", "unknown")) for t in all_tracks if t.get("label") or t.get("lang")}))
            console.print(
                f"[warning]Ep {ep_num}: Subtitle for requested language '{lang}' not available. Skipping subtitle download. (Available tracks: {', '.join(avail_langs)})[/warning]",
                style="yellow",
            )

        # Resolve 720p HLS or best available
        video_url = None
        if all_videos:
            hls = [v for v in all_videos if v["type"] == "hls"]
            if hls:
                video_url = self._get_720p_playlist_url(hls[0]["url"], player_url)
            else:
                video_url = all_videos[0]["url"]

        console.print(
            f"[success]Ep {ep_num}: video={'yes' if video_url else 'no'}, "
            f"subtitles={len(matched_subs)}[/success]"
        )
        return {"video_url": video_url, "subtitles": matched_subs, "player_url": player_url}

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _clean_ep_text(self, raw: str, ep_num: str) -> str:
        """Strip badges, episode numbers and trailing status keywords."""
        text = re.sub(r"\s+", " ", raw).strip()
        text = re.sub(
            r"(EN \(\d+\)|No Sub|Error|Scanning\.\.\.)$", "", text, flags=re.IGNORECASE
        ).strip()
        # Remove leading ep number (e.g. "1 - Title" → "Title")
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
        """Convert a player embed URL into a getSources API URL."""
        parsed = urlparse(player_url)
        path = parsed.path

        # Case A: megaplay.buzz /stream/s-N/<id>
        m = re.search(r"/stream/s-\d+/(\d+)", path)
        if m:
            return f"{parsed.scheme}://{parsed.netloc}/stream/getSources?id={m.group(1)}"

        # Case B: URL already points at getSources
        if "getSources" in path or "sources" in path:
            return player_url

        # Case C: megacloud / rapidcloud  /embed-X/e-Y/<id>
        m = re.search(r"(/embed-[^/]+/e-[^/]+/)([^/?#]+)", path)
        if m:
            return f"{parsed.scheme}://{parsed.netloc}{m.group(1)}getSources?id={m.group(2)}"

        return None

    def _find_subtitles(self, obj) -> list[dict]:
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
                                    "label": t.get("label")
                                    or t.get("name")
                                    or t.get("language")
                                    or "Sub",
                                    "lang": t.get("lang") or t.get("language") or "en",
                                }
                            )
            elif isinstance(v, str) and (
                v.endswith(".vtt") or v.endswith(".srt") or "lostproject.club" in v
            ):
                if v.startswith("http"):
                    lbl = "Sub"
                    if obj.get("label") or obj.get("name") or obj.get("language"):
                        lbl = obj.get("label") or obj.get("name") or obj.get("language")
                    else:
                        m = re.search(r"/([a-zA-Z0-9_-]+)\.(vtt|srt)", v)
                        if m:
                            lbl = m.group(1).upper()
                    tracks.append({"url": v, "label": lbl, "lang": lbl.lower()})
            elif isinstance(v, (dict, list)):
                tracks.extend(self._find_subtitles(v))
        return tracks

    def _find_video_sources(self, obj) -> list[dict]:
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
                                    "type": s.get("type") or ("hls" if ".m3u8" in u else "mp4"),
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
    ) -> list[dict]:
        """Filter tracks by language and return a list containing exactly the best matching subtitle track (at most 1)."""
        target_lower = target_lang.lower()

        # 1. Filter tracks that match the target language
        matched = []
        for t in tracks:
            lbl = t["label"].strip().lower()
            code = t["lang"].strip().lower()

            if target_lower in ("en", "eng", "english"):
                # Strict English check
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

                # If label or code matches non-English, skip
                if lbl in non_english_indicators or code in non_english_indicators:
                    continue
                if any(len(ind) > 2 and ind in lbl for ind in non_english_indicators):
                    continue

                # Must have English indicator
                english_keywords = ["english", "eng", "en", "forced", "force", "cr"]
                if (
                    lbl in english_keywords
                    or code in english_keywords
                    or any(kw in lbl for kw in ["english", "forced", "force", "cr"])
                    or lbl in ("sub", "srt", "vtt")
                ):
                    matched.append(t)
            elif target_lower in ("es-es", "esp", "spain", "castellano"):
                # Explicit Spain/European Spanish requested
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
                # Spanish (Latin America prioritized, European Spanish excluded unless explicitly requested)
                var = classify_spanish_variant(lbl, code)
                if var in ("es-LA", "es"):
                    matched.append(t)
            else:
                # For other languages (e.g. "vi")
                if target_lower in lbl or target_lower in code:
                    matched.append(t)
                elif target_lower == "vi" and ("viet" in lbl or "vi" == lbl):
                    matched.append(t)

        if not matched:
            return []

        # 2. Prioritize and select exactly one
        if target_lower in ("en", "eng", "english"):

            def get_priority(track: dict) -> int:
                lbl = track["label"].strip().lower()
                # Priority 0: English CR
                if "cr" in lbl:
                    return 0
                # Priority 1: Generic English (not forced)
                if "english" in lbl or "eng" in lbl or lbl == "en":
                    if "force" not in lbl:
                        return 1
                # Priority 2: Forced English
                if "force" in lbl or "forced" in lbl:
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

            def get_priority(track: dict) -> int:
                lbl = track["label"].strip().lower()
                c = track.get("lang", "").strip().lower()
                var = classify_spanish_variant(lbl, c)
                # Priority 0: Latin America (es-LA)
                if var == "es-LA":
                    return 0
                # Priority 1: CR Spanish
                if "cr" in lbl:
                    return 1
                # Priority 2: Spain Spanish or generic
                return 2

            matched.sort(key=get_priority)

        selected = matched[0]
        return [
            {
                "url": selected["url"],
                "label": selected["label"],
                "lang": selected["lang"],
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
            except Exception as e:
                if "403" in str(e):
                    # Fail fast on 403 to avoid retry delays
                    pass
                else:
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
