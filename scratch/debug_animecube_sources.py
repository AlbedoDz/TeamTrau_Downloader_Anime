import sys, os, json, base64, hashlib, re
from curl_cffi import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

sys.path.insert(0, os.path.abspath("src"))

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://animecube.live/"
}

url = "https://animecube.live/anime/ling-cage"
r = requests.get(url, headers=headers, impersonate="chrome120")
text = r.text

pushes = re.findall(r'self\.__next_f\.push\((.*?)\)</script>', text, re.DOTALL)
full_str = ""
for p in pushes:
    try:
        data = json.loads(p)
        if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], str):
            full_str += data[1]
    except Exception:
        pass

pt_match = re.search(r'"primaryTabs"\s*:\s*(\[.*?\])\s*,\s*"updateDays"', full_str)
if pt_match:
    primary_tabs = json.loads(pt_match.group(1))
    print("Primary tabs found:", len(primary_tabs))
    for ptab in primary_tabs:
        p_id = ptab.get("id")
        p_name = ptab.get("customName") or ptab.get("title")
        for season in ptab.get("seasons", []):
            s_id = season.get("id")
            s_name = season.get("title")
            eps = season.get("episodes", [])
            print(f"\nTab '{p_name}' ({p_id}) -> Season '{s_name}' ({s_id}) -> {len(eps)} episodes")

            reg_url = "https://animecube.live/api/anime-sources-versions"
            reg_json = requests.get(reg_url, headers=headers, impersonate="chrome120").json()
            version_hash = reg_json.get("bySeason", {}).get("ling-cage", {}).get(p_id, {}).get(s_id)
            print("  Version hash:", version_hash)

            if version_hash and eps:
                for ep in eps[:3]:
                    ep_id = ep.get("id")
                    x_obf = os.urandom(16).hex()
                    sources_url = (
                        f"https://animecube.live/api/anime/ling-cage/episode/{ep_id}/sources"
                        f"?v={version_hash}&primaryTabId={p_id}&seasonId={s_id}"
                    )
                    h = {"Accept": "application/json", "X-Obf": x_obf, "Referer": "https://animecube.live/anime/ling-cage"}
                    res_json = requests.get(sources_url, headers=h, impersonate="chrome120").json()
                    enc_payload = res_json.get("d")
                    if enc_payload:
                        raw = base64.b64decode(enc_payload)
                        iv = raw[:12]
                        ciphertext = raw[12:]
                        salt = f"{x_obf}|{version_hash}".encode()
                        key = hashlib.sha256(salt).digest()
                        aesgcm = AESGCM(key)
                        decrypted_bytes = aesgcm.decrypt(iv, ciphertext, None)
                        sources_data = json.loads(decrypted_bytes.decode("utf-8"))
                        print(f"\n  Ep {ep_id} -> sources count: {len(sources_data.get('sources', []))}")
                        for s in sources_data.get("sources", []):
                            print(f"    Source: platform={s.get('platform')}, videoId={s.get('videoId')}, quality={s.get('quality')}, url={s.get('url')}")
                        print(f"    Subtitles: {sources_data.get('subtitles')}")
