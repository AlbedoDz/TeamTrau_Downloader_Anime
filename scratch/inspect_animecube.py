import sys, json, re
from curl_cffi import requests

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://animecube.live/"
}

r = requests.get("https://animecube.live/anime/the-demon-hunter", headers=headers, impersonate="chrome120")
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

# Extract primaryTabs array structure
# Look for "primaryTabs":[{...}] or similar
pt_match = re.search(r'"primaryTabs"\s*:\s*(\[.*?\])\s*,\s*"updateDays"', full_str)
if pt_match:
    primary_tabs = json.loads(pt_match.group(1))
    print("Parsed primaryTabs count:", len(primary_tabs))
    total_eps = 0
    for ptab in primary_tabs:
        p_id = ptab.get("id", "primary-1")
        p_name = ptab.get("customName") or ptab.get("title") or p_id
        for season in ptab.get("seasons", []):
            s_id = season.get("id", "tab-1")
            s_name = season.get("title") or s_id
            eps = season.get("episodes", [])
            print(f"PrimaryTab '{p_name}' ({p_id}) -> Season '{s_name}' ({s_id}): {len(eps)} episodes")
            total_eps += len(eps)
    print("Total parsed episodes:", total_eps)
else:
    print("primaryTabs match not found")
