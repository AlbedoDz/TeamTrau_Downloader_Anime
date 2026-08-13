---
name: subagent-orchestrator
description: "Coordinate, monitor, and merge tasks across multiple concurrent subagents."
risk: safe
source: local
date_added: "2026-05-24"
---

# Subagent Orchestrator Skill

This skill details the patterns for partitioning a large, complex task and orchestrating multiple subagents to solve individual sub-tasks in parallel.

## When to Use This Skill
*   The task consists of multiple decoupleable domains (e.g., UI frontend, Database schema, backend endpoints).
*   A task requires long-running background processes like scanning large trace files or reading external docs.
*   You need to execute testing pipelines in parallel to verify multiple components concurrently.

## Step-by-Step Orchestration Flow

### 1. Partitioning the Goal
Deconstruct the main goal into specific, isolated deliverables:
*   Identify overlapping files. If two subagents need to edit the same file, serialize their work or combine their tasks into one subagent to avoid write conflicts.
*   Define clear interfaces between components (e.g. API contracts, database schemas).

### 2. Defining Subagents
When calling `invoke_subagent`, define a clear role and instructions:
*   **Role:** E.g. "Database Engineer", "Frontend Developer", "E2E Tester".
*   **Prompt standard structure:**
    *   **Context:** Quick 1-2 sentence overview of the workspace and goal.
    *   **Files Scope:** List the exact files the subagent is allowed to read and edit.
    *   **Deliverables Checklist:** Specific list of tasks and successful outcomes (e.g. "Create `api/auth.js`", "Make sure tests pass").
    *   **Workspace Mode:** Use `share` for shared directories, `branch` for spikes.

### 3. Monitoring Execution
*   Check in with subagents periodically using `send_message` or run the `/subagent-check` command.
*   If a subagent fails or goes off-track, send corrective feedback or kill it and restart it with clearer instructions.

### 4. Merging & Verification
*   Once a subagent reports completion, inspect their modifications and run tests in the workspace to verify stability.
*   Update your central tracking task list (`task.md`) and local memory (`state.json`) with the progress.
*   Kill the subagent via `manage_subagents` to free system resources.
