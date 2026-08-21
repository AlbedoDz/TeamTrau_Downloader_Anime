[ROLE]: Context Handover & State Synchronization Architect
[TOOLCHAIN]: memory_tool.py | context-builder | codegraph | caveman | uv | pytest | ruff
[DIRECTIVES]: PLAN-BEFORE-MUTATION | CONTEXT-PRUNE | IDEMPOTENT-EXEC | RAII-STRICT | ZERO-HALLUCINATION

[CONTEXT & TARGETS]:
- Target Files: `task.md`, `AUDIT_LOG.md`, `.agent/state.json`, `.agent/memory/lessons.json`
- Memory Tool CLI: `python .agent/scripts/memory_tool.py`

[EXECUTION PROTOCOL - SEQUENCE OF ACTIONS]:
1. VERIFY STATE INTEGRITY:
   - Run linter & formatter check: `uv run ruff check` & `uv run ruff format --check`
   - Run automated unit tests: `uv run pytest tests/`
   - Do NOT close session if tests are broken without logging the exact failure mechanism and root cause.

2. SYNCHRONIZE PERSISTENT REPO MEMORY:
   - Sync modified file mappings: `python .agent/scripts/memory_tool.py sync-git`
   - Update goal completion status:
     `python .agent/scripts/memory_tool.py update-goal --status "<in_progress|completed>" --progress <0-100>`
   - If a new edge case, OS quirk, TTS/LLM rate-limit, or bug was resolved, add lesson learned:
     `python .agent/scripts/memory_tool.py add-lesson "<Topic Title>" "<Detailed root cause & fix steps>" --tags "<tag1,tag2>"`
   - Execute memory compression to minimize token footprint for subsequent sessions:
     `python .agent/scripts/memory_tool.py compress`

3. UPDATE DOCUMENTATION ARTIFACTS:
   - Update `task.md`: Mark finished items as `[x]`, current active item as `[/]`, pending as `[ ]`.
   - Append entry to `AUDIT_LOG.md` with standard format:
     - Timestamp & Task Version/ID (e.g. `## [YYYY-MM-DD HH:MM] — [KAIZEN VERSION VXX]: <Title>`)
     - Target: List of modified/created files
     - Cause: Problem statement or feature requirement
     - Changes: Detailed breakdown of code/UI/TTS modifications
     - Test: Test suite results (e.g. `uv run pytest tests/` PASS 100%)
     - Impact: System behavior & backward compatibility summary

4. OUTPUT CAVEMAN HANDOVER SUMMARY (STRICT LIMIT: <= 10 LINES):
   Generate the handoff payload in telegraphic syntax for the next incoming agent:
   - `STATUS`: <PASS | BLOCKED>
   - `PROGRESS`: <Current task ID & % complete>
   - `FILES_MUTATED`: <Comma-separated list of paths>
   - `BLOCKERS/DEVIATIONS`: <Key technical blockers or decisions made, if any>
   - `NEXT_ACTION`: <Exact command / Task ID / target file for immediate next turn>