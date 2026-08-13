import sys, json
from curl_cffi import requests

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://animecube.live/"
}

video_id = "x9or71s"
auth = "k6JNTDpO47cP6mDDQTm"
meta_url = f"https://www.dailymotion.com/player/metadata/video/{video_id}?auth={auth}&embedder=https%3A%2F%2Fanimecube.live%2F"

r = requests.get(meta_url, headers=headers, impersonate="chrome120")
data = r.json()

print("Root keys in metadata JSON:", list(data.keys()))
for k, v in data.items():
    if k != "advertising":
        v_str = str(v).encode("ascii", "replace").decode("ascii")
        print(f"  {k}: {type(v).__name__} -> {v_str[:120]}")
