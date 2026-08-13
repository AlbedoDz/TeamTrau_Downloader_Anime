# Python 3.11+ & Windows 10+ Guidelines

These rules ensure that the project runs flawlessly on Windows 10+ environments and utilizes modern Python 3.11+ idioms.

## 1. Windows Path Compatibility
*   **Path Separation:** Always use `pathlib.Path` or double backslashes/raw strings (`r"C:\..."`) to represent Windows paths in Python to prevent character escaping errors (e.g. `\U` or `\n` escaping).
*   **Forward Slashes in Code:** In code logic, config JSONs, and markdown links, prefer using forward slashes (`/`) as Windows APIs and modern tools recognize them natively, which ensures cross-platform compatibility.

## 2. Shell Execution & Virtual Environment
*   **Powershell Cmdlets:** Use PowerShell syntax when writing CLI scripts or executing terminal commands. Prepend scripts with `.\` (e.g., `.\setup.ps1`).
*   **Venv Execution:** Never run python modules or scripts globally. Always prepend commands with `uv run` or run executable utilities from `.venv/Scripts/` (e.g. `.venv/Scripts/pytest`).
*   **Encoding Safety:** Force UTF-8 encoding when reading or writing text files on Windows to prevent `UnicodeDecodeError` (which defaults to Windows-1252 in some environments). Example: `open(file, "r", encoding="utf-8")`.

## 3. Python 3.11+ Standards
*   **Type Hinting:** Use strict, modern type hints. Use `list[str]` instead of `typing.List[str]`, and `str | None` instead of `typing.Optional[str]`.
*   **Pattern Matching:** Use `match case` patterns for clean control flow instead of deeply nested `if-elif-else` branches when processing inputs/commands.
*   **Exception Groups:** Leverage Python 3.11 Exception Groups (`ExceptionGroup` and `except*`) when dealing with concurrent tasks or multiple failures in subagents.
*   **Performance:** Minimize memory copies; use generator expressions and `pathlib` for file system operations.
