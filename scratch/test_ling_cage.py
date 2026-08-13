import sys, json
from curl_cffi import requests

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://animecube.live/",
    "Origin": "https://animecube.live",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
}

# Test metadata request with cross-site headers
url = "https://www.dailymotion.com/player/metadata/video/x9q0yw0?auth=k7IN2pETI8HhhVDMOsw"
r = requests.get(url, headers=headers, impersonate="chrome120")
print("Status:", r.status_code)
data = r.json()
print("Keys:", list(data.keys()))
if "error" in data:
    print("Error:", data["error"])
else:
    print("Qualities:", list(data.get("qualities", {}).keys()))
    print("Advertising ad_url:", data.get("advertising", {}).get("ad_url"))
