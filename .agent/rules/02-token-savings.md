# Token-Savings & Prompt Caching Rules

To minimize costs, speed up response times, and respect rate limits, you must actively conserve token usage.

## 1. Targeted File Interactions
*   **Lazy File Reading:** Do not read entire files if you only need to inspect a specific function or class. Use `view_file` with `StartLine` and `EndLine` parameters.
*   **Check Imports First:** Before reading a file, review the import statements or look at its structure to confirm it is the correct file.
*   **Filtered Searching:** When using `grep_search`, always supply specific folder paths and use glob filters (`Includes` property) to avoid scanning node_modules, build directories, or unrelated code.

## 2. Prompt Caching Optimization (for Gemini)
*   **Stable Instruction Prefix:** Keep the configuration, system rules, and base instructions identical and at the top of the context window.
*   **Segregate Dynamic Data:** Place frequently changing state (like list directories, command outputs, or temporary variables) at the end of the context where possible.
*   **Avoid Unnecessary Tool Repetitions:** Do not repeatedly call the same informational tool (e.g. listing the same directory or reading the same file segment) within a single turn unless the content has changed.

## 3. Concise Communication
*   **No Code Duplication:** Do not output whole files of code in your chat responses. Point the user to the file path, output brief diffs, or explain the changes conceptually.
*   **No Obvious Explanations:** Do not explain standard syntax or list what every line of code does. Focus explanations only on non-obvious design choices or critical context.
*   **Summarize Logs:** If a terminal command returns a huge output, do not copy-paste it all. Summarize the status, the count of tests passed/failed, and print only the relevant error traces.
