"""Unit tests for Native Window Launcher and NativeAPI bridge."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))

from ui.app_window import NativeAPI, find_free_port  # noqa: E402


def test_find_free_port():
    """Verify free port detection returns a valid port."""
    port = find_free_port(start_port=8900)
    assert isinstance(port, int)
    assert port >= 8900


def test_native_api_metadata():
    """Verify NativeAPI returns correct app info."""
    api = NativeAPI()
    info = api.get_version_info()
    assert info["name"] == "TeamTrau Anime Downloader"
    assert info["version"] == "v2.2.0"
    assert info["native"] is True


def test_native_api_window_controls():
    """Verify NativeAPI window controls interact with mock window object."""
    mock_window = MagicMock()
    api = NativeAPI(window=mock_window)

    res_min = api.minimize_window()
    assert res_min["success"] is True
    mock_window.minimize.assert_called_once()

    res_max = api.maximize_window()
    assert res_max["success"] is True

    res_close = api.close_window()
    assert res_close["success"] is True
    mock_window.destroy.assert_called_once()


def test_native_api_open_folder(tmp_path):
    """Verify NativeAPI open folder resolves without crashing."""
    api = NativeAPI()
    test_dir = tmp_path / "test_downloads"
    res = api.open_folder(str(test_dir))
    assert res["success"] is True
    assert test_dir.exists()


def test_native_api_start_drag():
    """Verify start_drag handles mock window handle gracefully."""
    mock_window = MagicMock()
    mock_target = MagicMock()
    mock_handle = MagicMock()
    mock_handle.ToInt64.return_value = 12345
    mock_target.Handle = mock_handle
    mock_window.native = mock_target

    api = NativeAPI(window=mock_window)
    res = api.start_drag()
    assert isinstance(res, dict)
    assert "success" in res
