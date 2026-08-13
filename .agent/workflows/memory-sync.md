# Workflow: Memory Sync (/memory-sync)

This workflow reconciles, cleans up, and compresses the local memory files to keep them small and token-efficient.

## Steps

### Step 1: Analyze Current State
Read the JSON files inside `.agent/memory/`. Evaluate if they exceed size guidelines (~20KB).

### Step 2: Archive Resolved Tasks
*   Find tasks marked as "completed" in `state.json` that are more than a week old or no longer relevant.
*   Remove or move them to an archive section inside `state.json` to keep the active task list short.

### Step 3: Consolidate Lessons
*   Review `lessons.json` for redundant or overlapping items (e.g. two entries about React routing issues).
*   Merge duplicates into single, highly comprehensive but concise entries.

### Step 4: Run Synchronization and Compression Scripts
Automatically scan modified files and compress memory files to minimize context size:
*   Sync Command: `python .agent/scripts/memory_tool.py sync-git`
*   Compression Command: `python .agent/scripts/memory_tool.py compress`

