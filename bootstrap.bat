@echo off
title Python Portable Env Setup Bootstrapper
cls

echo ============================================================
echo      KHOI TAO MOI TRUONG PYTHON DI DONG (PORTABLE)
echo ============================================================
echo.
echo Vui long chon phien ban Python ban muon thiet lap:
echo [1] Python 3.10 (Tuong thich rong rai)
echo [2] Python 3.11 (On dinh mac dinh)
echo [3] Python 3.12 (Hieu nang cao)
echo [4] Python 3.13 (Phien ban moi nhat hien tai)
echo [5] Phien ban khac (Nhap thu cong phien ban mong muon)
echo.

set /p user_choice="Chon chuc nang (1-5): "

if "%user_choice%"=="1" (
    set PYTHON_VER=3.10
    goto RUN_SETUP
)
if "%user_choice%"=="2" (
    set PYTHON_VER=3.11
    goto RUN_SETUP
)
if "%user_choice%"=="3" (
    set PYTHON_VER=3.12
    goto RUN_SETUP
)
if "%user_choice%"=="4" (
    set PYTHON_VER=3.13
    goto RUN_SETUP
)
if "%user_choice%"=="5" (
    echo.
    set /p PYTHON_VER="Nhap phien ban Python mong muon (vd: 3.11, 3.12, 3.13): "
    goto RUN_SETUP
)

echo.
echo Lua chon khong hop le! Thoat chuong trinh.
pause
exit /b 1

:RUN_SETUP
echo.
echo ------------------------------------------------------------
echo Bat dau thiet lap moi truong Python %PYTHON_VER% qua PowerShell...
echo ------------------------------------------------------------
echo.

powershell -ExecutionPolicy Bypass -File ".\bootstrap.ps1" -PythonVersion "%PYTHON_VER%"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [LOI] Co loi xay ra trong qua trinh thiet lap moi truong!
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo Thiet lap thanh cong! Nhan bat ky phim nao de thoat.
pause
exit /b 0
