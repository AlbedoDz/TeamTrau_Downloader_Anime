# Agent Behavioral Rules

These rules govern all agent reasoning and code modifications within this workspace. They prioritize absolute accuracy, simplicity, and cleanliness.

## 1. Plan & Think Before Coding
*   **State Assumptions:** Before writing any code, state your plan and assumptions.
*   **No Silent Decisions:** If there are multiple design paths or tradeoffs, present them to the user instead of picking one silently.
*   **Acknowledge Uncertainty:** Do not hide confusion. If a requirement is ambiguous, stop and ask for clarification.

## 2. Simplicity & Minimum Code
*   **No Speculative Engineering:** Implement only what is explicitly requested. Do not add "future-proofing", "flexibility", "configurability", or unused abstractions.
*   **Avoid Over-complication:** If a task can be solved in 20 lines of code, do not write 100 lines. Push back on over-engineering.
*   **Zero Placeholders:** Never use comment placeholders like `// TODO: implement later` or dummy mock responses unless specifically requested.

## 3. Surgical Code Modifications
*   **Strict Scope Preservation:** Edit only the lines necessary to satisfy the request. 
*   **No Stylistic Refactoring:** Do not clean up, reformat, or "improve" adjacent code unless explicitly asked to.
*   **Remove Dead Code:** Only remove dead code, variables, or imports that *your* modifications directly orphaned. Leave pre-existing dead code intact.

## 4. Verification Loops
*   **Define Success First:** Before writing code, state exactly how the change will be verified.
*   **Validate After Edits:** Always verify your work by running unit tests, inspecting build outputs, or using validation tools. Do not mark a task complete without verification.
