---
name: clone-project
description: "Automate cloning a project directory with the latest code updates, skipping unnecessary files (like .venv, .git) and bundling binaries."
category: automation
risk: safe
source: user
tags: "[automation, clone, zipping, portability]"
date_added: "2026-06-05"
---

# clone-project

## Purpose

Automates the packaging and zipping of a project into a portable archive. It gathers the latest code updates, bundles specific dependencies or tool folders (such as `ffmpeg` and `yt-dlp`), and automatically excludes metadata or cache directories (`.git`, `.venv`, `logs`, `.pytest_cache`, etc.).

## When to Use This Skill

This skill should be used when:
- The user asks to "clone this project", "clone project with latest code", or "create portable zip".
- The user wants a clean and portable ZIP file containing the latest code updates to copy to another machine.
- You need to run a zip command omitting temporary and virtual environments files to save space.

## Instructions

When triggered, automatically perform the following steps without waiting for further prompts unless clarification is needed:

1. **Verify Source Path:** Identify the root directory of the project the user wants to clone.
2. **Determine Exclusions:** Identify typical folders to exclude such as `.git`, `.venv`, `.pytest_cache`, `.ruff_cache`, `.vscode`, `logs`, `log-test`, and `downloads`.
3. **Execute Zipping Task:** Use a `python` script or a powershell script to create the zip file:
   ```python
   import zipfile, os
   zf = zipfile.ZipFile('download_subtitle_portable.zip', 'w', zipfile.ZIP_DEFLATED)
   exclusions = ['.git', '.venv', 'downloads', 'log-test', 'logs', '.pytest_cache', '.ruff_cache', '.agent', '.vscode']
   for r, d, files in os.walk('.'):
       for f in files:
           if not any(x in r.split(os.sep) for x in exclusions) and f != 'download_subtitle_portable.zip':
               zf.write(os.path.join(r, f), os.path.relpath(os.path.join(r, f), '.'))
   zf.close()
   ```
4. **Notify the User:** Once the task successfully finishes running, provide a local link to the generated zip file.

## Quality Standards
- Do not use complex third-party CLI tools if python standard libraries can do the job reliably.
- Do not delete any existing user files during the process.
- Keep the generated zip archive in the root of the project unless the user specifies otherwise.
