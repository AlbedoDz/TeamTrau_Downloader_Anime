import os

import typer

from downloader.core import BatchDownloader, is_ffmpeg_installed
from downloader.utils import console

app = typer.Typer(
    help="Automated Batch Anime Subtitle and Video Downloader",
    add_completion=False,
)


@app.command()
def download(
    url: str | None = typer.Option(
        None,
        "--url",
        "-u",
        help="The URL of the anime page on the supported streaming site (e.g. anikototv.to).",
    ),
    file: str | None = typer.Option(
        None,
        "--file",
        "-f",
        help="Path to a text file containing anime page URLs (one URL per line).",
    ),
    episodes: str = typer.Option(
        "all",
        "--episodes",
        "-e",
        help="Range or list of episodes to download (e.g., 'all', '1-5', '3,5,10-12').",
    ),
    lang: str = typer.Option(
        "en",
        "--lang",
        "-l",
        help="Language filter for subtitles (e.g. 'en', 'english', 'vietnamese').",
    ),
    output: str = typer.Option(
        ".",
        "--output",
        "-o",
        help="Output directory where downloaded anime folders will be saved.",
    ),
    sub_only: bool = typer.Option(
        False,
        "--sub-only",
        help="Only download subtitles, skip videos.",
    ),
    video_only: bool = typer.Option(
        False,
        "--video-only",
        help="Only download videos, skip subtitles.",
    ),
    delay: str = typer.Option(
        "3-7",
        "--delay",
        help="Randomized delay range in seconds between episode downloads (e.g., '3-7').",
    ),
):
    # 1. Validation: Either URL or File
    if not url and not file:
        console.print(
            "[error]Error: You must specify either --url (-u) or --file (-f).[/error]",
            style="red",
        )
        raise typer.Exit(code=1)

    # 2. Dependency Pre-check: Check if ffmpeg is installed if video download is requested
    if not sub_only and not is_ffmpeg_installed():
        console.print(
            "[error]ERROR: ffmpeg is not installed or not in system PATH![/error]\n"
            "To download videos (HLS/m3u8), ffmpeg is strictly required.\n"
            "Please install ffmpeg or run this script with '--sub-only' "
            "if you only want subtitles.",
            style="red",
        )
        raise typer.Exit(code=1)

    # 3. Parse delay range
    try:
        delay_min, delay_max = map(float, delay.split("-"))
        if delay_min < 0 or delay_max < delay_min:
            raise ValueError
        delay_range = (delay_min, delay_max)
    except Exception:
        console.print(
            f"[warning]Invalid delay format '{delay}'. Using default range (3-7s).[/warning]",
            style="yellow",
        )
        delay_range = (3.0, 7.0)

    # 4. Read input URLs
    urls = []
    if url:
        urls.append(url.strip())
    elif file:
        if not os.path.exists(file):
            console.print(f"[error]Error: File not found at '{file}'[/error]", style="red")
            raise typer.Exit(code=1)
        with open(file, encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str and not line_str.startswith("#"):
                    urls.append(line_str)

    if not urls:
        console.print("[error]No valid URLs found to process.[/error]", style="red")
        raise typer.Exit(code=1)

    # 5. Run downloader
    console.print("[bold green]Starting batch download process...[/bold green]")
    downloader = BatchDownloader(output_dir=output, delay_range=delay_range)

    try:
        for idx, target_url in enumerate(urls):
            console.print(
                f"\n[bold yellow]=== Processing Anime {idx + 1}/{len(urls)}: "
                f"{target_url} ===[/bold yellow]"
            )
            try:
                downloader.download_anime(
                    anime_url=target_url,
                    episode_range=episodes,
                    lang=lang,
                    sub_only=sub_only,
                    video_only=video_only,
                )
            except Exception as e:
                console.print(
                    f"[error]Error processing anime {target_url}: {e}[/error]", style="red"
                )
    finally:
        downloader.cleanup()

    console.print("\n[bold green]=== All done! ===[/bold green]")


def main():
    app()


if __name__ == "__main__":
    main()
