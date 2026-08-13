---
name: project-memory
description: "Read, write, and search persistent project context, file maps, and lessons learned."
risk: safe
source: local
date_added: "2026-05-24"
---

# Project Memory Skill

This skill allows the agent to maintain continuous context across restarts, multiple sessions, and complex task transitions by reading, writing, and querying the local memory files.

## When to Use This Skill
*   At the start of a task to onboard onto the workspace.
*   After completing a major goal, fixing a difficult bug, or making a system design decision.
*   To check if any specific pitfalls or lessons learned apply to the files being edited.

## Core Files & Schema

Memory is stored in:
1.  `state.json`: Active goals, files associated with them, current task status, and milestone completion flags.
2.  `lessons.json`: Actionable takeaways, code patterns, common lint errors and their fixes.

## Memory Tool Integration

Always use the Python helper script (`.agent/scripts/memory_tool.py`) to manage memories. Running the script is faster and less prone to parsing errors than editing the JSON files manually.

### Common Commands

*   **Initialize/Reset Memory:**
    ```bash
    python .agent/scripts/memory_tool.py init
    ```
*   **Show Current Status:**
    ```bash
    python .agent/scripts/memory_tool.py status
    ```
*   **Set Current Goal/Task:**
    ```bash
    python .agent/scripts/memory_tool.py set-goal "implement user auth" --description "add jwt auth middleware and login endpoints"
    ```
*   **Update Goal Progress:**
    ```bash
    python .agent/scripts/memory_tool.py update-goal --status "in_progress" --progress 50
    ```
*   **Add a Lesson Learned:**
    ```bash
    python .agent/scripts/memory_tool.py add-lesson "jwt expiration" "Ensure JWT tokens expire within 15 minutes, and refresh tokens are stored securely in HTTP-only cookies to prevent XSS theft." --tags "security,auth,jwt"
    ```
*   **Search Lessons:**
    ```bash
    python .agent/scripts/memory_tool.py search "jwt"
    ```
*   **Prune/Compress Memory:**
    ```bash
    python .agent/scripts/memory_tool.py compress
    ```

## Memory Retrieval Checklist

Before writing any new feature or touching code:
1.  Query the lessons database for keywords related to your current task (e.g. `python .agent/scripts/memory_tool.py search <keyword>`).
2.  Read the results and make sure to apply the documented patterns and avoid listed mistakes.
3.  If no lessons exist, execute following standard best practices.
