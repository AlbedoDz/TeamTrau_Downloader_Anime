import sys

# Prevent UnicodeEncodeError on legacy terminals by reconfiguring stdout/stderr
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(errors="backslashreplace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(errors="backslashreplace")
    except Exception:
        pass

import base64
import ctypes
import ctypes.wintypes
import json
import os
import random
import re
import shutil
import sqlite3
import tempfile
import time
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from curl_cffi import requests
from rich.console import Console


def get_safe_referer(url: str) -> str:
    """Extract origin and append trailing slash to create a safe Referer header for CDNs."""
    if not url:
        return ""
    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}/"
    return url


console = Console(safe_box=True)


def clean_filename(name: str) -> str:
    """Sanitize string for filesystem paths by removing invalid characters."""
    # Remove invalid characters: \ / : * ? " < > |
    sanitized = re.sub(r'[\\/*?:"<>|]', "", name)
    # Remove leading/trailing spaces or dots
    sanitized = sanitized.strip().strip(".")
    # Collapse multiple spaces
    sanitized = re.sub(r"\s+", " ", sanitized)
    return sanitized if sanitized else "Downloaded_File"


def clean_folder_name(name: str) -> str:
    """Sanitize string specifically for folder names."""
    return clean_filename(name)


def classify_spanish_variant(label: str, code: str = "") -> str | None:
    """Classify a subtitle track label/code as 'es-LA', 'es-ES', or 'es' (generic).

    Returns:
        - 'es-LA': Latin American Spanish (e.g. Spanish[LAT], Español (LA), Latin America, es-419)
        - 'es-ES': European / Spain Spanish (e.g. Spanish[ESP], Español (ES), Castellano)
        - 'es': Generic or neutral Spanish
        - None: Non-Spanish track (or Portuguese)
    """
    lbl = (label or "").strip().lower()
    c = (code or "").strip().lower()

    # 1. Anti-pattern guard: Exclude Portuguese ("portuguese" contains "es")
    if "portuguese" in lbl or "portugues" in lbl or c in ("pt", "por", "pt-br", "pt-pt"):
        return None

    # 2. Check if it matches Spanish keywords or codes
    is_spanish = False
    if any(kw in lbl for kw in ["spanish", "espanol", "español", "castellano", "castilian"]):
        is_spanish = True
    elif c in (
        "es",
        "spa",
        "spanish",
        "es-la",
        "es-419",
        "es-es",
        "es_la",
        "es_419",
        "es_es",
    ):
        is_spanish = True

    if not is_spanish:
        return None

    # 3. Check for Latin American Spanish indicators (Priority)
    latin_indicators = [
        "latin america",
        "latin_america",
        "latinamerica",
        "america latina",
        "américa latina",
        "americalatina",
        "latinoamérica",
        "latinoamerica",
        "latam",
        "[lat]",
        "(lat)",
        "[la]",
        "(la)",
        "[latam]",
        "(latam)",
        "[es-la]",
        "(es-la)",
        "[es-419]",
        "(es-419)",
        "spanish[lat]",
        "spanish[la]",
        "español (la)",
        "espanol (la)",
        "spanish (la)",
        "español (lat)",
        "espanol (lat)",
        "spanish (lat)",
        "español (latam)",
        "espanol (latam)",
        "spanish (latam)",
    ]
    if any(ind in lbl for ind in latin_indicators) or c in (
        "es-la",
        "es-419",
        "es_la",
        "es_419",
        "spa-la",
        "spa-lat",
    ):
        return "es-LA"
    if re.search(
        r"\[lat\]|\(lat\)|\b\[la\]|\(la\)|\b\[latam\]|\(latam\)|\b\[es-419\]|\(es-419\)|\bespañol\s*\(\s*la\s*\)|\bespanol\s*\(\s*la\s*\)|\bspanish\s*\(\s*la\s*\)|\bespañol\s*\(\s*lat\s*\)|\bespanol\s*\(\s*lat\s*\)|\bspanish\s*\(\s*lat\s*\)",
        lbl,
    ):
        return "es-LA"

    # 4. Check for Spain / European Spanish indicators
    spain_indicators = [
        "spain",
        "españa",
        "espana",
        "castellano",
        "castilian",
        "iberian",
        "[esp]",
        "(esp)",
        "[es]",
        "(es)",
        "[es-es]",
        "(es-es)",
        "spanish[esp]",
        "español (es)",
        "espanol (es)",
        "spanish (es)",
        "español (esp)",
        "espanol (esp)",
        "spanish (esp)",
    ]
    if any(ind in lbl for ind in spain_indicators) or c in ("es-es", "es_es", "spa-es"):
        return "es-ES"
    if re.search(
        r"\[esp\]|\(esp\)|\b-\s*esp\b|\[es-es\]|\(es-es\)|\bespañol\s*\(\s*es\s*\)|\bespanol\s*\(\s*es\s*\)|\bspanish\s*\(\s*es\s*\)|\bespañol\s*\(\s*esp\s*\)|\bespanol\s*\(\s*esp\s*\)",
        lbl,
    ):
        return "es-ES"

    return "es"


def convert_timestamp_vtt_to_srt(ts: str) -> str:
    """Convert WebVTT timestamp (HH:MM:SS.mmm or MM:SS.mmm) to SRT format (HH:MM:SS,mmm)."""
    ts = ts.strip().replace(".", ",")
    parts = ts.split(":")
    if len(parts) == 2:
        # MM:SS,mmm -> prepend HH: (00:)
        ts = f"00:{ts}"
    elif len(parts) == 3:
        # Check if HH is 1-digit, pad to 2-digits
        if len(parts[0]) == 1:
            parts[0] = f"0{parts[0]}"
            ts = ":".join(parts)
    return ts


def vtt_to_srt(vtt_content: str) -> str:
    """Convert WebVTT format subtitle content to SRT format."""
    # Normalize newlines
    content = vtt_content.replace("\r\n", "\n").replace("\r", "\n")

    # Split content into blocks by double newlines
    blocks = content.split("\n\n")
    srt_blocks = []
    cue_index = 1

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        lines = block.split("\n")
        # Skip header metadata blocks
        if any(
            lines[0].startswith(prefix) for prefix in ("WEBVTT", "STYLE", "NOTE", "REGION", "CLASS")
        ):
            continue

        # Look for timestamp line (containing -->)
        ts_line_idx = -1
        for idx, line in enumerate(lines):
            if "-->" in line:
                ts_line_idx = idx
                break

        if ts_line_idx == -1:
            continue

        ts_line = lines[ts_line_idx]
        parts = ts_line.split("-->")
        if len(parts) != 2:
            continue

        start_vtt, end_vtt = parts[0], parts[1]
        # WebVTT can have trailing display settings after the end timestamp
        # (e.g. alignment), strip them
        end_vtt = end_vtt.split()[0]

        try:
            start_srt = convert_timestamp_vtt_to_srt(start_vtt)
            end_srt = convert_timestamp_vtt_to_srt(end_vtt)
        except Exception:
            continue

        # Get subtitle lines after the timestamp line
        sub_lines = lines[ts_line_idx + 1 :]
        sub_text = "\n".join(sub_lines).strip()

        # Strip HTML/XML tags often found in VTT (e.g. <i>, <b>, <c.color>)
        sub_text = re.sub(r"<[^>]+>", "", sub_text)

        if not sub_text:
            continue

        srt_blocks.append(f"{cue_index}\n{start_srt} --> {end_srt}\n{sub_text}")
        cue_index += 1

    return "\n\n".join(srt_blocks)


class HttpClient:
    """HTTP Client impersonating chrome browser using curl_cffi."""

    def __init__(
        self,
        impersonate="chrome120",
        delay_range=(2.0, 5.0),
        proxy: str | None = None,
    ):
        self.session = requests.Session(impersonate=impersonate)
        self.delay_range = delay_range
        self.last_request_time = 0.0
        if proxy:
            self.set_proxy(proxy)

    def set_proxy(self, proxy: str):
        """Configure HTTP/HTTPS proxy for curl_cffi session."""
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}
            console.print(f"[success]Configured proxy for HTTP client: {proxy}[/success]")

    def load_cookies_from_file(self, cookies_file_path: str):
        """Load Netscape format cookies file into the curl_cffi session."""
        if not cookies_file_path or not os.path.exists(cookies_file_path):
            return
        try:
            import http.cookiejar

            cookie_jar = http.cookiejar.MozillaCookieJar(cookies_file_path)
            cookie_jar.load(ignore_discard=True, ignore_expires=True)
            for cookie in cookie_jar:
                self.session.cookies.set(
                    cookie.name, cookie.value, domain=cookie.domain, path=cookie.path
                )
            console.print(
                f"[success]Loaded cookies from {cookies_file_path} into HTTP client.[/success]"
            )
        except Exception as e:
            console.print(
                f"[warning]Failed to load cookies into HTTP client: {e}[/warning]", style="yellow"
            )

    def _sleep_for_rate_limiting(self):
        """Enforce standard randomized rate-limit delay between requests."""
        if self.last_request_time > 0.0:
            elapsed = time.time() - self.last_request_time
            sleep_time = random.uniform(*self.delay_range)
            if elapsed < sleep_time:
                time.sleep(sleep_time - elapsed)
        self.last_request_time = time.time()

    def get(
        self,
        url: str,
        headers: dict | None = None,
        referer: str | None = None,
        retries: int = 4,
        delay: float = 3.0,
        rate_limit: bool = True,
        **kwargs,
    ) -> requests.Response:
        """Execute GET request with exponential backoff on retryable failures."""
        if headers is None:
            headers = {}
        if referer:
            headers["Referer"] = referer
            # Derive Origin from Referer if not explicitly set
            if "Origin" not in headers:
                parsed_ref = urlparse(referer)
                if parsed_ref.scheme and parsed_ref.netloc:
                    headers["Origin"] = f"{parsed_ref.scheme}://{parsed_ref.netloc}"
        elif "Origin" not in headers:
            # Fallback: Derive Origin from destination URL
            parsed_dest = urlparse(url)
            if parsed_dest.scheme and parsed_dest.netloc:
                headers["Origin"] = f"{parsed_dest.scheme}://{parsed_dest.netloc}"

        # Inject Sec-Fetch-* headers to bypass WAF metadata filtering on CDNs like mewstream
        if "Origin" in headers or "Referer" in headers:
            if "Sec-Fetch-Site" not in headers:
                headers["Sec-Fetch-Site"] = "cross-site"
            if "Sec-Fetch-Mode" not in headers:
                headers["Sec-Fetch-Mode"] = "cors"
            if "Sec-Fetch-Dest" not in headers:
                headers["Sec-Fetch-Dest"] = "empty"

        options = {"headers": headers, "timeout": 60, **kwargs}

        attempt = 0
        current_delay = delay
        last_error = None

        while attempt < retries:
            if rate_limit:
                self._sleep_for_rate_limiting()
            try:
                console.print(f"[dim]HTTP GET -> {url} (Attempt {attempt + 1}/{retries})[/dim]")
                response = self.session.get(url, **options)

                # Success
                if response.status_code == 200:
                    return response

                # Rate limited or server error -> backoff
                if response.status_code in (429, 403, 500, 502, 503, 504):
                    last_error = f"HTTP {response.status_code}"
                    console.print(
                        f"[warning]HTTP {response.status_code} received. "
                        f"Retrying in {current_delay:.1f}s...[/warning]",
                        style="yellow",
                    )
                    time.sleep(current_delay)
                    current_delay *= 2
                    attempt += 1
                else:
                    # Non-retryable HTTP status
                    return response
            except Exception as e:
                last_error = e
                console.print(
                    f"[warning]Request exception: {e}. "
                    f"Retrying in {current_delay:.1f}s...[/warning]",
                    style="yellow",
                )
                time.sleep(current_delay)
                current_delay *= 2
                attempt += 1

        raise Exception(f"Failed to fetch url {url} after {retries} attempts: {last_error}")

    def get_soup(self, url: str, **kwargs) -> BeautifulSoup:
        """Fetch URL and parse HTML content with BeautifulSoup."""
        # Use a retry mechanism inside GET request
        response = self.get(url, **kwargs)
        return BeautifulSoup(response.text, "html.parser")

    def get_json(self, url: str, **kwargs) -> dict:
        """Fetch URL and parse JSON payload."""
        response = self.get(url, **kwargs)
        return response.json()

    def post(
        self,
        url: str,
        data: dict | str | None = None,
        json_data: dict | None = None,
        headers: dict | None = None,
        retries: int = 3,
        delay: float = 3.0,
        rate_limit: bool = True,
        **kwargs,
    ) -> requests.Response:
        """Execute POST request with exponential backoff on retryable failures."""
        if headers is None:
            headers = {}
        if json_data is not None:
            options = {"json": json_data}
        else:
            options = {"data": data}

        options.update({"headers": headers, "timeout": 60, **kwargs})

        attempt = 0
        current_delay = delay
        last_error = None

        while attempt < retries:
            if rate_limit:
                self._sleep_for_rate_limiting()
            try:
                console.print(f"[dim]HTTP POST -> {url} (Attempt {attempt + 1}/{retries})[/dim]")
                response = self.session.post(url, **options)

                # Success
                if response.status_code in (200, 201):
                    return response

                # Rate limited or server error -> backoff
                if response.status_code in (429, 403, 500, 502, 503, 504):
                    last_error = f"HTTP {response.status_code}"
                    console.print(
                        f"[warning]HTTP {response.status_code} received on POST. "
                        f"Retrying in {current_delay:.1f}s...[/warning]",
                        style="yellow",
                    )
                    time.sleep(current_delay)
                    current_delay *= 2
                    attempt += 1
                else:
                    return response
            except Exception as e:
                last_error = e
                console.print(
                    f"[warning]POST request exception: {e}. "
                    f"Retrying in {current_delay:.1f}s...[/warning]",
                    style="yellow",
                )
                time.sleep(current_delay)
                current_delay *= 2
                attempt += 1

        raise Exception(f"Failed to POST to url {url} after {retries} attempts: {last_error}")

    def post_json(self, url: str, **kwargs) -> dict:
        """Fetch URL via POST and parse JSON payload."""
        response = self.post(url, **kwargs)
        return response.json()


# DPAPI decryption structures
class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def decrypt_dpapi(encrypted_bytes: bytes) -> bytes:
    in_blob = DATA_BLOB(
        len(encrypted_bytes),
        ctypes.cast(ctypes.create_string_buffer(encrypted_bytes), ctypes.POINTER(ctypes.c_byte)),
    )
    out_blob = DATA_BLOB()
    if ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
    ):
        size = out_blob.cbData
        address = out_blob.pbData
        decrypted = ctypes.string_at(address, size)
        ctypes.windll.kernel32.LocalFree(address)
        return decrypted
    raise OSError("Failed to decrypt DPAPI key")


def get_browser_master_key(browser: str) -> bytes:
    """Get DPAPI master key for Chrome or Edge."""
    if browser == "chrome":
        subpath = os.path.join("Google", "Chrome")
    else:
        subpath = os.path.join("Microsoft", "Edge")

    local_state_path = os.path.join(
        os.environ["USERPROFILE"],
        "AppData",
        "Local",
        subpath,
        "User Data",
        "Local State",
    )
    if not os.path.exists(local_state_path):
        raise FileNotFoundError(f"{browser.capitalize()} Local State file not found.")
    with open(local_state_path, encoding="utf-8") as f:
        local_state = json.loads(f.read())
    encrypted_key_b64 = local_state["os_crypt"]["encrypted_key"]
    encrypted_key = base64.b64decode(encrypted_key_b64)
    # The key starts with "DPAPI"
    if encrypted_key.startswith(b"DPAPI"):
        encrypted_key = encrypted_key[5:]
    return decrypt_dpapi(encrypted_key)


def decrypt_chrome_cookie(ciphertext: bytes, key: bytes) -> str:
    # Ciphertext starts with "v10" or "v11"
    if ciphertext.startswith(b"v10") or ciphertext.startswith(b"v11"):
        iv = ciphertext[3:15]
        payload = ciphertext[15:]
        aesgcm = AESGCM(key)
        try:
            return aesgcm.decrypt(iv, payload, None).decode("utf-8")
        except Exception:
            return ""
    else:
        # Legacy DPAPI decryption (before Chrome 80)
        try:
            return decrypt_dpapi(ciphertext).decode("utf-8")
        except Exception:
            return ""


def get_chrome_cookies_temp_file() -> tuple[str, str] | None:
    """Extract browser cookies (Chrome, Edge, Brave, Vivaldi, Opera, Firefox), decrypt them, and write them to a temporary Netscape cookies file."""
    import glob

    # Define browsers and their paths
    browsers = [
        {
            "name": "chrome",
            "db_paths": [
                os.path.join(
                    os.environ["USERPROFILE"],
                    "AppData",
                    "Local",
                    "Google",
                    "Chrome",
                    "User Data",
                    "Default",
                    "Network",
                    "Cookies",
                ),
                os.path.join(
                    os.environ["USERPROFILE"],
                    "AppData",
                    "Local",
                    "Google",
                    "Chrome",
                    "User Data",
                    "Default",
                    "Cookies",
                ),
            ],
            "local_state": os.path.join(
                os.environ["USERPROFILE"],
                "AppData",
                "Local",
                "Google",
                "Chrome",
                "User Data",
                "Local State",
            ),
            "display": "Google Chrome",
            "type": "chromium",
        },
        {
            "name": "edge",
            "db_paths": [
                os.path.join(
                    os.environ["USERPROFILE"],
                    "AppData",
                    "Local",
                    "Microsoft",
                    "Edge",
                    "User Data",
                    "Default",
                    "Network",
                    "Cookies",
                ),
                os.path.join(
                    os.environ["USERPROFILE"],
                    "AppData",
                    "Local",
                    "Microsoft",
                    "Edge",
                    "User Data",
                    "Default",
                    "Cookies",
                ),
            ],
            "local_state": os.path.join(
                os.environ["USERPROFILE"],
                "AppData",
                "Local",
                "Microsoft",
                "Edge",
                "User Data",
                "Local State",
            ),
            "display": "Microsoft Edge",
            "type": "chromium",
        },
        {
            "name": "brave",
            "db_paths": [
                os.path.join(
                    os.environ["USERPROFILE"],
                    "AppData",
                    "Local",
                    "BraveSoftware",
                    "Brave-Browser",
                    "User Data",
                    "Default",
                    "Network",
                    "Cookies",
                ),
                os.path.join(
                    os.environ["USERPROFILE"],
                    "AppData",
                    "Local",
                    "BraveSoftware",
                    "Brave-Browser",
                    "User Data",
                    "Default",
                    "Cookies",
                ),
            ],
            "local_state": os.path.join(
                os.environ["USERPROFILE"],
                "AppData",
                "Local",
                "BraveSoftware",
                "Brave-Browser",
                "User Data",
                "Local State",
            ),
            "display": "Brave Browser",
            "type": "chromium",
        },
        {
            "name": "vivaldi",
            "db_paths": [
                os.path.join(
                    os.environ["USERPROFILE"],
                    "AppData",
                    "Local",
                    "Vivaldi",
                    "User Data",
                    "Default",
                    "Network",
                    "Cookies",
                ),
                os.path.join(
                    os.environ["USERPROFILE"],
                    "AppData",
                    "Local",
                    "Vivaldi",
                    "User Data",
                    "Default",
                    "Cookies",
                ),
            ],
            "local_state": os.path.join(
                os.environ["USERPROFILE"], "AppData", "Local", "Vivaldi", "User Data", "Local State"
            ),
            "display": "Vivaldi",
            "type": "chromium",
        },
        {
            "name": "opera",
            "db_paths": [
                os.path.join(
                    os.environ["USERPROFILE"],
                    "AppData",
                    "Roaming",
                    "Opera Software",
                    "Opera Stable",
                    "Network",
                    "Cookies",
                ),
                os.path.join(
                    os.environ["USERPROFILE"],
                    "AppData",
                    "Roaming",
                    "Opera Software",
                    "Opera Stable",
                    "Cookies",
                ),
            ],
            "local_state": os.path.join(
                os.environ["USERPROFILE"],
                "AppData",
                "Roaming",
                "Opera Software",
                "Opera Stable",
                "Local State",
            ),
            "display": "Opera",
            "type": "chromium",
        },
        {"name": "firefox", "type": "firefox", "display": "Mozilla Firefox"},
    ]

    # Resolve Firefox database paths dynamically if profile exists
    try:
        ff_pattern = os.path.join(
            os.environ["APPDATA"], "Mozilla", "Firefox", "Profiles", "*", "cookies.sqlite"
        )
        ff_paths = glob.glob(ff_pattern)
        if ff_paths:
            # Add to firefox entry
            for b in browsers:
                if b["type"] == "firefox":
                    b["db_paths"] = ff_paths
    except Exception:
        pass

    temp_cookie_file = os.path.join(tempfile.gettempdir(), "netscape_cookies.txt")
    total_decrypted = 0
    cookies_written = False
    primary_browser_type = None

    # Initialize cookies file
    try:
        with open(temp_cookie_file, "w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write("# This file was generated automatically by the Downloader CLI\n\n")
        cookies_written = True
    except Exception as e:
        console.print(
            f"[warning]Failed to initialize temp cookies file: {e}[/warning]", style="yellow"
        )
        return None

    for b in browsers:
        db_paths = b.get("db_paths", [])
        cookies_db_path = None
        for path in db_paths:
            if os.path.exists(path):
                cookies_db_path = path
                break

        if not cookies_db_path:
            continue

        temp_db_path = os.path.join(tempfile.gettempdir(), f"{b['name']}_cookies_temp.db")

        # Copy using native Windows CopyFileW API to bypass browser locked-file locks, fallback to shutil
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
                # If copying fails due to a locked file (Sharing Violation / Permission Denied),
                # we can connect directly to the locked database in read-only and no-lock mode.
                pass

        try:
            decrypted_count = 0
            rows = []

            if copied:
                conn = sqlite3.connect(temp_db_path)
                cursor = conn.cursor()
                if b["type"] == "chromium":
                    cursor.execute(
                        "SELECT host_key, name, path, is_secure, expires_utc, encrypted_value FROM cookies"
                    )
                else:
                    cursor.execute(
                        "SELECT host, name, path, isSecure, expiry, value FROM moz_cookies"
                    )
                rows = cursor.fetchall()
                conn.close()
                if os.path.exists(temp_db_path):
                    os.remove(temp_db_path)
            else:
                # Direct URI connection to locked database bypassing locks
                uri_path = cookies_db_path.replace("\\", "/")
                # For Windows drive letters, ensure we have the correct URI prefix
                if not uri_path.startswith("/"):
                    uri_path = "/" + uri_path
                uri = f"file://{uri_path}?mode=ro&nolock=1"
                try:
                    conn = sqlite3.connect(uri, uri=True)
                    cursor = conn.cursor()
                    if b["type"] == "chromium":
                        cursor.execute(
                            "SELECT host_key, name, path, is_secure, expires_utc, encrypted_value FROM cookies"
                        )
                    else:
                        cursor.execute(
                            "SELECT host, name, path, isSecure, expiry, value FROM moz_cookies"
                        )
                    rows = cursor.fetchall()
                    conn.close()
                except Exception as db_err:
                    console.print(
                        f"[dim]Failed direct connection to locked database {b['display']}: {db_err}[/dim]"
                    )
                    continue

            # --- Chromium-based Browser Parsing ---
            if b["type"] == "chromium":
                key = get_browser_master_key(b["name"])
                with open(temp_cookie_file, "a", encoding="utf-8") as f:
                    for host_key, name, path, is_secure, expires_utc, encrypted_value in rows:
                        decrypted_val = decrypt_chrome_cookie(encrypted_value, key)
                        if decrypted_val:
                            is_subdomain = "TRUE" if host_key.startswith(".") else "FALSE"
                            secure_str = "TRUE" if is_secure else "FALSE"
                            expiry_sec = 0
                            if expires_utc > 0:
                                if expires_utc > 20000000000:
                                    expiry_sec = int((expires_utc / 1000000) - 11644473600)
                                else:
                                    expiry_sec = int(expires_utc)

                            f.write(
                                f"{host_key}\t{is_subdomain}\t{path}\t{secure_str}\t{expiry_sec}\t{name}\t{decrypted_val}\n"
                            )
                            decrypted_count += 1

            # --- Firefox-based Browser Parsing (Plaintext SQLite) ---
            elif b["type"] == "firefox":
                with open(temp_cookie_file, "a", encoding="utf-8") as f:
                    for host, name, path, is_secure_val, expiry, value in rows:
                        if value:
                            is_subdomain = "TRUE" if host.startswith(".") else "FALSE"
                            secure_str = "TRUE" if is_secure_val else "FALSE"
                            f.write(
                                f"{host}\t{is_subdomain}\t{path}\t{secure_str}\t{expiry}\t{name}\t{value}\n"
                            )
                            decrypted_count += 1

            conn.close()
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)

            if decrypted_count > 0:
                console.print(
                    f"[success]Successfully loaded {decrypted_count} cookies from {b['display']}.[/success]"
                )
                total_decrypted += decrypted_count
                if not primary_browser_type:
                    primary_browser_type = b["type"]

        except Exception as e:
            console.print(f"[dim]Failed to extract {b['display']} cookies: {e}[/dim]")
            if os.path.exists(temp_db_path):
                try:
                    os.remove(temp_db_path)
                except Exception:
                    pass

    if total_decrypted > 0:
        return temp_cookie_file, primary_browser_type

    if cookies_written and os.path.exists(temp_cookie_file):
        try:
            os.remove(temp_cookie_file)
        except Exception:
            pass

    console.print(
        "[warning]No browser cookies (Chrome, Edge, Brave, Vivaldi, Opera, Firefox) could be extracted. Program will continue without browser sessions.[/warning]",
        style="yellow",
    )
    return None
