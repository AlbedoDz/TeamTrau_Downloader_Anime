#!/usr/bin/env python3
import argparse
import json
import os
import sys
from datetime import datetime

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY_DIR = os.path.join(BASE_DIR, "memory")
STATE_FILE = os.path.join(MEMORY_DIR, "state.json")
LESSONS_FILE = os.path.join(MEMORY_DIR, "lessons.json")

DEFAULT_STATE = {
    "current_goal": {
        "name": "Untitled Goal",
        "description": "No description set.",
        "status": "not_started",
        "progress": 0,
        "started_at": None,
        "updated_at": None,
    },
    "files_mapping": {},
    "active_subagents": [],
    "milestones": [],
}


def load_json(filepath, default):
    if not os.path.exists(filepath):
        return default
    try:
        with open(filepath, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}", file=sys.stderr)
        raise ValueError(f"Corrupt JSON file detected at {filepath}: {e}. Aborting operation to prevent data loss.")


def save_json(filepath, data, compact=False):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            if compact:
                json.dump(data, f, separators=(",", ":"))
            else:
                json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving {filepath}: {e}", file=sys.stderr)


def get_timestamp():
    return datetime.now().isoformat()


def cmd_init(args):
    """Initializes the memory folder and default json files."""
    os.makedirs(MEMORY_DIR, exist_ok=True)
    created = False
    if not os.path.exists(STATE_FILE):
        save_json(STATE_FILE, DEFAULT_STATE)
        print(f"Created state file: {STATE_FILE}")
        created = True
    if not os.path.exists(LESSONS_FILE):
        save_json(LESSONS_FILE, [])
        print(f"Created lessons file: {LESSONS_FILE}")
        created = True
    if not created:
        print("Memory files already initialized.")


def cmd_status(args):
    """Displays the active goal, progress, and milestone completion."""
    state = load_json(STATE_FILE, DEFAULT_STATE)
    lessons = load_json(LESSONS_FILE, [])

    goal = state.get("current_goal", {})
    print("=" * 60)
    print(" PROJECT STATUS & MEMORY SUMMARY")
    print("=" * 60)
    print(f"Goal:        {goal.get('name', 'N/A')}")
    print(f"Description: {goal.get('description', 'N/A')}")
    print(f"Status:      {goal.get('status', 'N/A').upper()} ({goal.get('progress', 0)}% complete)")
    print(f"Started At:  {goal.get('started_at', 'N/A')}")
    print(f"Updated At:  {goal.get('updated_at', 'N/A')}")
    print("-" * 60)

    mapping = state.get("files_mapping", {})
    if mapping:
        print("Key File Mapping:")
        for file, desc in mapping.items():
            print(f"  - {file}: {desc}")
    else:
        print("Key File Mapping: None")

    print("-" * 60)
    milestones = state.get("milestones", [])
    if milestones:
        print("Milestones:")
        for m in milestones:
            status_char = "[x]" if m.get("status") == "completed" else "[ ]"
            print(f"  {status_char} {m.get('name')} (Completed: {m.get('completed_at', 'N/A')})")
    else:
        print("Milestones: None")

    print("-" * 60)
    print(f"Lessons Learned Logged: {len(lessons)}")
    print("=" * 60)


def cmd_set_goal(args):
    """Sets the current goal name and description."""
    state = load_json(STATE_FILE, DEFAULT_STATE)
    ts = get_timestamp()
    state["current_goal"] = {
        "name": args.name,
        "description": args.description or "No description set.",
        "status": "in_progress",
        "progress": args.progress or 0,
        "started_at": ts,
        "updated_at": ts,
    }
    save_json(STATE_FILE, state)
    print(f"Successfully set goal to: {args.name}")


def cmd_update_goal(args):
    """Updates goal progress, status, and adds milestones if completed."""
    state = load_json(STATE_FILE, DEFAULT_STATE)
    goal = state.get("current_goal", {})

    if args.status:
        goal["status"] = args.status
    if args.progress is not None:
        goal["progress"] = args.progress

    goal["updated_at"] = get_timestamp()
    state["current_goal"] = goal

    if args.milestone:
        ts = get_timestamp()
        milestones = state.get("milestones", [])
        milestones.append({"name": args.milestone, "status": "completed", "completed_at": ts})
        state["milestones"] = milestones
        print(f"Added milestone: {args.milestone}")

    save_json(STATE_FILE, state)
    print(f"Updated goal progress to {goal.get('progress')}% ({goal.get('status')})")


def cmd_add_lesson(args):
    """Adds a new lesson learned to the lessons.json file."""
    lessons = load_json(LESSONS_FILE, [])
    next_id = max([item.get("id", 0) for item in lessons] + [0]) + 1

    tags = [t.strip().lower() for t in args.tags.split(",") if t.strip()] if args.tags else []

    lesson = {
        "id": next_id,
        "topic": args.topic,
        "lesson": args.lesson,
        "tags": tags,
        "created_at": get_timestamp(),
    }
    lessons.append(lesson)
    save_json(LESSONS_FILE, lessons)
    print(f"Lesson added successfully under ID {next_id}: {args.topic}")


def cmd_search(args):
    """Searches lessons for matching keywords in topic, lesson content, or tags."""
    lessons = load_json(LESSONS_FILE, [])
    query = args.query.lower()

    matches = []
    for item in lessons:
        topic_match = query in item.get("topic", "").lower()
        content_match = query in item.get("lesson", "").lower()
        tag_match = any(query in tag for tag in item.get("tags", []))

        if topic_match or content_match or tag_match:
            matches.append(item)

    if not matches:
        print(f"No lessons found matching: '{args.query}'")
        return

    print(f"Found {len(matches)} matching lesson(s):")
    for m in matches:
        print("-" * 60)
        print(f"[{m.get('id')}] Topic: {m.get('topic')}")
        print(f"Tags: {', '.join(m.get('tags', []))}")
        print(f"Lesson: {m.get('lesson')}")
    print("-" * 60)


def cmd_compress(args):
    """Saves all memory files using a compact single-line layout to conserve tokens."""
    state = load_json(STATE_FILE, DEFAULT_STATE)
    lessons = load_json(LESSONS_FILE, [])

    save_json(STATE_FILE, state, compact=True)
    save_json(LESSONS_FILE, lessons, compact=True)

    state_size = os.path.getsize(STATE_FILE)
    lessons_size = os.path.getsize(LESSONS_FILE)

    print("Memory files compressed successfully:")
    print(f"  - state.json size: {state_size} bytes")
    print(f"  - lessons.json size: {lessons_size} bytes")


def cmd_sync_git(args):
    """Automatically scans modified/untracked files via git status and maps them in state.json."""
    import subprocess
    state = load_json(STATE_FILE, DEFAULT_STATE)
    try:
        # Run git status --porcelain -u
        result = subprocess.run(
            ["git", "status", "--porcelain", "-u"],
            capture_output=True, text=True, check=True
        )
        lines = result.stdout.strip().split("\n")
        mapping = state.setdefault("files_mapping", {})
        
        current_modified = {}
        for line in lines:
            if not line:
                continue
            status_code = line[:2].strip()
            filepath = line[3:].strip()
            
            if ".agent/" in filepath or "project_template.zip" in filepath or not filepath:
                continue
            
            current_modified[filepath] = status_code
            
        new_mapping = {}
        updated = False
        
        for filepath, status_code in current_modified.items():
            desc = f"Modified ({status_code})"
            if filepath in mapping:
                old_desc = mapping[filepath]
                if "Modified (" in old_desc:
                    new_mapping[filepath] = desc
                    if old_desc != desc:
                        updated = True
                else:
                    new_mapping[filepath] = old_desc
            else:
                new_mapping[filepath] = desc
                updated = True
                
        if len(new_mapping) != len(mapping):
            updated = True
            
        if updated:
            state["files_mapping"] = new_mapping
            save_json(STATE_FILE, state)
            print("Successfully updated state.json files_mapping based on git status.")
        else:
            print("No changes in modified files to sync to state.json.")
    except Exception as e:
        print(f"Error syncing with git: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Workspace Memory CLI helper for Antigravity agents"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Init subcommand
    subparsers.add_parser("init", help="Initialize memory directory and databases")

    # Status subcommand
    subparsers.add_parser("status", help="Show current goal and status")

    # Set Goal subcommand
    p_set_goal = subparsers.add_parser("set-goal", help="Set the active goal")
    p_set_goal.add_argument("name", help="Goal name")
    p_set_goal.add_argument("--description", "-d", help="Goal description")
    p_set_goal.add_argument(
        "--progress", "-p", type=int, default=0, help="Initial progress (0-100)"
    )

    # Update Goal subcommand
    p_update_goal = subparsers.add_parser("update-goal", help="Update the active goal progress")
    p_update_goal.add_argument(
        "--status",
        "-s",
        choices=["not_started", "in_progress", "completed"],
        help="Update status",
    )
    p_update_goal.add_argument("--progress", "-p", type=int, help="Update progress (0-100)")
    p_update_goal.add_argument("--milestone", "-m", help="Add a completed milestone")

    # Add Lesson subcommand
    p_add_lesson = subparsers.add_parser("add-lesson", help="Add a lesson learned")
    p_add_lesson.add_argument("topic", help="Topic of the lesson")
    p_add_lesson.add_argument("lesson", help="Detailed description of the lesson")
    p_add_lesson.add_argument("--tags", "-t", help="Comma-separated list of tags")

    # Search subcommand
    p_search = subparsers.add_parser("search", help="Search lessons learned")
    p_search.add_argument("query", help="Query string")

    # Compress subcommand
    subparsers.add_parser("compress", help="Compress memory JSON files to save tokens")

    # Sync Git subcommand
    subparsers.add_parser("sync-git", help="Auto-sync modified files from git status to state.json")

    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "status": cmd_status,
        "set-goal": cmd_set_goal,
        "update-goal": cmd_update_goal,
        "add-lesson": cmd_add_lesson,
        "search": cmd_search,
        "compress": cmd_compress,
        "sync-git": cmd_sync_git,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()

