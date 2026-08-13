import sys
from curl_cffi import requests

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.dailymotion.com/",
    "Origin": "https://www.dailymotion.com"
}

# 1. Fetch Dailymotion metadata for Perfect World Ep 228
video_id = "x9or71s"
auth = "k6JNTDpO47cP6mDDQTm"
meta_url = f"https://www.dailymotion.com/player/metadata/video/{video_id}?auth={auth}&embedder=https%3A%2F%2Fanimecube.live%2F"

r1 = requests.get(meta_url, headers=headers, impersonate="chrome120")
print("Meta status:", r1.status_code)
data = r1.json()
ad_url = data.get("advertising", {}).get("ad_url")
print("ad_url:", ad_url)

if ad_url:
    # 2. Fetch the m3u8 playlist using curl_cffi
    r2 = requests.get(ad_url, headers=headers, impersonate="chrome120")
    print("\nm3u8 Status:", r2.status_code)
    print("m3u8 Content-Type:", r2.headers.get("content-type"))
    print("m3u8 text snippet:\n", r2.text[:500])
