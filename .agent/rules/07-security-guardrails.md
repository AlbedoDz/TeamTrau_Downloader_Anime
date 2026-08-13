# 🛡️ SECURITY GUARDRAIL & EXECUTION POLICY (IMMUTABLE)

## 1. MANDATORY CONTEXT BOUNDARY
- You are STRICTLY FORBIDDEN from executing any file system operation or terminal command outside the current project root directory.
- Never touch, scan, or analyze any paths containing system directories, cloud sync paths, or global user profiles (e.g., `C:/Windows`, `C:/Users/Administrator`, `/etc/`, `/var/`).

## 2. TERMINAL COMMAND BLACKLIST (STRICT BAN)
You are absolutely prohibited from generating or running the following destructive commands under any circumstances. If a task implies their usage, STOP immediately and demand human intervention:

### A. POSIX / WSL2 / Docker Environment Banned Commands:
- `rm -rf /` or `rm -rf *` (or any recursive deletion above the local subdirectory level).
- `chmod 777` or `chown` on root levels.
- `docker system prune -a` or `docker rmi` without explicit target hashes.
- `kill -9` on system PIDs.

### B. Native Windows Environment Banned Commands:
- `rd /s /q c:\` or `rd /s /q` on any parent directories.
- `del /f /s /q` targeted at wildcard extensions outside `.venv` or temporary caches.
- `format`, `diskpart`, `cipher`.
- `Remove-Item -Recurse -Force` targeted at root or user profile paths.

## 3. SAFE DELETION PROTOCOL (POKA-YOKE)
When tasked with cleaning up files, directories, or optimizing code structures:
1. **Verification Turn:** You must perform a `git status` or file list check first to log exactly what files are targeted.
2. **Local Scope Isolation:** Deletion is only permitted inside specific volatile directories: `.pytest_cache/`, `__pycache__/`, or files explicitly added by the active sub-task.
3. **No Global Cleanup:** Never attempt to resolve Python library bloat by clearing system-wide folders. Always operate within the local `.venv` using `uv`.

## 4. SECURITY INTERCEPTOR VIOLATION TRIGGER
If any generated plan or subagent routine attempts to bypass these rules, you must:
- Immediately abort the active orchestration loop.
- Write a high-priority alert block into `AUDIT_LOG.md` detailing the blocked token payload.
- Return control to the user with a `CRITICAL_SECURITY_EXCEPTION` message.
