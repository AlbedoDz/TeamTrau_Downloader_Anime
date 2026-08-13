import sys, json
from curl_cffi import requests

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://animecube.live/"
}

# Allowed fields in Dailymotion API: id, title, embed_url, private, duration, mode
api_url = "https://api.dailymotion.com/video/x9ps6dc?fields=id,title,embed_url,private,duration,mode"
r1 = requests.get(api_url, headers=headers, impersonate="chrome120")
print("API Dailymotion Status:", r1.status_code)
print("API Response:", r1.text)
