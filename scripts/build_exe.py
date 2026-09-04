"""Automated PyInstaller build script for TeamTrau Anime Downloader Native Windows 11 EXE."""

import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
ENTRY_POINT = SRC_DIR / "ui" / "app_window.py"
DIST_DIR = BASE_DIR / "dist"
BUILD_DIR = BASE_DIR / "build"


def build_windows_exe(onefile: bool = False):
    """Execute PyInstaller build process."""
    print("============================================================")
    print(" BUILDING TEAMTRAU ANIME DOWNLOADER NATIVE WINDOWS 11 .EXE  ")
    print("============================================================")
    print(f"Target: {'Single-File EXE' if onefile else 'Single-Folder Distribution'}")
    print(f"Entry point: {ENTRY_POINT}")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name=TeamTrauDownloader",
        "--windowed",  # No console window
        f"--paths={SRC_DIR}",
        # Collect static UI assets
        f"--add-data={SRC_DIR / 'ui' / 'index.html'};ui",
        f"--add-data={SRC_DIR / 'ui' / 'assets'};ui/assets",
        f"--add-data={SRC_DIR / 'ui' / 'tokens'};ui/tokens",
        # Include hidden imports for webview and core
        "--hidden-import=webview",
        "--hidden-import=webview.platforms.winforms",
        "--hidden-import=clr_loader",
        "--hidden-import=sqlite3",
        "--hidden-import=curl_cffi",
        "--hidden-import=cryptography",
        f"--icon={SRC_DIR / 'ui' / 'assets' / 'icon.ico'}",
    ]

    # Include ffmpeg if present
    ffmpeg_dir = BASE_DIR / "ffmpeg"
    if ffmpeg_dir.exists():
        cmd.append(f"--add-data={ffmpeg_dir};ffmpeg")

    # Mode: onefile vs onedir
    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    cmd.append(str(ENTRY_POINT))

    print(f"Running command: {' '.join(cmd[:6])} ...")
    result = subprocess.run(cmd, cwd=str(BASE_DIR))

    if result.returncode == 0:
        print("\n[SUCCESS] PyInstaller build completed successfully!")
        if onefile:
            target_exe = DIST_DIR / "TeamTrauDownloader.exe"
            print(f"[OUTPUT] Executable file: {target_exe}")
        else:
            target_folder = DIST_DIR / "TeamTrauDownloader"
            target_exe = target_folder / "TeamTrauDownloader.exe"
            print(f"[OUTPUT] Application folder: {target_folder}")
            print(f"[OUTPUT] Main executable: {target_exe}")

        print("============================================================")
        return 0
    else:
        print(f"\n[ERROR] PyInstaller build failed with exit code {result.returncode}")
        return result.returncode


if __name__ == "__main__":
    is_onefile = "--onefile" in sys.argv
    sys.exit(build_windows_exe(onefile=is_onefile))
