# Portable Python & Antigravity 2.0+ Template

This is a portable, high-performance Python 3.11+ starter template optimized for pair programming with Antigravity 2.0+ agents (Gemini, Claude, Codex, etc.) on Windows 10+.

It includes localized agent rules, expert debugging skills, specialized subagent prompt setups, token optimization protocols, security guardrails, and ultra-fast dependency management using `uv`.

## Features
*   🚀 **Fast Portable Setup:** Uses `uv` to automatically provision a standalone Python environment inside the project directory (`.venv`) without modifying global system configurations.
*   🧠 **Persistent Local Memory:** Features a local JSON-based context manager (`state.json` & `lessons.json`) backed by a standard Python CLI tool (`.agent/scripts/memory_tool.py`).
*   🤖 **18 Specialized Subagents:** Non-conversational, focused prompts inside `.agent/subagents/` corresponding to curated skill bundles (including LLM App Developer, Agent Architect, Security Pentester, Secure Developer, Growth Hacker, and more).
*   🛡️ **Immutable Security Guardrails:** Local context boundaries and command blacklists inside `AGENTS.md` and `.agent/rules/` to prevent accidental file deletion and traversal.
*   🛠️ **Integrated Quality Tooling:** Pre-configured out-of-the-box with `ruff` (linter and formatter) and `pytest` (testing framework).
*   📚 **Localized Expert Skills:** Imports and optimizes core global agent skills directly into the repository.

---

## Directory Layout

```
├── .agent/                  # Antigravity agent configuration folder
│   ├── rules/               # Behavioral constraints (token saving, security boundaries, etc.)
│   ├── skills/              # Local copies of domain skills (python-pro, kaizen, security, etc.)
│   ├── workflows/           # Slash commands (/onboard, /memory-sync, /subagent-check)
│   ├── subagents/           # 18 specialized prompts for multi-agent roles
│   ├── memory/              # Local memory files (state.json, lessons.json)
│   └── scripts/             # Python helper tools (memory_tool.py)
├── docs/                    # Documentation folder
│   └── user_guide.md        # Comprehensive Vietnamese cẩm nang hướng dẫn sử dụng
├── src/                     # Python source files
│   └── main.py              # Main code module
├── tests/                   # Pytest test suite
│   └── test_main.py         # Unit tests
├── AGENTS.md                # Single Source of Truth for all agent onboarding and hand-off rules
├── clean.bat                # JIT cleanup utility script (wipes caches, logs, .venv)
├── bootstrap.bat            # Interactive Windows Command Prompt bootstrapper
├── bootstrap.ps1            # PowerShell environment setup bootstrapper
├── update.bat               # Dependency upgrade utility script (rebuilt with goto labels)
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
    Nhấp đúp hoặc chạy trực tiếp tệp `bootstrap.bat` từ Command Prompt/PowerShell. Giao diện menu sẽ hiện lên cho bạn chọn phiên bản Python mong muốn:
    ```cmd
    bootstrap.bat
    ```

*   **Cách 2: Chạy trực tiếp script PowerShell (.ps1):**
    Chạy trực tiếp với tham số phiên bản Python cụ thể (mặc định là 3.11):
    ```powershell
    .\bootstrap.ps1 -PythonVersion "3.11"
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
    uv run python .agent/scripts/memory_tool.py status
    ```
*   **Upgrade Dependencies:**
    ```cmd
    update.bat
    ```

---

## 📚 Hướng Dẫn Sử Dụng Chi Tiết (User Guide)

Để biết cách thiết lập chi tiết, quy trình phối hợp giữa các Agent và Sub-agent, cũng như cách đồng bộ hóa và quản lý bộ nhớ dự án khi chuyển đổi tài khoản AI, vui lòng tham khảo:
*   [Cẩm nang Hướng dẫn sử dụng chi tiết (Vietnamese User Guide)](file:///C:/Users/firef/Documents/antigravity/joyful-babbage/docs/user_guide.md)
