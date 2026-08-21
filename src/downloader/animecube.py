import base64
import hashlib
import json
import os
import re
from urllib.parse import urlparse

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from downloader.extractor import BaseExtractor, register_extractor
from downloader.utils import console


@register_extractor
class AnimeCubeExtractor(BaseExtractor):
    """Extractor for animecube.live using Next.js API and AES-256-GCM decryption."""

    def __init__(self, http_client):
        super().__init__(http_client)
        self.base_url = "https://animecube.live"

    def match(self, url: str) -> bool:
        """Match URLs containing animecube.live."""
        parsed = urlparse(url)
        return "animecube.live" in parsed.netloc

    def get_anime_details(self, url: str) -> dict:
        """Extract anime title and complete episode list from Next.js state."""
        url = url.strip("\"'")
        parsed = urlparse(url)
        path_parts = [p for p in parsed.path.split("/") if p]
        anime_slug = path_parts[1] if len(path_parts) > 1 else "unknown"

        console.print(f"[info]Fetching AnimeCube page: {url}[/info]")

        try:
            res = self.http.get(url)
            if res.status_code != 200:
                console.print(
                    f"[error]Failed to fetch AnimeCube page (HTTP {res.status_code})[/error]",
                    style="red",
                )
                return {"title": anime_slug.replace("-", " ").title(), "episodes": []}

            text = res.text
            title = anime_slug.replace("-", " ").title()

            m_title = re.search(r"<h1[^>]*>([^<]+)</h1>", text)
            if m_title:
                title = m_title.group(1).strip()
            else:
                m_og = re.search(r'property="og:title"\s+content="([^"]+)"', text)
                if m_og:
                    title = m_og.group(1).split("-")[0].strip().title()

            console.print(f"[success]Anime Title: {title}[/success]")

            # Extract Next.js state (__next_f pushes)
            pushes = re.findall(r"self\.__next_f\.push\((.*?)\)</script>", text, re.DOTALL)
            full_str = ""
            for p in pushes:
                try:
                    data = json.loads(p)
                    if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], str):
                        full_str += data[1]
                except Exception:
                    pass

            episodes = []
            seen = set()
            ep_index = 1

            pt_match = re.search(r'"primaryTabs"\s*:\s*(\[.*?\])\s*,\s*"updateDays"', full_str)
            if pt_match:
                try:
                    primary_tabs = json.loads(pt_match.group(1))
                    for ptab in primary_tabs:
                        p_id = ptab.get("id", "primary-1")
                        p_type = ptab.get("type", "series")
                        # Filter out trailer/PV tabs unless that's all there is
                        if p_type in ["pv", "trailer"] and len(primary_tabs) > 1:
                            continue

                        for season in ptab.get("seasons", []):
                            s_id = season.get("id", "tab-1")
                            for ep in season.get("episodes", []):
                                ep_id = ep.get("id")
                                num_disp = str(
                                    ep.get("numberDisplay") or ep.get("number") or ep_index
                                )
                                if ep_id and ep_id not in seen:
                                    seen.add(ep_id)
                                    ep_url = (
                                        f"{self.base_url}/anime/{anime_slug}"
                                        f"?season={s_id}&episode={ep_id}"
                                    )
                                    episodes.append(
                                        {
                                            "num": str(ep_index),
                                            "display_num": num_disp,
                                            "slug": ep_id,
                                            "ids": ep_id,
                                            "url": ep_url,
                                            "anime_slug": anime_slug,
                                            "primary_tab_id": p_id,
                                            "season_id": s_id,
                                            "clean_text": f"Episode {num_disp}",
                                        }
                                    )
                                    ep_index += 1
                except Exception as e:
                    console.print(f"[warning]Failed to parse primaryTabs JSON: {e}[/warning]")

            # Fallback regex search if __next_f extraction failed
            if not episodes:
                ep_pattern = re.compile(
                    rf"({re.escape(anime_slug)}-(?:(primary-[^-\s]+)-)?(tab-[^-\s]+)-ep-(\d+))"
                )
                matches = ep_pattern.findall(text)
                for full_id, p_tab, s_tab, ep_num_str in matches:
                    if full_id not in seen:
                        seen.add(full_id)
                        primary_tab_id = p_tab if p_tab else "primary-1"
                        season_id = s_tab if s_tab else "tab-1"
                        ep_num = int(ep_num_str)

                        ep_url = (
                            f"{self.base_url}/anime/{anime_slug}"
                            f"?season={season_id}&episode={full_id}"
                        )

                        episodes.append(
                            {
                                "num": str(ep_num),
                                "display_num": str(ep_num),
                                "slug": full_id,
                                "ids": full_id,
                                "url": ep_url,
                                "anime_slug": anime_slug,
                                "primary_tab_id": primary_tab_id,
                                "season_id": season_id,
                                "clean_text": f"Episode {ep_num}",
                            }
                        )
                episodes.sort(key=lambda x: int(x["num"]))

            console.print(f"[success]Found {len(episodes)} episodes on AnimeCube.[/success]")
            return {"title": title, "episodes": episodes, "description": "", "year": None}

        except Exception as e:
            console.print(f"[error]Failed to parse AnimeCube details: {e}[/error]", style="red")
            return {"title": anime_slug.replace("-", " ").title(), "episodes": []}

    def get_episode_data(
        self, episode_item: dict, lang: str, server_info: dict | None = None
    ) -> dict:
        """Resolve video source URL and subtitles using AES-256-GCM decrypted sources API."""
        ep_slug = episode_item["slug"]
        anime_slug = episode_item.get("anime_slug")
        if not anime_slug:
            anime_slug = ep_slug.split("-tab-")[0] if "-tab-" in ep_slug else ep_slug

        primary_tab_id = episode_item.get("primary_tab_id", "primary-1")
        season_id = episode_item.get("season_id", "tab-1")
        ep_num = episode_item.get("display_num") or episode_item.get("num", "1")

        console.print(f"[info]Resolving AnimeCube Ep {ep_num} ({ep_slug})...[/info]")

        # 1. Fetch versions registry
        reg_url = f"{self.base_url}/api/anime-sources-versions"
        try:
            reg_json = self.http.get_json(reg_url, referer=episode_item.get("url", self.base_url))
            by_season = reg_json.get("bySeason", {})
            version_hash = by_season.get(anime_slug, {}).get(primary_tab_id, {}).get(season_id)
        except Exception as e:
            console.print(
                f"[warning]Failed to fetch version registry: {e}[/warning]",
                style="yellow",
            )
            version_hash = None

        if not version_hash:
            console.print(
                f"[error]No version hash for {anime_slug} ({primary_tab_id}/{season_id})[/error]",
                style="red",
            )
            return {"video_url": None, "subtitles": []}

        # 2. Build obfuscated sources request
        x_obf = os.urandom(16).hex()
        sources_url = (
            f"{self.base_url}/api/anime/{anime_slug}/episode/{ep_slug}/sources"
            f"?v={version_hash}&primaryTabId={primary_tab_id}&seasonId={season_id}"
        )
        headers = {
            "Accept": "application/json",
            "X-Obf": x_obf,
            "Referer": f"{self.base_url}/anime/{anime_slug}",
        }

        try:
            res_json = self.http.get_json(sources_url, headers=headers)
        except Exception as e:
            console.print(f"[error]Failed to fetch sources API: {e}[/error]", style="red")
            return {"video_url": None, "subtitles": []}

        enc_payload = res_json.get("d")
        if not enc_payload:
            console.print(
                "[warning]Sources response missing encrypted payload 'd'[/warning]",
                style="yellow",
            )
            return {"video_url": None, "subtitles": []}

        # 3. AES-256-GCM Decryption
        try:
            raw = base64.b64decode(enc_payload)
            iv = raw[:12]
            ciphertext = raw[12:]

            salt = f"{x_obf}|{version_hash}".encode()
            key = hashlib.sha256(salt).digest()

            aesgcm = AESGCM(key)
            decrypted_bytes = aesgcm.decrypt(iv, ciphertext, None)
            sources_data = json.loads(decrypted_bytes.decode("utf-8"))
        except Exception as e:
            console.print(f"[error]Failed to decrypt sources payload: {e}[/error]", style="red")
            return {"video_url": None, "subtitles": []}

        sources_list = sources_data.get("sources", [])
        if not sources_list:
            console.print(
                f"[warning]No video sources found in payload for Ep {ep_num}[/warning]",
                style="yellow",
            )
            return {"video_url": None, "subtitles": []}

        # 4. Resolve video URL across ALL available sources in payload
        video_url = None
        selected_platform = "unknown"

        for src in sources_list:
            platform = src.get("platform", "").lower()
            video_id = src.get("videoId")
            private_id = src.get("privateId")
            direct_url = src.get("url") or src.get("file") or src.get("link")

            if platform == "dailymotion" and video_id:
                auth_str = f"auth={private_id}&" if private_id else ""
                meta_url = (
                    f"https://www.dailymotion.com/player/metadata/video/{video_id}?"
                    f"{auth_str}embedder=https%3A%2F%2Fanimecube.live%2F"
                )
                try:
                    meta_res = self.http.get_json(meta_url, referer="https://animecube.live/")
                    dm_err = meta_res.get("error")
                    if dm_err:
                        err_code = dm_err.get("code", "UNKNOWN")
                        console.print(
                            f"[warning]Dailymotion {video_id} unavailable ({err_code})[/warning]",
                            style="yellow",
                        )

                    qualities = meta_res.get("qualities", {})
                    auto_list = qualities.get("auto", [])
                    if auto_list and isinstance(auto_list, list):
                        for item in auto_list:
                            if item.get("url"):
                                video_url = item.get("url")
                                break
                    if not video_url:
                        for _q_key, q_val in qualities.items():
                            if isinstance(q_val, list):
                                for item in q_val:
                                    if item.get("url"):
                                        video_url = item.get("url")
                                        break
                            if video_url:
                                break
                except Exception as e:
                    console.print(
                        f"[warning]Failed DM metadata {video_id}: {e}[/warning]",
                        style="yellow",
                    )
                    video_url = None
            elif direct_url:
                video_url = direct_url

            if video_url:
                selected_platform = platform or "direct"
                break

        # Subtitles extraction
        subtitles = []
        raw_subs = sources_data.get("subtitles", [])
        for sub in raw_subs:
            sub_url = sub.get("url") or sub.get("file")
            sub_lang = sub.get("lang") or sub.get("language") or "en"
            sub_label = sub.get("label") or "English"
            if sub_url:
                subtitles.append(
                    {
                        "url": sub_url,
                        "label": sub_label,
                        "lang": sub_lang,
                        "referer": episode_item.get("url", self.base_url),
                    }
                )

        has_vid = "yes" if video_url else "no"
        console.print(
            f"[success]Ep {ep_num}: platform={selected_platform}, video={has_vid}, "
            f"subtitles={len(subtitles)}[/success]"
        )

        return {"video_url": video_url, "subtitles": subtitles, "player_url": video_url}
