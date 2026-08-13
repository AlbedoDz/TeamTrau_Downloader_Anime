from downloader.anikoto import AnikotoExtractor
from downloader.utils import HttpClient


def inspect_url(url):
    http = HttpClient()
    from downloader.utils import get_chrome_cookies_temp_file

    cookies_info = get_chrome_cookies_temp_file()
    if cookies_info:
        cookies_path, _browser_name = cookies_info
        http.load_cookies_from_file(cookies_path)

    extractor = AnikotoExtractor(http)
    details = extractor.get_anime_details(url)
    episodes = details.get("episodes", [])
    if not episodes:
        print(f"No episodes found for {url}")
        return

    ep = episodes[0]  # Inspect first episode
    print(f"\n--- URL: {url} ---")
    print(f"Episode: {ep['num']}")

    servers = extractor.get_episode_servers(ep)
    print("\nParsed servers in order of appearance:")
    for idx, s in enumerate(servers):
        print(f"  {idx + 1}. Name: {s['name']}, ID: {s['id']}, Type: {s['type']}")
        try:
            ep_data = extractor.get_episode_data(ep, "en", server_info=s)
            print(f"     Video URL: {ep_data.get('video_url')}")
            print(f"     Subtitles: {ep_data.get('subtitles')}")
        except Exception as e:
            print(f"     Error: {e}")



def main():
    urls = [
        "https://anikototv.to/watch/haibara-s-teenage-new-game-8axzw/ep-4",
    ]
    for url in urls:
        inspect_url(url)



if __name__ == "__main__":
    main()
