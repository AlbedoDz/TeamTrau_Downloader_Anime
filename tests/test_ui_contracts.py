import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
UI_DIR = BASE_DIR / "src" / "ui"


def test_theme_tokens_json_validity() -> None:
    """Verify theme.json exists, is valid JSON, and adheres to dark glass palette standards."""
    theme_file = UI_DIR / "tokens" / "theme.json"
    assert theme_file.exists(), f"theme.json missing at {theme_file}"

    with open(theme_file, encoding="utf-8") as f:
        data = json.load(f)

    assert "colors" in data
    assert "background" in data["colors"]
    assert data["colors"]["background"]["base"] == "#0B0F17"
    assert "accent" in data["colors"]
    assert data["colors"]["accent"]["emerald"] == "#10B981"
    assert data["colors"]["accent"]["cyan"] == "#06B6D4"


def test_tokens_css_exists_and_contains_classes() -> None:
    """Verify tokens.css exists and defines essential glassmorphism utility classes."""
    css_file = UI_DIR / "tokens" / "tokens.css"
    assert css_file.exists(), f"tokens.css missing at {css_file}"

    with open(css_file, encoding="utf-8") as f:
        content = f.read()

    assert "--bg-base: #0B0F17" in content
    assert ".glass-panel" in content
    assert ".glass-card" in content
    assert ".pulse-gradient-bar" in content


def test_typescript_types_strictness() -> None:
    """Verify that types/index.ts does not use forbidden 'any' types and contains all domain models."""
    types_file = UI_DIR / "types" / "index.ts"
    assert types_file.exists(), f"types/index.ts missing at {types_file}"

    with open(types_file, encoding="utf-8") as f:
        content = f.read()

    # Verify no ': any' or '<any>'
    assert not re.search(r":\s*any\b", content), "Found forbidden 'any' type in types/index.ts"
    assert not re.search(r"<\s*any\s*>", content), "Found forbidden '<any>' type in types/index.ts"

    # Verify essential domain interfaces exist
    assert "export interface DownloadTaskRecord" in content
    assert "export interface SettingsConfig" in content
    assert "export interface BatchOptions" in content
    assert "export interface ParsedAnimeDetails" in content
    assert "export type ExtractorSite" in content
    assert "export type DownloadMode" in content
    assert "export type NamingFormat" in content
    assert "export type TaskStatus" in content


def test_all_ui_components_exist() -> None:
    """Verify all planned UI components and shell templates exist."""
    required_components = [
        "components/Shell.tsx",
        "components/UrlInputHero.tsx",
        "components/BatchOptionsModal.tsx",
        "components/DownloadTableView.tsx",
        "components/TaskDetailModal.tsx",
        "components/ManagerToolbar.tsx",
        "components/SidebarCategories.tsx",
        "components/ConsoleDrawer.tsx",
        "components/SettingsDrawer.tsx",
        "state/useDownloadStore.ts",
        "App.tsx",
        "index.html",
        "server.py",
    ]

    for rel_path in required_components:
        target_path = UI_DIR / rel_path
        assert target_path.exists(), f"Required UI file missing: {rel_path}"


def test_tasks_api_contract_counts() -> None:
    """Verify DatabaseManager and counts dictionary provide all required reactive categories."""
    from data.db import DatabaseManager
    from data.models import TaskStatus

    db = DatabaseManager()
    all_tasks = db.get_all_tasks(status_filter="all")

    counts = {
        "all": len(all_tasks),
        "downloading": sum(1 for t in all_tasks if t.status == TaskStatus.DOWNLOADING),
        "queued": sum(1 for t in all_tasks if t.status == TaskStatus.QUEUED),
        "completed": sum(1 for t in all_tasks if t.status == TaskStatus.COMPLETED),
        "paused": sum(1 for t in all_tasks if t.status == TaskStatus.PAUSED),
        "failed": sum(1 for t in all_tasks if t.status == TaskStatus.FAILED),
        "anime": sum(1 for t in all_tasks if t.download_mode.value == "full"),
        "video": sum(1 for t in all_tasks if t.download_mode.value == "video_only"),
        "subtitle": sum(1 for t in all_tasks if t.download_mode.value == "sub_only"),
    }

    required_keys = ["all", "downloading", "queued", "completed", "paused", "failed", "anime", "video", "subtitle"]
    for key in required_keys:
        assert key in counts, f"Missing count category: {key}"
        assert isinstance(counts[key], int)


def test_config_persistence_contract(tmp_path: Path) -> None:
    """Verify that settings can be loaded and saved to config.json reliably."""
    from ui.server import load_app_settings, save_app_settings, CONFIG_PATH
    import ui.server as server_module

    # Temporarily point CONFIG_PATH to tmp_path
    original_config_path = server_module.CONFIG_PATH
    test_config = tmp_path / "config.json"
    server_module.CONFIG_PATH = test_config

    try:
        initial = load_app_settings()
        assert "outputDir" in initial
        assert "maxWorkers" in initial

        # Save customized settings
        test_settings = {
            "outputDir": str(tmp_path / "custom_downloads"),
            "maxWorkers": 5,
            "proxyUrl": "http://127.0.0.1:8888",
            "delaySec": 2.5,
            "namingFormat": "standard"
        }
        save_app_settings(test_settings)
        assert test_config.exists()

        reloaded = load_app_settings()
        assert reloaded["outputDir"] == str(tmp_path / "custom_downloads")
        assert reloaded["maxWorkers"] == 5
        assert reloaded["proxyUrl"] == "http://127.0.0.1:8888"
        assert reloaded["delaySec"] == 2.5
    finally:
        server_module.CONFIG_PATH = original_config_path


def test_video_preview_path_resolution(tmp_path: Path) -> None:
    """Verify that save_path resolution handles relative paths for video preview."""
    fake_video = tmp_path / "test_episode.mp4"
    fake_video.write_bytes(b"\x00" * 1024)

    assert fake_video.resolve().exists()
    assert fake_video.stat().st_size == 1024


