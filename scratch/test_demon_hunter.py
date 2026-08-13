import sys, os, json, base64, hashlib, re
from curl_cffi import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://animecube.live/"
}

url = "https://animecube.live/anime/the-demon-hunter"
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
    print(f"Primary tabs count: {len(primary_tabs)}", flush=True)

    reg_url = "https://animecube.live/api/anime-sources-versions"
    reg_json = requests.get(reg_url, headers=headers, impersonate="chrome120").json()

    for ptab in primary_tabs:
        p_id = ptab.get("id")
        p_name = ptab.get("customName") or ptab.get("title")
        p_type = ptab.get("type")
        for season in ptab.get("seasons", []):
            s_id = season.get("id")
            s_name = season.get("title")
            eps = season.get("episodes", [])
            print(f"\nTab: '{p_name}' ({p_id}, type={p_type}) -> Season: '{s_name}' ({s_id}) -> {len(eps)} eps", flush=True)

            version_hash = reg_json.get("bySeason", {}).get("the-demon-hunter", {}).get(p_id, {}).get(s_id)
            print("  Version hash:", version_hash, flush=True)

            if version_hash and eps:
                # Check first 5 episodes
                for ep in eps[:5]:
                    ep_num = str(ep.get("numberDisplay") or ep.get("number") or "")
                    ep_id = ep.get("id")
                    x_obf = os.urandom(16).hex()
                    sources_url = (
                        f"https://animecube.live/api/anime/the-demon-hunter/episode/{ep_id}/sources"
                        f"?v={version_hash}&primaryTabId={p_id}&seasonId={s_id}"
                    )
                    h = {"Accept": "application/json", "X-Obf": x_obf, "Referer": "https://animecube.live/anime/the-demon-hunter"}
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

                        for s in sources_data.get("sources", []):
                            vid_id = s.get("videoId")
                            priv_id = s.get("privateId")
                            plat = s.get("platform")
                            if plat == "dailymotion" and vid_id:
                                auth_str = f"auth={priv_id}&" if priv_id else ""
                                m_url = f"https://www.dailymotion.com/player/metadata/video/{vid_id}?{auth_str}embedder=https%3A%2F%2Fanimecube.live%2F"
                                meta_res = requests.get(m_url, headers=headers, impersonate="chrome120").json()
                                err = meta_res.get("error", {}).get("code") if meta_res.get("error") else "NONE"
                                quals = meta_res.get("qualities", {})
                                print(f"  Ep {ep_num} ({ep_id}) -> Dailymotion {vid_id} -> Error: {err}, Streams: {list(quals.keys())}", flush=True)
