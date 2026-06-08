# Portable Python & Antigravity 2.0+ Template

This is a portable, high-performance Python 3.11+ starter template optimized for pair programming with Antigravity 2.0+ agents on Windows 10+.

It includes localized agent rules, expert debugging skills, specialized subagent prompt setups, token optimization protocols, and ultra-fast dependency management using `uv`.

## Features
*   🚀 **Fast Portable Setup:** Uses `uv` to automatically provision a standalone Python environment inside the project directory (`.venv`) without modifying global system configurations.
*   🧠 **Persistent Local Memory:** Features a local JSON-based context manager (`state.json` & `lessons.json`) backed by a standard Python CLI tool (`.agent/scripts/memory_tool.py`).
*   🤖 **Token-Efficient Multi-Subagents:** Features non-conversational, specialized prompts (`coder.md`, `linter.md`, `tester.md`) to save input/output tokens when spawning background subagents.
*   🛠️ **Integrated Quality Tooling:** Pre-configured out-of-the-box with `ruff` (linter and formatter) and `pytest` (testing framework).
*   📚 **Localized Expert Skills:** Imports and optimizes core global agent skills (`vibe-code-auditor`, `systematic-debugging`, `python-pro`, `kaizen`, `andrej-karpathy`) directly into the repository.

---

## Directory Layout

```
├── .agent/                  # Antigravity agent configuration folder
│   ├── rules/               # Behavioral constraints (token saving, path compat, subagents)
│   ├── skills/              # Local copies of domain skills (auditing, debugging, etc.)
│   ├── workflows/           # Slash commands (/onboard, /memory-sync, /subagent-check, /debug-flow)
│   ├── subagents/           # Prompts for coder, linter, and tester subagents
│   ├── memory/              # Local memory files (state.json, lessons.json)
│   └── scripts/             # Python helper tools (memory_tool.py)
├── src/                     # Python source files
│   └── main.py              # Main code module
├── tests/                   # Pytest test suite
│   └── test_main.py         # Unit tests
├── clean.bat                # JIT cleanup utility script
├── setup_env_py.bat         # Interactive Windows Command Prompt bootstrapper
├── setup.ps1                # PowerShell environment setup bootstrapper
├── pyproject.toml           # Configurations for Ruff, Pytest, and package metadata
├── requirements.txt         # Package dependencies
└── README.md                # This documentation
```

---

## Getting Started

### 1. Prerequisite
Ensure the `uv` package manager is installed on your Windows system:
```powershell
# Install via winget
winget install astral-sh.uv
```

### 2. Environment Bootstrapping
Bạn có thể thiết lập môi trường bằng một trong hai cách sau trên Windows:

*   **Cách 1: Chạy file Batch (.bat) tương tác:**
    Nhấp đúp hoặc chạy trực tiếp tệp `setup_env_py.bat` từ Command Prompt/PowerShell. Giao diện menu sẽ hiện lên cho bạn chọn phiên bản Python mong muốn:
    ```cmd
    setup_env_py.bat
    ```

*   **Cách 2: Chạy trực tiếp script PowerShell (.ps1):**
    Chạy trực tiếp với tham số phiên bản Python cụ thể (mặc định là 3.11):
    ```powershell
    .\setup.ps1 -PythonVersion "3.11"
    ```

### 3. Activating and Running Commands
All commands run inside the local virtual environment context using `uv run`.

*   **Run linter and formatter checks:**
    ```powershell
    uv run ruff check
    uv run ruff format --check
    ```
*   **Run test suite:**
    ```powershell
    uv run pytest
    ```
*   **Inspect Agent Memory Status:**
    ```powershell
    python .agent/scripts/memory_tool.py status
    ```
