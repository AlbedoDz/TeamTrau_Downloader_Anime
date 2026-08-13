import sys, json, re
from curl_cffi import requests

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://animecube.live/",
    "Origin": "https://animecube.live"
}

vids = [
    ("x9q0yw0", "k7IN2pETI8HhhVDMOsw"),
    ("x9nm6ji", "k3jihnvMLd02FHDvP5A"),
    ("x9ps1gs", "k51PdThRbOubKUDL45K")
]

for video_id, private_id in vids:
    auth_param = f"?auth={private_id}" if private_id else ""
    meta_url = f"https://www.dailymotion.com/player/metadata/video/{video_id}{auth_param}&embedder=https%3A%2F%2Fanimecube.live%2F"
    r = requests.get(meta_url, headers=headers, impersonate="chrome120")
    print(f"\n--- Video {video_id} --- Status: {r.status_code}")
    data = r.json()
    if "error" in data:
        print("  Error code:", data["error"].get("code"))
    else:
        print("  Title:", data.get("title"))
        ad_url = data.get("advertising", {}).get("ad_url")
        print("  ad_url:", ad_url[:100] if ad_url else "None")
