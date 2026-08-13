@echo off
setlocal enabledelayedexpansion
title AniKoto Downloader CLI - anikototv.to
cls

cd /d "%~dp0"

if not exist ".venv" (
    echo [ERROR] Virtual environment .venv not found.
    echo Please run setup_env_py.bat first to set up the environment.
    pause
    exit /b 1
)

:: If command-line arguments are provided, execute directly
if not "%~1"=="" (
    set "FIRST_ARG=%~1"
    if "!FIRST_ARG:~0,1!"=="-" (
        .venv\Scripts\python.exe run_app.py %*
    ) else (
        .venv\Scripts\python.exe run_app.py -u %*
    )
    echo.
    pause
    exit /b !ERRORLEVEL!
)

echo ============================================================
echo      ANIKOTO.TO - BATCH ANIME DOWNLOADER MODULE
echo ============================================================
echo.
echo Target Site : https://anikototv.to
echo Example URL : https://anikototv.to/watch/the-villager-of-level-999/ep-6
echo.
echo Please answer the following prompts (Press Enter for defaults).
echo.

:PROMPT_URL
set "ANIME_URL="
set /p ANIME_URL="[1/7] Enter AniKoto Watch/Anime URL: "
if not defined ANIME_URL (
    echo [ERROR] Anime URL cannot be empty!
    goto PROMPT_URL
)
for /f "delims=" %%I in ("!ANIME_URL!") do set ANIME_URL=%%~I

echo.
set /p EPISODES="[2/7] Episode Range (e.g. all, 1-5, 6) [all]: "
if not defined EPISODES set EPISODES=all

echo.
echo [3/7] Subtitle Language:
echo   [1] English (en) - Default
echo   [2] Spanish / Espanol - Latin America Priority (es)
echo   [3] Vietnamese / Tieng Viet (vi)
echo   [4] Custom / Enter Language Code
echo.
set /p LANG_CHOICE="Enter Choice (1/2/3/4) [1]: "
if not defined LANG_CHOICE set LANG_CHOICE=1

set SUB_LANG=en
if "!LANG_CHOICE!"=="2" set SUB_LANG=es
if "!LANG_CHOICE!"=="3" set SUB_LANG=vi
if "!LANG_CHOICE!"=="4" (
    set /p CUSTOM_LANG="    Enter custom language code (e.g. fr, de): "
    if defined CUSTOM_LANG set SUB_LANG=!CUSTOM_LANG!
)

echo.
echo [4/7] Episode Naming Format:
echo   [1] Simple (e.g. Anime Title - S01E06.mp4 / .srt) - Default
echo   [2] TVDB Compliant (e.g. Anime Title - S01E06.en.srt)
echo   [3] AniKoto Original
echo.
set /p NAMING_CHOICE="Enter Choice (1/2/3) [1]: "
if not defined NAMING_CHOICE set NAMING_CHOICE=1

set NAMING_FORMAT=simple
if "!NAMING_CHOICE!"=="2" set NAMING_FORMAT=tvdb
if "!NAMING_CHOICE!"=="3" set NAMING_FORMAT=anikoto

echo.
set /p OUTPUT_DIR="[5/7] Output Directory [.\downloads]: "
if not defined OUTPUT_DIR set OUTPUT_DIR=.\downloads

echo.
echo [6/7] Select Download Mode:
echo   [1] Subtitles Only (Fast)
echo   [2] Videos Only
echo   [3] Both Subtitles + Videos (Default)
echo.
set /p MODE_CHOICE="Enter Choice (1/2/3) [3]: "
if not defined MODE_CHOICE set MODE_CHOICE=3

set EXTRA_ARGS=
if "!MODE_CHOICE!"=="1" set EXTRA_ARGS=--sub-only
if "!MODE_CHOICE!"=="2" set EXTRA_ARGS=--video-only

echo.
echo [7/7] Advanced Options:
set /p INTERACTIVE_CHOICE="  - Enable Interactive Server Selection (y/n) [n]: "
if /i "!INTERACTIVE_CHOICE:~0,1!"=="y" (
    set EXTRA_ARGS=!EXTRA_ARGS! --interactive
)

set /p PROXY_URL="  - Optional Proxy URL (Enter for none): "
if defined PROXY_URL (
    for /f "delims=" %%I in ("!PROXY_URL!") do set PROXY_URL=%%~I
    set EXTRA_ARGS=!EXTRA_ARGS! --proxy "!PROXY_URL!"
)

set /p SNIFFER_CHOICE="  - Enable Playwright Browser Network Sniffer (y/n) [n]: "
if /i "!SNIFFER_CHOICE:~0,1!"=="y" (
    set EXTRA_ARGS=!EXTRA_ARGS! --use-browser-sniffer
)

echo.
echo ------------------------------------------------------------
echo  Starting AniKoto Download...
echo  URL      : !ANIME_URL!
echo  Episodes : !EPISODES!
echo  Language : !SUB_LANG!
echo  Naming   : !NAMING_FORMAT!
echo  Output   : !OUTPUT_DIR!
echo  Extra    : !EXTRA_ARGS!
echo ------------------------------------------------------------
echo.

.venv\Scripts\python.exe run_app.py -u "!ANIME_URL!" -e "!EPISODES!" -l "!SUB_LANG!" --naming-format "!NAMING_FORMAT!" -o "!OUTPUT_DIR!" !EXTRA_ARGS!

echo.
echo ============================================================
echo  Download session finished! Press any key to return/exit.
echo ============================================================
pause
