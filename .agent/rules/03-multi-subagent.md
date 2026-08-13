# Multi-Subagent Orchestration Rules

Spawning subagents allows parallel work and isolated problem solving. To use them effectively and prevent token explosions, follow these guidelines:

## 1. When to Spawn Subagents
*   **Parallel Tasks:** Delegate when a task can be partitioned into independent modules (e.g. backend service development, frontend component creation, E2E test setup).
*   **Deep Research:** Spawn a specialized subagent with read-only tools to audit a library, read docs, or analyze logs in the background while you continue building.
*   **Do Not Over-Spawn:** For simple or sequential tasks, do the work yourself. Spawning subagents introduces context-switching overhead and duplicate prompt loading.

## 2. Workspace Modes
When calling `invoke_subagent`, choose the workspace mode carefully:
*   `inherit` (Default): The subagent works in the exact same workspace state. Use this for quick assistance.
*   `share`: The subagent shares the underlying directory but operates independently (like a git worktree). Use this when subagents need to write code to the same project.
*   `branch`: The subagent operates in a cloned/isolated branch directory. Use this for high-risk experiments, spikes, or testing changes without affecting the main working tree.

## 3. Standardized Task Prompts
*   **Define Clear Inputs & Outputs:** A subagent's prompt should contain a specific objective, paths of files to modify, and expected deliverables.
*   **Context Trimming:** Do not pass the entire conversation history to a subagent. Summarize the current architecture and state, and pass only the relevant details.

## 4. Specialized Subagent Library
Use the following specialized subagents in `.agent/subagents/` to execute task types:
- **coder**: Write Python source code and logic changes (`python-pro`, `andrej-karpathy`).
- **linter**: Clean formatting and fix linter alerts (`lint-and-validate`).
- **tester**: Run test suites and report assertion traces (`pytest`).
- **planner**: Brainstorm design workflows, check-lists (`brainstorming`, `concise-planning`, `kaizen`).
- **designer**: Design wireframes and graphics (`canvas-design`, `algorithmic-art`).
- **frontend**: Implement interactive layouts and mobile styling (`frontend-design`, `interactive-portfolio`).
- **backend**: Implement APIs, models, and input boundaries (`python-pro`, `andrej-karpathy`).
- **writer**: Draft copy content and document changes (`content-creator`, `copy-editing`).
- **debugger**: Troubleshoot errors, reproduce issues systematically (`systematic-debugging`).
- **auditor**: Verify security bounds and code safety checks (`vibe-code-auditor`, `kaizen`).
- **refactorer**: Simplify code smells and reduce line counts (`simplify-code`, `andrej-karpathy`).
- **git_manager**: Commit and push releases using conventional git structures (`git-pushing`).
- **coordinator**: Track subagent collisions, sync task checklists (`subagent-orchestrator`, `project-memory`).
- **llm_app_developer**: Build LLM prompt pipelines, manage prompt caching, RAG retrieval (`llm-app-patterns`, `prompt-caching`, `rag-implementation`, `context-window-management`, `langfuse`).
- **agent_architect**: Build multi-actor graphs, custom MCP servers, evaluate reliability metrics (`ai-agents-architect`, `langgraph`, `mcp-builder`, `prompt-engineering`, `rag-engineer`, `agent-evaluation`).
- **security_engineer**: Run vulnerability scans, penetration testing, threat auditing (`security-auditor`, `vulnerability-scanner`, `cloud-penetration-testing`, `ethical-hacking-methodology`, `linux-privilege-escalation`, `top-web-vulnerabilities`, `burp-suite-testing`).
- **security_developer**: Write secure code patterns, configure API headers, rate-limiting (`frontend-security-coder`, `backend-security-coder`, `api-security-best-practices`, `auth-implementation-patterns`, `cc-skill-security-review`, `pci-compliance`).
- **marketing_growth**: Setup A/B tests, GA4/PostHog events, crawler SEO audits (`ab-test-setup`, `analytics-tracking`, `seo-audit`, `content-creator`).



## 5. Subagent Communication & Management
*   **Action-Oriented Messaging:** Use the `send_message` tool to check on status or give new instructions. Keep messages concise.
*   **JSON Status Tracking:** When subagents report status, encourage them to output in a structured format:
    *   `status`: "running" | "done" | "failed"
    *   `progress`: % complete
    *   `deliverables`: list of modified files or test results
*   **Kill Idle Subagents:** Always terminate subagents via `manage_subagents` with the `kill` action once their task is complete or if they get stuck.

