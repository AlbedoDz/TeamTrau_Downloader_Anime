@echo off
title Cleanup Python Template Project (JIT)
cls

echo ============================================================
echo      DON DEP THU MUC DU AN MAU (JUST-IN-TIME CLEANUP)
echo ============================================================
echo.
echo Tien trinh nay se xoa cac tep tin/thu muc tam thoi va cache.
echo (Ban co the khoi tao lai bat ky luc nao bang setup_env_py.bat)
echo.

set /p confirm="Ban co chac chan muon don dep? (Y/N): "
if /i "%confirm%" neq "Y" (
    echo.
    echo Da huy tien trinh don dep.
    pause
    exit /b 0
)

echo.
echo ------------------------------------------------------------
echo Dang tien hanh xoa cac thu muc rac va cache...
echo ------------------------------------------------------------

:: 1. Delete virtual environment folder
if exist ".venv" (
    echo [Xoa] Moi truong ao .venv...
    rmdir /s /q ".venv"
)

:: 2. Delete logs folder
if exist "logs" (
    echo [Xoa] Thu muc logs...
    rmdir /s /q "logs"
)

:: 3. Delete cache folders
if exist ".pytest_cache" (
    echo [Xoa] Cache kiem thu .pytest_cache...
    rmdir /s /q ".pytest_cache"
)
if exist ".ruff_cache" (
    echo [Xoa] Cache linter .ruff_cache...
    rmdir /s /q ".ruff_cache"
)

:: 4. Delete lock and local environment configurations
if exist "uv.lock" (
    echo [Xoa] Tep khoa uv.lock...
    del /f /q "uv.lock"
)
if exist ".env" (
    echo [Xoa] Tep cau hinh cuc bo .env...
    del /f /q ".env"
)

:: 5. Delete pycache and pyc files recursively
echo [Xoa] Cac tep tin Python da bien dich (__pycache__, *.pyc)...
for /d /r . %%d in (__pycache__) do (
    if exist "%%d" rmdir /s /q "%%d"
)
del /s /q /f *.pyc *.pyo *.pyd >nul 2>&1

echo.
echo ------------------------------------------------------------
echo Don dep hoan tat! Thu muc hien tai da sach se tuyet doi.
echo ------------------------------------------------------------
echo.
pause
exit /b 0
