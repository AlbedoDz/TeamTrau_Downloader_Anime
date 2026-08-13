import sys, json
from curl_cffi import requests

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://animecube.live/"
}

# Test a known public Dailymotion video
video_id = "x8x5v4c" # Public video
meta_url = f"https://www.dailymotion.com/player/metadata/video/{video_id}?embedder=https%3A%2F%2Fanimecube.live%2F"

r = requests.get(meta_url, headers=headers, impersonate="chrome120")
data = r.json()

print("Status:", r.status_code)
print("Title:", data.get("title"))
print("Has error:", "error" in data)
qualities = data.get("qualities", {})
print("Qualities keys:", list(qualities.keys()))

for res_name, res_list in qualities.items():
    print(f"\nResolution: {res_name}")
    for item in res_list:
        print("  Type:", item.get("type"), "-> URL:", item.get("url")[:100])
