@echo off
title Update Project Libraries & Tools
cls

cd /d "%~dp0"

echo ============================================================
echo      UPDATE PROJECT LIBRARIES & TOOLS (Latest Versions)
echo ============================================================
echo.

:: ------------------------------------------------------------
:: STEP 1: DETECT UV
:: ------------------------------------------------------------
echo [1/3] Detecting package manager (uv)...
set UV_CMD=uv
where uv >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo - Global 'uv' detected.
    goto UPDATE_LIBRARIES
)

if exist "uv.exe" (
    echo - Local 'uv.exe' detected.
    set UV_CMD=.\uv.exe
    goto UPDATE_LIBRARIES
)

echo [ERROR] 'uv' package manager not found!
echo Please run setup_portable.bat first to set up the environment.
pause
exit /b 1

:: ------------------------------------------------------------
:: STEP 2: UPDATE PYTHON LIBRARIES
:: ------------------------------------------------------------
:UPDATE_LIBRARIES
echo.
echo [2/3] Updating Python libraries to latest...
%UV_CMD% pip install --upgrade -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Failed to upgrade some Python packages.
) else (
    echo - Python packages upgraded successfully.
)
echo.

:: ------------------------------------------------------------
:: STEP 3: UPDATE YT-DLP
:: ------------------------------------------------------------
echo [3/3] Checking and updating yt-dlp...
if not exist "yt-dlp" mkdir "yt-dlp"
if exist "yt-dlp\yt-dlp.exe" (
    echo - Running internal yt-dlp self-update...
    yt-dlp\yt-dlp.exe -U
) else (
    echo - yt-dlp not found locally. Downloading latest release...
    where curl.exe >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        curl.exe -L -o "yt-dlp\yt-dlp.exe" "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
    ) else (
        powershell -NoProfile -Command "Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe' -OutFile 'yt-dlp/yt-dlp.exe'"
    )
)
if exist "yt-dlp\yt-dlp.exe" (
    echo - yt-dlp is up to date.
) else (
    echo [WARNING] Failed to download/update yt-dlp.
)
echo.

echo ============================================================
echo      ALL LIBRARIES AND TOOLS UPDATED SUCCESSFULLY!
echo ============================================================
echo.
pause
exit /b 0
