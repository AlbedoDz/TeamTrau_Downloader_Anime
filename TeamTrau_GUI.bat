@echo off
setlocal enabledelayedexpansion
title TeamTrau Anime Downloader GUI Launcher
cls

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

echo [OK] Su dung Python: %PY_EXE%
echo [INFO] Dang khoi dong Web GUI Server tai http://127.0.0.1:8765/ ...
echo.

:: Launch UI Server in background window
start "TeamTrau Web Server Engine" /min "%PY_EXE%" src\ui\server.py 127.0.0.1 8765

:: Wait 1.5 seconds for server initialization
timeout /t 2 /nobreak >nul

:: Attempt to open in Microsoft Edge App Mode (Frameless Desktop UI)
where msedge >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo [OK] Khoi chay ung dung Desktop App qua Microsoft Edge...
    start msedge.exe --app="http://127.0.0.1:8765/" --window-size=1160,820
) else (
    echo [OK] Mo giao dien tren trinh duyet mac dinh...
    start http://127.0.0.1:8765/
)

echo.
echo ============================================================
echo Giao dien TeamTrau Downloader da duoc khoi chay thanh cong!
echo Ban co the thu nho cua so nay hoac dong lai khi dung xong.
echo ============================================================
echo.
pause
