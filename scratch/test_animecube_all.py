import sys, os, json
sys.path.insert(0, os.path.abspath("src"))

from downloader.animecube import AnimeCubeExtractor
from downloader.utils import HttpClient

client = HttpClient()
extractor = AnimeCubeExtractor(client)

anime_list = [
    "https://animecube.live/anime/battle-through-the-heavens",
    "https://animecube.live/anime/swallowed-star",
    "https://animecube.live/anime/renegade-immortal",
    "https://animecube.live/anime/perfect-world",
    "https://animecube.live/anime/martial-universe",
    "https://animecube.live/anime/shrouding-the-heavens",
    "https://animecube.live/anime/stellar-transformations"
]

print("--- Testing AnimeCubeExtractor across popular anime titles ---")
for url in anime_list:
    slug = url.split("/")[-1]
    try:
        details = extractor.get_anime_details(url)
        eps = details.get("episodes", [])
        print(f"\nAnime: {details.get('title')} ({slug}) -> Total eps: {len(eps)}")
        if eps:
            ep1 = eps[0]
            ep_data = extractor.get_episode_data(ep1, lang="en")
            v_url = ep_data.get("video_url")
            print(f"  Ep 1 ({ep1.get('slug')}) -> Video URL: {v_url[:90] if v_url else 'None (Unavailable/Private)'}")
    except Exception as e:
        print(f"  Error on {slug}: {e}")
