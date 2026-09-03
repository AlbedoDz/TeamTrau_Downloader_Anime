"""Unit tests for SafeConsole and Unicode safety on Windows charmap/cp1252."""

import io
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))

from downloader.utils import SafeConsole  # noqa: E402


class MockCharmapStream(io.StringIO):
    """Simulates a legacy Windows cp1252/charmap stream that fails on Vietnamese characters."""

    encoding = "cp1252"

    def write(self, s: str) -> int:
        # Simulate cp1252 encoder failing on Vietnamese character \u0110
        s.encode("cp1252")
        return super().write(s)


def test_safe_console_handles_vietnamese_unicode_on_cp1252():
    """Verify SafeConsole prevents UnicodeEncodeError crashes on legacy streams."""
    bad_stream = MockCharmapStream()
    safe_console = SafeConsole(file=bad_stream)

    # Should not raise UnicodeEncodeError
    test_msg = "Đang xử lý Bungo Stray Dogs WAN! 2 - S01E02 (1/1)"
    safe_console.print(f"[M3U8_STREAM] {test_msg}")

    output = bad_stream.getvalue()
    assert len(output) > 0
    # Confirm fallback sanitized character occurred instead of unhandled crash
    assert "Bungo Stray Dogs" in output
