@echo off
setlocal enabledelayedexpansion
title TeamTrau Anime Downloader GUI Launcher
cls

:: Ensure UTF-8 Console and Python Encoding
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

cd /d "%~dp0"

echo ============================================================
echo      TEAMTRAU ANIME DOWNLOADER - WEB GUI LAUNCHER v2.0+
echo ============================================================
echo.

:: Detect Python executable
set "PY_EXE="
if exist ".venv\Scripts\python.exe" (
    set "PY_EXE=.venv\Scripts\python.exe"
) else if exist "python\python.exe" (
    set "PY_EXE=python\python.exe"
) else (
    where python >nul 2>nul
    if !ERRORLEVEL! equ 0 (
        set "PY_EXE=python"
    ) else (
        where py >nul 2>nul
        if !ERRORLEVEL! equ 0 (
            set "PY_EXE=py"
        )
    )
)

if "%PY_EXE%"=="" (
    echo [ERROR] Khong tim thay Python tren may tinh cua ban!
    echo Vui long chay 'bootstrap.bat' de tu dong khoi tao moi truong Python Portable.
    echo.
    pause
    exit /b 1
)
:: Priority 1: Check if compiled Native EXE exists
if exist "dist\TeamTrauDownloader\TeamTrauDownloader.exe" (
    echo [OK] Phat hien ban Native EXE tai dist\TeamTrauDownloader\TeamTrauDownloader.exe
    echo [INFO] Dang khoi chay TeamTrau Downloader Native Windows 11...
    start "" "dist\TeamTrauDownloader\TeamTrauDownloader.exe"
    exit /b 0
)

if exist "dist\TeamTrauDownloader.exe" (
    echo [OK] Phat hien ban Single-File EXE tai dist\TeamTrauDownloader.exe
    echo [INFO] Dang khoi chay TeamTrau Downloader Native Windows 11...
    start "" "dist\TeamTrauDownloader.exe"
    exit /b 0
)

:: Priority 2: Launch Native App Window via pywebview / app_window.py
echo [OK] Su dung Python: %PY_EXE%
echo [INFO] Dang khoi dong TeamTrau Native Desktop Window...
echo.

"%PY_EXE%" src\ui\app_window.py
exit /b %ERRORLEVEL%

echo.
echo ============================================================
echo Giao dien TeamTrau Downloader da duoc khoi chay thanh cong!
echo Ban co the thu nho cua so nay hoac dong lai khi dung xong.
echo ============================================================
echo.
pause
