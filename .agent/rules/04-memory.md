# Project Memory Rules

To maintain long-term context across separate agent sessions, restarts, and workspace changes, you must utilize the local workspace memory.

## 1. Memory Storage Files
Memory is stored inside the `.agent/memory/` directory:
*   `state.json`: Tracks active tasks, implementation status, file mapping, and current progress.
*   `lessons.json`: Tracks lessons learned, patterns, coding rules that worked well, and errors to avoid.

## 2. Bootstrapping and Session Initiation
*   **Check Memory on Startup:** At the beginning of any session or task, read `state.json` and `lessons.json` to understand the state of the workspace and recall lessons from previous sessions.
*   **Check Workflows:** Run the `/onboard` command if available to quickly get a summary of the current task.

## 3. Recording Memory
*   **Document Major Milestones:** When a feature is completed, a critical bug is fixed, or an architectural choice is made, record the outcome in the memory files.
*   **Capture Lessons Learned:** If you resolve a complex bug or hit a linting issue, immediately record a lesson in `lessons.json` explaining what went wrong and how it was fixed.
*   **Use the CLI Tool:** Use `python .agent/scripts/memory_tool.py` to add, list, update, and search memory items efficiently.

## 4. Memory Maintenance & Compression
*   **Avoid Memory Rot:** Delete or archive completed goals in `state.json` to keep the file small.
*   **Compress & Summarize:** Regularly prune and summarize entries in the JSON files. Do not allow memory files to grow beyond 20KB. If they do, run `/memory-sync` to compress them.
