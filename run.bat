@echo off
setlocal enabledelayedexpansion
title Unified Multi-Site Anime Downloader Launcher
cls

cd /d "%~dp0"

if not exist ".venv" (
    echo [ERROR] Virtual environment .venv not found.
    echo Please run setup_env_py.bat first to set up the environment.
    pause
    exit /b 1
)

:: If direct URL parameter is passed via command line, execute auto-detect mode
if not "%~1"=="" (
    .venv\Scripts\python.exe run_app.py -u "%~1" %2 %3 %4 %5 %6 %7 %8 %9
    echo.
    pause
    exit /b !ERRORLEVEL!
)

:MENU
cls
echo ============================================================
echo      TEAMTRAU UNIFIED MULTI-SITE ANIME DOWNLOADER
echo ============================================================
echo.
echo Select Site Download Module:
echo.
echo   [1] AnimeCube Module (animecube.live)
echo   [2] AniKoto Module   (anikototv.to)
echo   [3] Auto-Detect Site (Enter any supported Anime URL)
echo   [0] Exit Launcher
echo.
set /p LAUNCHER_CHOICE="Enter Choice [1]: "
if not defined LAUNCHER_CHOICE set LAUNCHER_CHOICE=1

if "!LAUNCHER_CHOICE!"=="1" (
    call run_animecube.bat
    goto :MENU
)
if "!LAUNCHER_CHOICE!"=="2" (
    call run_anikoto.bat
    goto :MENU
)
if "!LAUNCHER_CHOICE!"=="3" goto :AUTO_DETECT
if "!LAUNCHER_CHOICE!"=="0" exit /b 0

:AUTO_DETECT
echo.
echo ------------------------------------------------------------
echo  AUTO-DETECT DOWNLOAD MODE
echo ------------------------------------------------------------
set /p ANIME_URL="Enter Anime URL: "
if not defined ANIME_URL (
    echo [ERROR] Anime URL cannot be empty!
    pause
    goto :MENU
)

for /f "delims=" %%I in ("!ANIME_URL!") do set ANIME_URL=%%~I

set /p EPISODES="Episode Range (e.g. all, 1-5, SP) [all]: "
if not defined EPISODES set EPISODES=all

set /p SUB_LANG="Subtitle Language (e.g. en, vi) [en]: "
if not defined SUB_LANG set SUB_LANG=en

set /p OUTPUT_DIR="Output Directory [.\downloads]: "
if not defined OUTPUT_DIR set OUTPUT_DIR=.\downloads

echo.
.venv\Scripts\python.exe run_app.py -u "!ANIME_URL!" -e "!EPISODES!" -l "!SUB_LANG!" -o "!OUTPUT_DIR!"
echo.
pause
goto :MENU
