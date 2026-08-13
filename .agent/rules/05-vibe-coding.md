# Vibe Coding Safety Rules

Vibe coding enables rapid iteration, but can lead to silent bugs, technical debt, and architectural regression. Follow these rules to keep the codebase robust.

## 1. Grounded Coding
*   **Goal Definition:** Before suggesting or implementing any code blocks, state clearly what the changes are and what issue they address.
*   **No Copy-Paste Bloat:** Do not duplicate large portions of existing code to make small edits. Use surgical modifications.
*   **Keep Functions Compact:** Limit functions to a maximum of 50 lines. If a function is growing larger, decompose it into smaller helper functions.

## 2. Active Auditing
*   **Audit Rapid Changes:** For any new module or significant function created via fast prompt rounds, run a sanity check using `vibe-code-auditor` dimensions.
*   **Check for Obvious Issues:** Always scan for:
    *   Hardcoded secrets or configurations (must use env vars).
    *   Bare `except Exception:` blocks (must log or handle specific exceptions).
    *   Synchronous long-running network/IO calls without timeouts (always specify `timeout`).

## 3. Regression Prevention
*   **Run Linter Instantly:** After editing any Python file, run Ruff (`uv run ruff check --fix`) to ensure formatting and lint issues are resolved immediately.
*   **Write Tests Parallelly:** Never write a core function without writing a corresponding unit test in `tests/`.
*   **Verify Before Committing:** Run `uv run pytest` to ensure all tests pass before declaring a task finished.
