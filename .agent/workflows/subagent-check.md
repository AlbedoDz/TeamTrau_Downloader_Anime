# Workflow: Subagent Check (/subagent-check)

This workflow scans active subagents, checks their progress, retrieves their outputs, and cleans up finished or stuck processes to optimize resource usage.

## Steps

### Step 1: List Active Subagents
Call the subagent management tool or API to inspect all running background agents:
*   Action: `list` subagents to retrieve their names, conversation IDs, and status.

### Step 2: Query Progress
For each active subagent:
*   Send a status request message if they have been silent (e.g. "Hi, please give a quick status update on your task").
*   Inspect their workspaces or log outputs to verify if they have committed or modified files.

### Step 3: Clean Up
*   Identify subagents that have finished their tasks or have been idle for a long duration.
*   Run the `kill` action via `manage_subagents` for their specific Conversation IDs.

### Step 4: Aggregate Outputs
*   Incorporate any code or designs they generated into the main project state.
*   Update `state.json` and `task.md` with completed subagent items.
