<#
.SYNOPSIS
    Automated environment setup script for Python template on Windows.
.DESCRIPTION
    Checks for the 'uv' package manager, provisions a portable/standalone Python environment,
    installs requirements, and runs syntax and test suite checks.
.PARAMETER PythonVersion
    The major/minor Python version to target (e.g., "3.11" or "3.12"). Defaults to "3.11".
.EXAMPLE
    .\bootstrap.ps1 -PythonVersion "3.11"
#>
param(
    [string]$PythonVersion = "3.11"
)

$ErrorActionPreference = "Stop"

# 0. Kill existing watcher to release file locks on .venv
$pidPath = ".agent/memory/watcher.pid"
if (Test-Path $pidPath) {
    try {
        $oldPid = Get-Content $pidPath -ErrorAction SilentlyContinue
        if ($oldPid) {
            taskkill /F /PID $oldPid /T > $null 2>&1
            Start-Sleep -Seconds 1
        }
        Remove-Item $pidPath -Force -ErrorAction SilentlyContinue
    } catch {}
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " PORTABLE PYTHON TEMPLATE INITIALIZATION" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Verify uv installation
Write-Host "[1/5] Checking for 'uv' package manager..." -ForegroundColor Yellow
$uvCheck = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvCheck) {
    Write-Error "The 'uv' package manager is not installed or not in PATH. Please install uv first (e.g. run 'winget install astral-sh.uv' or download from github.com/astral-sh/uv)."
}
$uvVersion = & uv --version
Write-Host "Found: $uvVersion" -ForegroundColor Green

# 2. Provision portable virtual environment using uv
Write-Host "[2/5] Creating local virtual environment (.venv) using portable Python $PythonVersion..." -ForegroundColor Yellow
if (Test-Path ".venv") {
    Write-Host "Existing .venv folder found. Re-creating environment..." -ForegroundColor DarkYellow
    Remove-Item -Path ".venv" -Recurse -Force
}

try {
    # uv venv --python 3.11 automatically fetches the latest portable release of Python 3.11
    & uv venv --python $PythonVersion
    Write-Host "Successfully initialized virtual environment using portable Python $PythonVersion!" -ForegroundColor Green
} catch {
    Write-Error "Failed to create virtual environment with Python $PythonVersion. Ensure the version is valid (e.g. 3.11, 3.12) and uv is functional."
}

# 3. Install dependencies from requirements.txt
Write-Host "[3/5] Installing dependencies from requirements.txt..." -ForegroundColor Yellow
if (Test-Path "requirements.txt") {
    & uv pip install -r requirements.txt
    Write-Host "Dependencies successfully installed!" -ForegroundColor Green
} else {
    Write-Host "No requirements.txt found. Skipping dependency installation." -ForegroundColor DarkYellow
}

# Copy .env.example if .env does not exist
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "Created .env configuration file from .env.example!" -ForegroundColor Green
    }
}

# 4. Run Ruff linting and formatting check
Write-Host "[4/5] Running Ruff code analysis..." -ForegroundColor Yellow
try {
    & uv run ruff check .
    & uv run ruff format --check .
    Write-Host "Code style and quality checks passed!" -ForegroundColor Green
} catch {
    Write-Warning "Linter checks reported errors. Please run 'uv run ruff check --fix' and 'uv run ruff format' to resolve them."
}

# 5. Run Pytest unit tests
Write-Host "[5/5] Running test suite..." -ForegroundColor Yellow
try {
    & uv run pytest
    Write-Host "All tests passed successfully!" -ForegroundColor Green
} catch {
    Write-Error "Some tests failed. Check output logs for debugging details."
}

# 6. Configure Git Pre-commit Hook
Write-Host "Configuring Git pre-commit hook..." -ForegroundColor Yellow
if (Test-Path ".git") {
    $hooksDir = ".git/hooks"
    if (-not (Test-Path $hooksDir)) {
        New-Item -ItemType Directory -Path $hooksDir -Force | Out-Null
    }
    
    $hookPath = "$hooksDir/pre-commit"
    $hookContent = @'
#!/bin/sh
# Auto-generated pre-commit hook by Antigravity Python template
echo "========================================="
echo "Running Auto-Sync and Ruff checks..."
echo "========================================="
uv run python .agent/scripts/memory_tool.py sync-git
git add .agent/memory/state.json
uv run ruff check .
if [ $? -ne 0 ]; then
  echo "Ruff checks failed. Commit aborted!"
  exit 1
fi
echo "Checks passed! Proceeding to commit..."
exit 0
'@
    # Write pre-commit hook using ASCII encoding to ensure Git compatibility on Windows
    [System.IO.File]::WriteAllText((Get-Item -Path ".").FullName + "/" + $hookPath, $hookContent, [System.Text.Encoding]::ASCII)
    Write-Host "Git pre-commit hook successfully configured at $hookPath!" -ForegroundColor Green
} else {
    Write-Host "Not a git repository. Skipping git hook installation." -ForegroundColor DarkYellow
}

# 7. Start background Memory Watcher
Write-Host "Configuring and launching background Memory Watcher..." -ForegroundColor Yellow


try {
    $projDir = (Get-Item -Path ".").FullName
    $pythonExe = Join-Path $projDir ".venv\Scripts\python.exe"
    $watcherScript = Join-Path $projDir ".agent\scripts\watcher.py"
    Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
        CommandLine = "`"$pythonExe`" `"$watcherScript`""
        CurrentDirectory = $projDir
    } | Out-Null
    Write-Host "Memory Watcher successfully launched in the background!" -ForegroundColor Green
} catch {
    Write-Warning "Failed to automatically launch Memory Watcher background process: $_"
}

Write-Host "============================================================" -ForegroundColor Green
Write-Host " ENVIRONMENT READY! Portable virtual env configured in .venv/" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green

