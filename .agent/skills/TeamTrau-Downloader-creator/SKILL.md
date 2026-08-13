---
name: TeamTrau-Downloader-creator
description: "Guidelines and architecture for designing and implementing high-performance, browser-less anime batch downloaders. Covers AJAX reverse-engineering, native VRF decryption, locked-file cookie extraction, WAF/CDN bypasses, HLS fragment decoding, and Sonarr integrations."
category: development
tags: "[anime, downloader, python, crawler, waf-bypass, rc4, cookies-extraction]"
date_added: "2026-06-05"
---

# TeamTrau-Downloader-creator

This skill encapsulates the architecture, logic, and techniques developed during the TeamTrau Batch Downloader project. Use it as a blueprint to design, build, and optimize robust download tools for various anime streaming platforms.

## 1. Core Architecture Philosophy

Always prioritize lightweight static calls over heavy browser automation:
1. **Static API/AJAX (Top Priority):** Reverse-engineer the target site's JavaScript to locate AJAX endpoints for episode lists and stream sources. Implement token generation (e.g., VRF tokens) natively in Python.
2. **Avoid Headless Browsers:** Browser tools like Playwright or Selenium consume significant resources and frequently fail due to network/firewall blocks on new machines.
3. **Multi-Browser Cookies Backup:** Collect session cookies to bypass WAF, but scan multiple browsers (Chrome, Edge, Brave, Vivaldi, Opera, Firefox) and bypass write locks dynamically.

---

## 2. Technical Implementation Details & Code Snippets

### Technique 1: Browser-less Scraping via Native VRF/RC4 Encryption
Anime sites often protect AJAX endpoints using dynamic tokens (`vrf`) hashed from IDs.
- **Discovery:** Open DevTools (F12) -> Network Tab -> search for `ajax/episode/list` or media source APIs to analyze parameters.
- **Replication:** Search JS source files for encryption algorithms (usually RC4, Base64, MD5, or AES).

*Native Python RC4 Decryption Code:*
```python
import base64
import urllib.parse

def rc4(key: str, data: bytes) -> bytes:
    s_box = list(range(256))
    j = 0
    out = bytearray()
    key_bytes = key.encode('utf-8')
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

def generate_vrf(text: str, rc4_key: str = "simple-hash") -> str:
    encrypted = rc4(rc4_key, text.encode('utf-8'))
    return base64.b64encode(encrypted).decode('utf-8')
```

### Technique 2: Locked-File Cookie Extraction (SQLite URI & Backup Copy)
When browsers are running, their `Cookies` SQLite databases are exclusively locked on Windows, causing `PermissionError: [Errno 13] Permission denied`.
- **Solution:** Attempt to copy the file using Windows API (`CopyFileW` via `ctypes`) or `shutil`. If copying fails, directly query the locked database by establishing a read-only, non-locking connection using the SQLite URI scheme query parameter `?mode=ro&nolock=1`.

*Safe Database Copy & URI Parser Code:*
```python
import os
import shutil
import sqlite3
import tempfile
import ctypes

def safe_extract_cookies(cookies_db_path: str, temp_db_path: str) -> list:
    copied = False
    try:
        res = ctypes.windll.kernel32.CopyFileW(cookies_db_path, temp_db_path, False)
        if res != 0:
            copied = True
    except Exception:
        pass

    if not copied:
        try:
            shutil.copy2(cookies_db_path, temp_db_path)
            copied = True
        except Exception:
            pass

    rows = []
    if copied:
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT host_key, name, path, is_secure, expires_utc, encrypted_value FROM cookies")
        rows = cursor.fetchall()
        conn.close()
        os.remove(temp_db_path)
    else:
        # Connect to the locked database directly in read-only and no-lock mode
        uri_path = cookies_db_path.replace("\\", "/")
        if not uri_path.startswith("/"):
            uri_path = "/" + uri_path
        uri = f"file://{uri_path}?mode=ro&nolock=1"
        try:
            conn = sqlite3.connect(uri, uri=True)
            cursor = conn.cursor()
            cursor.execute("SELECT host_key, name, path, is_secure, expires_utc, encrypted_value FROM cookies")
            rows = cursor.fetchall()
            conn.close()
        except Exception as e:
            print(f"Failed direct locked connection: {e}")
    return rows
```
*Multi-browser scan logic:* Iterate through Chrome, Edge, Brave, Vivaldi, Opera (decrypting keys via DPAPI) and **Firefox** (read plaintext from `cookies.sqlite` in `%APPDATA%\Mozilla\Firefox\Profiles\`).

### Technique 3: Bypassing WAF (Web Application Firewall) & Cloudflare
1. **TLS Fingerprinting:** Use `curl_cffi` instead of standard `requests` to simulate Chrome/Firefox Client Hello TLS fingerprints.
2. **Origin-Only Referers:** Video CDNs (e.g., Mewstream, Nekostream) validate the `Referer` header. Detailed URL paths or query strings trigger `403 Forbidden`. Trim referer headers to scheme and domain only (e.g. `https://megaplay.buzz/`).
3. **Dynamic Origin Derivation:** Derive and supply an `Origin` header dynamically based on either the `Referer` domain or the target segment/API hostname to satisfy WAF cross-origin (CORS) check validations.

*Secure Client impersonation Code:*
```python
from curl_cffi import requests
import urllib.parse

class HttpClient:
    def __init__(self):
        self.session = requests.Session(impersonate="chrome120")
        
    def get(self, url: str, referer: str = None) -> requests.Response:
        headers = {}
        if referer:
            # Clean Referer to origin only
            parsed = urllib.parse.urlparse(referer)
            headers["Referer"] = f"{parsed.scheme}://{parsed.netloc}/"
            # Derive Origin
            if parsed.scheme and parsed.netloc:
                headers["Origin"] = f"{parsed.scheme}://{parsed.netloc}"
        else:
            parsed_dest = urllib.parse.urlparse(url)
            if parsed_dest.scheme and parsed_dest.netloc:
                headers["Origin"] = f"{parsed_dest.scheme}://{parsed_dest.netloc}"
        return self.session.get(url, headers=headers)
```

### Technique 4: Parallel HLS Downloads, CORS Bypasses & Retry Resilience
Some CDNs hide TS video chunks as PNG images by adding a mock 70-byte PNG header (`\x89PNG\r\n\x1a\n...`). Without cleansing, ffmpeg interprets this as static images, resulting in broken 10-second outputs.
- **Concurrent Workers:** Use a thread pool with higher worker counts (e.g., `max_workers=16`) and low sleep jitter (`random.uniform(0.05, 0.12)`) to accelerate downloads without triggering WAF blocks.
- **CORS Bypass (Correct Origin):** Set the `Origin` header to match the player host origin (derived from the player's referer URL) rather than the CDN segment hostname. This mimics real browser cross-origin requests.
- **Segment Retry Resilience:** Ensure the native segment downloader retries failed segments individually (e.g., up to 3 attempts with exponential backoff like `random.uniform(1.0, 2.5) * attempt`) instead of immediately aborting the entire HLS task on a single transient HTTP failure.
- **Handling AES-128 Encryption & Fallback:** Native segment downloading does not natively decrypt AES-128 HLS streams. Scrapers must detect `#EXT-X-KEY` in the m3u8 playlist. If encryption is present, or if native remuxing fails, immediately fall back to `yt-dlp` or raw `ffmpeg` which natively support key resolution and decryption.

*Cleansing Fake PNG Header & Fallback logic snippet:*
```python
# 1. Skip native downloader if encrypted
if "#EXT-X-KEY" in m3u8_text or "#EXT-X-SESSION-KEY" in m3u8_text:
    raise ValueError("HLS stream is encrypted (AES-128)")

# 2. Cleansing fake PNG headers
def clean_ts_segment(data: bytes) -> bytes:
    PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
    if data.startswith(PNG_SIGNATURE):
        return data[70:]
    return data
```

### Technique 5: Sonarr-Compliant Folder and File Naming
Strictly structure directories and output files to integrate cleanly with Sonarr:
- **Directory Structure:** `{clean_series_title}/season-{season}/`
- **Single Episode File:** `{clean_series_title}-s{season:02d}e{episode:02d}.mp4`
- **Multi-Episode / Range File:** `{clean_series_title}-s{season:02d}e{start:02d}-e{end:02d}.mp4`

### Technique 6: Single-Track Subtitle Selection & Prioritization
When streaming APIs return subtitles for multiple languages without proper language tags or under generic classifications, downloaders can end up downloading dozens of unneeded subtitles.
- **Solution:** Filter tracks strictly by verifying labels and codes against a non-target language blocklist. If multiple matching tracks for the target language (e.g. English) are found, prioritize them based on tags (e.g., preference: CR > standard > forced) and return **exactly one** best track. This results in exactly 1 clean subtitle file without redundant language suffix files.

*Single-Track Selection & Prioritization Code:*
```python
def select_best_subtitle(tracks: list[dict], target_lang: str) -> list[dict]:
    target_lower = target_lang.lower()
    matched = []
    
    # 1. Filter out non-target languages
    for t in tracks:
        lbl = t["label"].strip().lower()
        code = t["lang"].strip().lower()
        
        if target_lower in ("en", "eng", "english"):
            # Block non-English indicators
            non_eng = ["vi", "vietnamese", "es", "spanish", "fr", "french", "de", "german", "ar", "arabic", "ru", "russian", "ko", "korean", "ja", "japanese", "zh", "ch", "chinese", "id", "indonesian", "th", "thai"]
            if lbl in non_eng or code in non_eng or any(len(x) > 2 and x in lbl for x in non_eng):
                continue
            # Accept only English keywords
            if (lbl in ["english", "eng", "en", "forced", "force", "cr"] or 
                any(kw in lbl for kw in ["english", "forced", "force", "cr"]) or 
                lbl in ("sub", "srt", "vtt")):
                matched.append(t)
        else:
            if target_lower in lbl or target_lower in code:
                matched.append(t)
                
    if not matched:
        return []
        
    # 2. Prioritize English tracks (CR > Standard > Forced)
    if target_lower in ("en", "eng", "english"):
        def get_priority(track: dict) -> int:
            lbl = track["label"].strip().lower()
            if "cr" in lbl:
                return 0
            if "english" in lbl or "eng" in lbl or lbl == "en":
                if "force" not in lbl:
                    return 1
            if "force" in lbl or "forced" in lbl:
                return 2
            return 3
        matched.sort(key=get_priority)
        
    return [matched[0]]
```

### Technique 7: Consensus-Based CDN Cross-Checking
To prevent servers from serving files of incorrect shows or wrong episodes due to database mismappings:
1. **Extract MD5 CDN Hashes:** Extract the unique anime and episode hashes from resolved stream or subtitle URLs (`/anime/<anime_hash>/<episode_hash>/`).
2. **Consensus Voting:** Pre-resolve all available servers for the target episode. Group and count the occurrences of the MD5 hashes.
3. **Filter Outliers:** Discard any server whose resolved hashes do not match the majority consensus hash to ensure you only download the correct movie.

*Extract Hashes & Consensus Validation Code:*
```python
import re

def extract_hashes_from_url(url: str) -> tuple[str, str] | None:
    if not url:
        return None
    # MD5 hashes are 32-character hex strings
    m = re.search(r"/anime/([a-fA-F0-9]{32})/([a-fA-F0-9]{32})/", url)
    if m:
        return m.group(1), m.group(2)
    return None
```

### Technique 8: Windows MAX_PATH Protection (Truncation & Unique Hash)
Windows enforces a default `MAX_PATH` limit of 260 characters. Extremely long anime titles easily cause standard players (like Windows Media Player) or Explorer to fail.
- **Solution:** Clean and truncate the title to a maximum length (e.g., 80 characters) using word boundaries.
- **Collision Avoidance:** Append a short unique MD5-based suffix (e.g. `[8f12a4]`) so that truncated titles do not collide in the filesystem.

*MAX_PATH Protection Code:*
```python
import hashlib

def shorten_title_safe(title: str, max_len: int = 80) -> str:
    if len(title) <= max_len:
        return title
    # Truncate at a word boundary
    truncated = title[:max_len].rsplit(" ", 1)[0].strip()
    if len(truncated) < max_len // 2:
        truncated = title[:max_len].strip()
    h = hashlib.md5(title.encode("utf-8")).hexdigest()[:6]
    return f"{truncated} [{h}]"
```

### Technique 9: FFmpeg Remux Optimization & Error Handling
1. **Audio Compatibility:** When converting HLS `.ts` (using ADTS AAC) to `.mp4`, apply `-bsf:a aac_adtstoasc` to ensure correct audio indexing on older media players.
2. **Fast Start:** Use `-movflags +faststart` to move the index atom to the beginning of the file, allowing immediate playback.
3. **DNS Fail-Fast:** Catch DNS resolution errors immediately during HLS fragment fetching and skip the server instantly instead of hanging on timeouts.

---

## 3. Step-by-Step New Scraper Scaffolding

When writing a downloader module for a new platform:
1. **Analyze:** Capture AJAX requests using static pages and extract movie IDs (`animeId`/`mangaId`).
2. **Server List Extraction:** Request `/ajax/server/list` to fetch active embed providers.
3. **Resolve Stream Sources:** Execute a POST/GET API call to `/stream/getSources` with custom WAF headers and Origin referers to get HLS m3u8 playlist links.
4. **Cross-Check Verification:** Run the consensus MD5 check across all resolved servers to filter out mismatched/wrong titles.
5. **Download & Process:** Run concurrent HLS downloads with DNS fail-fast handling, clean fake signatures, and remux via local `ffmpeg` using `-bsf:a aac_adtstoasc` and `-movflags +faststart`.
6. **Format:** Output to directories conforming to Sonarr conventions, keeping total path lengths safe on Windows via `shorten_title_safe`.
