# Workflow: Onboard (/onboard)

This workflow bootstraps a new agent session, reading local memory and rules, and displaying the current status of the workspace in a token-efficient manner.

## Steps

### Step 1: Read Project Memory
Run the memory CLI tool to read the current state of goals and lessons:
*   Command: `python .agent/scripts/memory_tool.py status`
*   If the files do not exist, run `python .agent/scripts/memory_tool.py init` to set up initial structures.

### Step 2: Read Project Rules
Quickly scan the active rules files in `.agent/rules/` to load critical constraints and style rules:
*   `01-behavior.md`
*   `02-token-savings.md`
*   `03-multi-subagent.md`
*   `04-memory.md`

### Step 3: Check Checklist status
Read `task.md` at the workspace root (or inside the brain artifacts directory if applicable) to see the TODO checklist.

### Step 4: Output Summary
Print a concise summary of the workspace:
*   **Active Goal:** Name and description of the current main goal.
*   **Current Progress:** Percentage completion and active tasks.
*   **Key Files:** Files currently being worked on.
*   **Recent Lessons:** High-priority items from the lessons database.
*   **Next Action:** The immediate next step to execute.
