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
