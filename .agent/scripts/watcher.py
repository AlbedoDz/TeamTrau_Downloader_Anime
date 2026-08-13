#!/usr/bin/env python3
import os
import sys
import time
import subprocess

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY_DIR = os.path.join(BASE_DIR, "memory")
PID_FILE = os.path.join(MEMORY_DIR, "watcher.pid")

def get_modified_files():
    try:
        # Run git status --porcelain -u
        result = subprocess.run(
            ["git", "status", "--porcelain", "-u"],
            capture_output=True, text=True, check=True
        )
        lines = result.stdout.strip().split("\n")
        files = []
        for line in lines:
            if not line:
                continue
            filepath = line[3:].strip()
            # Ignore agent internal folders and packaged templates
            if ".agent/" in filepath or "project_template.zip" in filepath or not filepath:
                continue
            files.append(filepath)
        return sorted(files)
    except Exception:
        return []

def kill_existing_watcher():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r", encoding="utf-8") as f:
                pid = int(f.read().strip())
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            else:
                os.kill(pid, 9)
        except Exception:
            pass

def main():
    kill_existing_watcher()
    
    os.makedirs(MEMORY_DIR, exist_ok=True)
    with open(PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
        
    last_files = None
    
    # Run a quick initial sync on startup
    subprocess.run(
        [sys.executable, os.path.join(BASE_DIR, "scripts", "memory_tool.py"), "sync-git"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    last_files = get_modified_files()
    
    while True:
        time.sleep(2)
        current_files = get_modified_files()
        if current_files != last_files:
            # Sync to state.json
            subprocess.run(
                [sys.executable, os.path.join(BASE_DIR, "scripts", "memory_tool.py"), "sync-git"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            last_files = current_files

if __name__ == "__main__":
    main()
