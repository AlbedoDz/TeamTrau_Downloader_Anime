@echo off
setlocal enabledelayedexpansion
title AnimeCube Downloader CLI - animecube.live
cls

:: Change directory to script folder
cd /d "%~dp0"

:: Check virtual environment
if not exist ".venv" (
    echo [ERROR] Virtual environment .venv not found.
    echo Please run setup_env_py.bat first to set up the environment.
    pause
    exit /b 1
)

:: If URL argument is provided via command line, execute directly
if not "%~1"=="" (
    .venv\Scripts\python.exe run_app.py -u "%~1" %2 %3 %4 %5 %6 %7 %8 %9
    echo.
    pause
    exit /b !ERRORLEVEL!
)

:: ============================================================
::   ANIMECUBE MODULE INTERACTIVE MENU
:: ============================================================
echo ============================================================
echo      ANIMECUBE.LIVE - BATCH ANIME DOWNLOADER MODULE
echo ============================================================
echo.
echo Target Site : https://animecube.live
echo Example URL : https://animecube.live/anime/ling-cage?season=tab-1^&episode=ling-cage-tab-1-ep-SP
echo.
echo Please answer the following prompts (Press Enter for defaults).
echo.

set /p ANIME_URL="[1/6] Enter AnimeCube URL: "
if not defined ANIME_URL (
    echo [ERROR] Anime URL cannot be empty!
    pause
    exit /b 1
)

:: Strip surrounding quotes if user entered them
for /f "delims=" %%I in ("!ANIME_URL!") do set ANIME_URL=%%~I

echo.
set /p EPISODES="[2/6] Episode Range (e.g. all, 1, 1-5, SP) [all]: "
if not defined EPISODES set EPISODES=all

set /p SUB_LANG="[3/6] Subtitle Language (e.g. en, vi) [en]: "
if not defined SUB_LANG set SUB_LANG=en

set /p OUTPUT_DIR="[4/6] Output Directory [.\downloads]: "
if not defined OUTPUT_DIR set OUTPUT_DIR=.\downloads

echo.
echo [5/6] Select Download Mode:
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
set /p INTERACTIVE_CHOICE="[6/7] Enable Interactive Server Selection (y/n) [n]: "
if /i "!INTERACTIVE_CHOICE:~0,1!"=="y" (
    set EXTRA_ARGS=!EXTRA_ARGS! --interactive
)

echo.
set /p PROXY_URL="[7/8] Optional HTTP/SOCKS5 Proxy (e.g. http://127.0.0.1:8080 or Enter for none): "
if defined PROXY_URL (
    for /f "delims=" %%I in ("!PROXY_URL!") do set PROXY_URL=%%~I
    set EXTRA_ARGS=!EXTRA_ARGS! --proxy "!PROXY_URL!"
)

echo.
set /p SNIFFER_CHOICE="[8/8] Enable Playwright Browser Network Sniffer (y/n) [n]: "
if /i "!SNIFFER_CHOICE:~0,1!"=="y" (
    set EXTRA_ARGS=!EXTRA_ARGS! --use-browser-sniffer
)

echo.
echo ------------------------------------------------------------
echo  Starting AnimeCube Download...
echo  URL      : !ANIME_URL!
echo  Episodes : !EPISODES!
echo  Language : !SUB_LANG!
echo  Output   : !OUTPUT_DIR!
echo  Extra    : !EXTRA_ARGS!
echo ------------------------------------------------------------
echo.

.venv\Scripts\python.exe run_app.py -u "!ANIME_URL!" -e "!EPISODES!" -l "!SUB_LANG!" -o "!OUTPUT_DIR!" !EXTRA_ARGS!

echo.
echo ============================================================
echo  Download session finished! Press any key to return/exit.
echo ============================================================
pause
