@echo off
title Portable Python 3.11 ^& Tool Setup
cls

cd /d "%~dp0"

echo ============================================================
echo      PORTABLE SETUP BOOTSTRAPPER (Python 3.11 + Tools)
echo ============================================================
echo.
echo This script will set up a local, portable Python environment,
echo install dependencies, and download video helpers (ffmpeg/yt-dlp).
echo.

:: ------------------------------------------------------------
:: STEP 1: DETECT OR DOWNLOAD UV
:: ------------------------------------------------------------
echo [Step 1/5] Checking package manager (uv)...
set UV_CMD=uv
where uv >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo - Global 'uv' detected.
    goto SETUP_VENV
)

if exist "uv.exe" (
    echo - Local 'uv.exe' detected.
    set UV_CMD=.\uv.exe
    goto SETUP_VENV
)

echo - 'uv' not found. Downloading standalone 'uv.exe' locally...

where curl.exe >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo - Downloading uv via curl.exe...
    curl.exe -L -o uv.zip "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip"
) else (
    echo - Downloading uv via PowerShell...
    powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip' -OutFile 'uv.zip'"
)

if not exist "uv.zip" (
    echo [ERROR] Failed to download 'uv.zip'.
    echo Please make sure you have internet access.
    pause
    exit /b 1
)

echo - Extracting uv.zip...
if exist "uv_temp" rmdir /s /q "uv_temp"
mkdir "uv_temp"

where tar.exe >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo - Extracting using tar.exe...
    tar.exe -xf uv.zip -C uv_temp
) else (
    echo - Extracting using PowerShell Expand-Archive...
    powershell -NoProfile -Command "Expand-Archive -Path 'uv.zip' -DestinationPath 'uv_temp' -Force"
)

move /y "uv_temp\uv-x86_64-pc-windows-msvc\uv.exe" "." >nul 2>&1
move /y "uv_temp\uv-x86_64-pc-windows-msvc\uvx.exe" "." >nul 2>&1

if not exist "uv.exe" (
    for /r "uv_temp" %%f in (uv.exe) do (
        if exist "%%f" move /y "%%f" "." >nul 2>&1
    )
)
if not exist "uvx.exe" (
    for /r "uv_temp" %%f in (uvx.exe) do (
        if exist "%%f" move /y "%%f" "." >nul 2>&1
    )
)

if exist "uv.zip" del /f /q "uv.zip"
if exist "uv_temp" rmdir /s /q "uv_temp"

if not exist "uv.exe" (
    echo [ERROR] Failed to download or extract 'uv.exe'.
    echo Please make sure you have internet access and powershell is enabled.
    pause
    exit /b 1
)

set UV_CMD=.\uv.exe
echo - Local 'uv.exe' successfully configured!
echo.

:: ------------------------------------------------------------
:: STEP 2: CREATE PORTABLE VIRTUAL ENVIRONMENT
:: ------------------------------------------------------------
:SETUP_VENV
echo [Step 2/5] Creating portable Python 3.11 environment...
if exist ".venv" (
    echo - Existing .venv found, cleaning up...
    rmdir /s /q ".venv"
)

%UV_CMD% venv --python 3.11
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to create virtual environment with Python 3.11.
    pause
    exit /b 1
)
echo - Portable Python 3.11 virtual environment initialized.
echo.

:: ------------------------------------------------------------
:: STEP 3: INSTALL PIP DEPENDENCIES
:: ------------------------------------------------------------
echo [Step 3/5] Installing package dependencies...
if not exist "requirements.txt" (
    echo [ERROR] requirements.txt not found!
    pause
    exit /b 1
)

%UV_CMD% pip install --upgrade -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo - All Python dependencies installed successfully.
echo.

:: ------------------------------------------------------------
:: STEP 4: DOWNLOAD ffmpeg ^& yt-dlp (OPTIONAL)
:: ------------------------------------------------------------
echo [Step 4/5] Video Downloader Helpers Configuration
if exist "ffmpeg\ffmpeg.exe" (
    if exist "yt-dlp\yt-dlp.exe" (
        echo - Integrated ffmpeg and yt-dlp detected. Skipping download step!
        echo.
        goto SETUP_ENV
    )
)

echo If you plan to download videos, ffmpeg and yt-dlp are required.
set /p INSTALL_VIDEO="Do you want to download/configure video helpers (ffmpeg ^& yt-dlp)? (Y/N) [Y]: "
if "%INSTALL_VIDEO%"=="" set INSTALL_VIDEO=Y

if /i "%INSTALL_VIDEO%" neq "Y" (
    echo - Skipping video helper installation.
    goto SETUP_ENV
)

echo - Downloading/updating yt-dlp...
if not exist "yt-dlp" mkdir "yt-dlp"
if exist "yt-dlp\yt-dlp.exe" (
    echo - Existing yt-dlp found. Checking for updates...
    yt-dlp\yt-dlp.exe -U
) else (
    where curl.exe >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        curl.exe -L -o "yt-dlp\yt-dlp.exe" "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
    ) else (
        powershell -NoProfile -Command "Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe' -OutFile 'yt-dlp/yt-dlp.exe'"
    )
)
if not exist "yt-dlp\yt-dlp.exe" (
    echo [WARNING] Failed to download yt-dlp.
) else (
    echo - yt-dlp configured successfully.
)

echo.
if exist "ffmpeg\ffmpeg.exe" (
    echo - Existing ffmpeg found. Skipping download...
) else (
    echo - Downloading ffmpeg release (essentials build)...
    if not exist "ffmpeg" mkdir "ffmpeg"
    
    where curl.exe >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        curl.exe -L -o ffmpeg.zip "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    ) else (
        powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip' -OutFile 'ffmpeg.zip'"
    )
    
    if exist "ffmpeg.zip" (
        echo - Extracting ffmpeg.zip...
        if exist "ffmpeg_temp" rmdir /s /q "ffmpeg_temp"
        mkdir "ffmpeg_temp"
        
        where tar.exe >nul 2>&1
        if %ERRORLEVEL% equ 0 (
            tar.exe -xf ffmpeg.zip -C ffmpeg_temp
        ) else (
            powershell -NoProfile -Command "Expand-Archive -Path 'ffmpeg.zip' -DestinationPath 'ffmpeg_temp' -Force"
        )
        
        for /r "ffmpeg_temp" %%f in (ffmpeg.exe) do (
            if exist "%%f" move /y "%%f" "ffmpeg" >nul 2>&1
        )
        for /r "ffmpeg_temp" %%f in (ffprobe.exe) do (
            if exist "%%f" move /y "%%f" "ffmpeg" >nul 2>&1
        )
        
        if exist "ffmpeg.zip" del /f /q "ffmpeg.zip"
        if exist "ffmpeg_temp" rmdir /s /q "ffmpeg_temp"
    )
)
if not exist "ffmpeg\ffmpeg.exe" (
    echo [WARNING] Failed to download/extract ffmpeg.
) else (
    echo - ffmpeg ^& ffprobe configured successfully.
)
echo.

:: ------------------------------------------------------------
:: STEP 5: CONFIG ENVIRONMENT FILE (.env)
:: ------------------------------------------------------------
:SETUP_ENV
echo [Step 5/5] Checking configuration (.env)...
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo - Created .env from .env.example template.
    ) else (
        echo - Warning: No .env or .env.example found.
    )
) else (
    echo - .env file already exists.
)
echo.

echo ============================================================
echo      SETUP COMPLETED SUCCESSFULLY!
echo ============================================================
echo.

set /p START_RUN="Do you want to launch the downloader now? (Y/N) [Y]: "
if "%START_RUN%"=="" set START_RUN=Y
if /i "%START_RUN%"=="Y" (
    call run.bat
)

exit /b 0
