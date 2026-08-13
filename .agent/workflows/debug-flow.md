# Workflow: Debug Flow (/debug-flow)

This workflow implements the systematic debugging methodology to investigate, isolate, and resolve bugs efficiently.

## Steps

### Step 1: Read Error & Gather Stack Trace
Run the test runner to capture the exact failure signature:
*   Command: `uv run pytest -vv` (or run python test script directly).
*   Carefully inspect line numbers, file paths, and exception messages.

### Step 2: Reproduce the Bug Consistently
*   Verify if the error can be triggered reliably.
*   Identify the exact steps, inputs, and environment config under which the bug occurs.

### Step 3: Trace Data Flow Backward
Trace the origin of the failing variable/state:
*   Look up the stack trace line by line.
*   Identify where the invalid value was first calculated or passed in.
*   If in a multi-component system, add diagnostic instrumentation (logs) at boundary limits.

### Step 4: Formulate and Test Hypothesis
*   Write down a single clear hypothesis: "I think X is the root cause because Y."
*   Make the **smallest possible change** to verify this hypothesis.
*   Verify the outcome. If the hypothesis is wrong, discard the edit and formulate a new one.

### Step 5: Implement and Verify Fix
*   Apply the final behavior-preserving fix.
*   Run the linter (`uv run ruff check --fix`).
*   Run pytest (`uv run pytest`) to ensure the bug is resolved and no regressions were introduced.
