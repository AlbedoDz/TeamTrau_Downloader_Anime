import os
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_ZIP = BASE_DIR / "TeamTrau_Downloader_Anime_Portable_v2.0.zip"

# Clean whitelist of top-level files and directories to include
INCLUDE_TOP_LEVEL_DIRS = {
    "src",
    "ffmpeg",
    "yt-dlp",
    "Script",
}

INCLUDE_TOP_LEVEL_FILES = {
    "TeamTrau_GUI.bat",
    "run.bat",
    "run_anikoto.bat",
    "run_allwish.bat",
    "run_animesuge.bat",
    "run_animecube.bat",
    "run_app.py",
    "bootstrap.bat",
    "bootstrap.ps1",
    "clean.bat",
    "requirements.txt",
    "pyproject.toml",
    "README.md",
}

EXCLUSIONS_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "joyful_babbage.egg-info",
}

EXCLUSIONS_EXTENSIONS = {
    ".pyc",
    ".log",
    ".tmp",
    ".zip",
    ".mp4",
    ".mkv",
    ".ts",
}


def create_portable_bundle():
    print(f"Creating portable zip bundle: {OUTPUT_ZIP.name}...")
    file_count = 0
    total_uncompressed_bytes = 0

    if OUTPUT_ZIP.exists():
        try:
            OUTPUT_ZIP.unlink()
        except Exception:
            pass

    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Add explicitly whitelisted top-level files
        for filename in INCLUDE_TOP_LEVEL_FILES:
            file_path = BASE_DIR / filename
            if file_path.exists() and file_path.is_file():
                zf.write(file_path, arcname=filename)
                file_count += 1
                total_uncompressed_bytes += file_path.stat().st_size

        # 2. Add whitelisted directories recursively
        for dirname in INCLUDE_TOP_LEVEL_DIRS:
            dir_path = BASE_DIR / dirname
            if not dir_path.exists() or not dir_path.is_dir():
                continue

            for root, dirs, files in os.walk(dir_path):
                # Filter out excluded directories
                dirs[:] = [
                    d
                    for d in dirs
                    if d not in EXCLUSIONS_DIR_NAMES and not d.endswith(".egg-info")
                ]

                for file in files:
                    file_path = Path(root) / file
                    if file_path.suffix in EXCLUSIONS_EXTENSIONS:
                        continue

                    rel_path = file_path.relative_to(BASE_DIR)
                    zf.write(file_path, arcname=str(rel_path))
                    file_count += 1
                    total_uncompressed_bytes += file_path.stat().st_size

    zip_size = OUTPUT_ZIP.stat().st_size
    print("=" * 60)
    print(" PORTABLE BUNDLE PACKAGE SUMMARY")
    print("=" * 60)
    print(f" Output Archive : {OUTPUT_ZIP.name}")
    print(f" Total Files    : {file_count}")
    print(f" Raw Size       : {total_uncompressed_bytes / (1024 * 1024):.2f} MB")
    print(f" Compressed Size: {zip_size / (1024 * 1024):.2f} MB")
    print("=" * 60)
    print(" Hoan tat dong goi! San sang chia se cho moi may tinh Windows.")


if __name__ == "__main__":
    create_portable_bundle()
