@echo off
setlocal enabledelayedexpansion
title TeamTrau Anime Downloader - Windows 11 EXE Builder
cls

cd /d "%~dp0"

echo ============================================================
echo   TEAMTRAU ANIME DOWNLOADER - NATIVE EXE BUILD PIPELINE
echo ============================================================
echo.

:: Detect Python executable
set "PY_EXE="
if exist ".venv\Scripts\python.exe" (
    set "PY_EXE=.venv\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if !ERRORLEVEL! equ 0 (
        set "PY_EXE=python"
    )
)

if "%PY_EXE%"=="" (
    echo [ERROR] Khong tim thay Python trong moi truong!
    pause
    exit /b 1
)

echo [OK] Su dung Python: %PY_EXE%
echo [INFO] Dang kiem tra va cai dat dependencies build neu thieu...
"%PY_EXE%" -m pip install pywebview pyinstaller --quiet

echo.
echo [MENU] Chon che do dong goi .EXE:
echo   [1] Single-Folder (De xuat: Khoi dong tuc thi duoi 0.5s, on dinh 100%%)
echo   [2] Single-File (1 file .EXE duy nhat)
echo.
set /p "BUILD_CHOICE=Nhap lua chon cua ban (1 hoac 2, mac dinh 1): "

if "%BUILD_CHOICE%"=="2" (
    echo [INFO] Dang build ban Single-File EXE...
    "%PY_EXE%" scripts\build_exe.py --onefile
) else (
    echo [INFO] Dang build ban Single-Folder Distribution...
    "%PY_EXE%" scripts\build_exe.py
)

echo.
echo ============================================================
echo Qua trinh build da ket thuc. Kiem tra thu muc 'dist'.
echo ============================================================
echo.
pause
