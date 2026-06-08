@echo off
title Anime Downloader CLI Bootstrapper
cls

:: Change to the directory where this .bat file lives (fixes double-click from Explorer)
cd /d "%~dp0"

:: Check if the virtual environment exists
if not exist ".venv" (
    echo [ERROR] Virtual environment .venv not found.
    echo Please run setup_env_py.bat first to set up the environment.
    pause
    exit /b 1
)

:: If arguments are passed, run directly in CLI mode forwarding all arguments
if not "%~1"=="" (
    .venv\Scripts\python.exe main.py %*
    echo.
    pause
    exit /b %ERRORLEVEL%
)

:: ============================================================
::   INTERACTIVE MODE
:: ============================================================
echo ============================================================
echo      ANIME SUBTITLE AND VIDEO BATCH DOWNLOADER
echo ============================================================
echo.
echo  Supported site: https://anikototv.to
echo  URL format   : https://anikototv.to/watch/^<anime-slug^>
echo.
echo Please answer the following prompts. Leave blank to use defaults.
echo.

set /p ANIME_URL="[1/5] Enter Anime URL: "
if "%ANIME_URL%"=="" (
    echo [ERROR] Anime URL cannot be empty!
    pause
    exit /b 1
)

set /p EPISODES="[2/5] Episode Range (e.g., all, 1-5, 3,5,10-12) [all]: "
if "%EPISODES%"=="" set EPISODES=all

set /p SUB_LANG="[3/5] Subtitle Language (e.g. en, vi) [en]: "
if "%SUB_LANG%"=="" set SUB_LANG=en

set /p OUTPUT_DIR="[4/5] Output Directory [.\downloads]: "
if "%OUTPUT_DIR%"=="" set OUTPUT_DIR=.\downloads

echo.
echo [5/5] Select Download Mode:
echo   [1] Subtitles Only  (fast, no ffmpeg needed)
echo   [2] Videos Only
echo   [3] Both Subtitles + Videos  (default)
echo.
set /p MODE_CHOICE="Enter Choice (1/2/3) [3]: "
if "%MODE_CHOICE%"=="" set MODE_CHOICE=3

set EXTRA_ARGS=
if "%MODE_CHOICE%"=="1" set EXTRA_ARGS=--sub-only
if "%MODE_CHOICE%"=="2" set EXTRA_ARGS=--video-only

echo.
echo ------------------------------------------------------------
echo  Starting download...
echo  URL      : %ANIME_URL%
echo  Episodes : %EPISODES%
echo  Language : %SUB_LANG%
echo  Output   : %OUTPUT_DIR%
echo  Mode     : %EXTRA_ARGS%
echo ------------------------------------------------------------
echo.

.venv\Scripts\python.exe main.py -u "%ANIME_URL%" -e "%EPISODES%" -l "%SUB_LANG%" -o "%OUTPUT_DIR%" %EXTRA_ARGS%

echo.
echo ============================================================
echo  Done! Press any key to exit.
echo ============================================================
pause
