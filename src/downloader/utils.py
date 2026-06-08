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


console = Console()


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

    def __init__(self, impersonate="chrome120", delay_range=(2.0, 5.0)):
        self.session = requests.Session(impersonate=impersonate)
        self.delay_range = delay_range
        self.last_request_time = 0.0

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
        response = self.get(url, **kwargs)
        return BeautifulSoup(response.text, "html.parser")

    def get_json(self, url: str, **kwargs) -> dict:
        """Fetch URL and parse JSON payload."""
        response = self.get(url, **kwargs)
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


def get_chrome_cookies_temp_file() -> str | None:
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
            except Exception as e:
                console.print(f"[dim]Failed to copy {b['display']} cookies database: {e}[/dim]")
                continue

        try:
            conn = sqlite3.connect(temp_db_path)
            cursor = conn.cursor()

            decrypted_count = 0

            # --- Chromium-based Browser Parsing ---
            if b["type"] == "chromium":
                key = get_browser_master_key(b["name"])
                cursor.execute(
                    "SELECT host_key, name, path, is_secure, expires_utc, encrypted_value FROM cookies"
                )
                rows = cursor.fetchall()

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
                cursor.execute("SELECT host, name, path, isSecure, expiry, value FROM moz_cookies")
                rows = cursor.fetchall()

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

        except Exception as e:
            console.print(f"[dim]Failed to extract {b['display']} cookies: {e}[/dim]")
            if os.path.exists(temp_db_path):
                try:
                    os.remove(temp_db_path)
                except Exception:
                    pass

    if total_decrypted > 0:
        return temp_cookie_file

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
