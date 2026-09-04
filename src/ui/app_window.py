"""TeamTrau Anime Downloader - Native Windows 11 Application Launcher.

Provides a frameless native desktop window utilizing Microsoft Edge WebView2
(via pywebview) with custom titlebar controls, Mica/dark styling, and graceful IPC.
"""

import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

# Force UTF-8 across entire process and streams on Windows
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Canonical project root resolution (supports both python source and PyInstaller frozen exe)
if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

sys.path.insert(0, str(PROJECT_ROOT / "src"))

from http.server import ThreadingHTTPServer

from core.logger import manager_logger
from core.queue_manager import queue_manager
from ui.server import TeamTrauAPIHandler


def find_free_port(start_port: int = 8765, max_attempts: int = 50) -> int:
    """Find an available TCP port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port


class NativeAPI:
    """IPC Bridge exposed to JavaScript via window.pywebview.api."""

    def __init__(self, window=None):
        self.window = window
        self._is_maximized = False

    def set_window(self, window):
        self.window = window

    def minimize_window(self) -> dict:
        """Minimize the native window asynchronously."""
        if self.window:
            try:
                self.window.minimize()
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": False, "error": "No native window handle"}

    def maximize_window(self) -> dict:
        """Toggle maximize/restore state safely without freezing WinForms."""
        if self.window:
            try:
                if self._is_maximized:
                    self.window.restore()
                    self._is_maximized = False
                else:
                    self.window.maximize()
                    self._is_maximized = True
                return {"success": True, "maximized": self._is_maximized}
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": False, "error": "No native window handle"}

    def close_window(self) -> dict:
        """Gracefully close the native application without blocking the UI thread."""
        if self.window:
            try:
                # Decouple queue shutdown into background thread to prevent UI thread lock
                threading.Thread(target=queue_manager.shutdown, daemon=True).start()
                self.window.destroy()
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": False, "error": "No native window handle"}

    def start_drag(self) -> dict:
        """Initiate native Windows 11 hardware window drag via WM_SYSCOMMAND SC_DRAGMOVE."""
        if self.window:
            try:
                import ctypes

                target = getattr(self.window, "native", None) or getattr(self.window, "gui", None)
                if target and hasattr(target, "Handle"):
                    hwnd = int(target.Handle.ToInt64())

                    def _do_drag():
                        ctypes.windll.user32.ReleaseCapture()
                        # 0x0112 = WM_SYSCOMMAND, 0xF012 = SC_DRAGMOVE (Native Windows hardware drag)
                        ctypes.windll.user32.SendMessageW(hwnd, 0x0112, 0xF012, 0)

                    if hasattr(target, "InvokeRequired") and target.InvokeRequired:
                        from System import Func, Type

                        target.BeginInvoke(Func[Type](_do_drag))
                    else:
                        _do_drag()
                    return {"success": True}
            except Exception as e:
                manager_logger.log("warn", "general", f"start_drag error: {e}")
                return {"success": False, "error": str(e)}
        return {"success": False, "error": "No window handle"}

    def select_folder(self, default_path: str = "") -> str:
        """Open native OS directory picker dialog without freezing the main loop."""
        resolved_dir = (
            str(Path(default_path).resolve()) if default_path else str(Path.home() / "Downloads")
        )
        if self.window:
            try:
                import webview

                result = self.window.create_file_dialog(
                    webview.FOLDER_DIALOG,
                    directory=resolved_dir,
                )
                if result and len(result) > 0:
                    return result[0]
            except Exception as e:
                manager_logger.log("warning", "general", f"pywebview folder dialog fallback: {e}")

        # Fallback to native Tkinter dialog (100% reliable on Windows)
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            selected = filedialog.askdirectory(
                initialdir=resolved_dir, title="Chọn thư mục tải xuống"
            )
            root.destroy()
            return selected or ""
        except Exception as e:
            manager_logger.log("error", "general", f"Lỗi chọn thư mục: {e}")
            return ""

    def open_folder(self, folder_path: str) -> dict:
        """Open folder in Windows File Explorer."""
        target = Path(folder_path).resolve()
        if not target.exists():
            target.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(str(target))
            else:
                subprocess.Popen(["xdg-open", str(target)])
            return {"success": True}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def read_clipboard(self) -> str:
        """Read clipboard text using native 64-bit Win32 API without spawning Tkinter UI."""
        if sys.platform == "win32":
            try:
                import ctypes

                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32

                user32.OpenClipboard.argtypes = [ctypes.c_void_p]
                user32.OpenClipboard.restype = ctypes.c_bool
                user32.CloseClipboard.argtypes = []
                user32.CloseClipboard.restype = ctypes.c_bool
                user32.GetClipboardData.argtypes = [ctypes.c_uint]
                user32.GetClipboardData.restype = ctypes.c_void_p
                kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
                kernel32.GlobalLock.restype = ctypes.c_void_p
                kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
                kernel32.GlobalUnlock.restype = ctypes.c_bool

                # Try opening clipboard with quick retry (non-blocking)
                for _ in range(3):
                    if user32.OpenClipboard(None):
                        try:
                            # 13 = CF_UNICODETEXT
                            h_data = user32.GetClipboardData(13)
                            if h_data:
                                p_data = kernel32.GlobalLock(h_data)
                                if p_data:
                                    try:
                                        val = ctypes.c_wchar_p(p_data).value
                                        return str(val).strip() if val else ""
                                    finally:
                                        kernel32.GlobalUnlock(h_data)
                        finally:
                            user32.CloseClipboard()
                        break
                    time.sleep(0.01)
            except Exception:
                pass

        # Fallback to Tkinter if Win32 API fails
        try:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            content = root.clipboard_get()
            root.destroy()
            return str(content).strip() if content else ""
        except Exception:
            return ""

    def get_version_info(self) -> dict:
        """Return app metadata."""
        return {
            "name": "TeamTrau Anime Downloader",
            "version": "v2.2.0",
            "edition": "Windows 11 Native Edition",
            "author": "TeamTrau & AlbedoDz",
            "native": True,
        }


def start_background_server(port: int) -> ThreadingHTTPServer:
    """Run UI HTTP Server in a background daemon thread with short socket timeouts."""
    server_address = ("127.0.0.1", port)
    httpd = ThreadingHTTPServer(server_address, TeamTrauAPIHandler)
    httpd.timeout = 2.0
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    manager_logger.log(
        "info",
        "general",
        f"Native UI Server started on http://127.0.0.1:{port}/",
    )
    return httpd


def run_native_app():
    """Main entrypoint for native Windows 11 application."""
    port = find_free_port(8765)
    start_background_server(port)

    # Active micro-polling for server readiness (replaces slow static 200ms sleep)
    start_time = time.perf_counter()
    while time.perf_counter() - start_time < 1.0:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.05)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                break
        time.sleep(0.01)
    app_url = f"http://127.0.0.1:{port}/"

    # Try launching via pywebview (Edge WebView2)
    try:
        import webview

        # Disable pywebview's internal JS mousemove loop to prevent IPC flooding & lag
        webview.settings["DRAG_REGION_SELECTOR"] = ".__disabled_drag_region__"

        api = NativeAPI()
        window = webview.create_window(
            title="TeamTrau Anime Downloader",
            url=app_url,
            js_api=api,
            width=1200,
            height=800,
            min_size=(980, 640),
            frameless=True,  # Windows 11 custom titlebar
            easy_drag=False,  # Use 100% native Win32 hardware drag via start_drag()
            background_color="#0A0D14",
        )
        api.set_window(window)

        # Cleanup on close
        def on_closing():
            manager_logger.log("info", "general", "Application window closing, cleaning up...")
            try:
                queue_manager.shutdown()
            except Exception:
                pass

        window.events.closing += on_closing

        # Resolve application icon
        icon_file = PROJECT_ROOT / "src" / "ui" / "assets" / "icon.ico"
        if not icon_file.exists():
            icon_file = PROJECT_ROOT / "ui" / "assets" / "icon.ico"
        icon_arg = str(icon_file) if icon_file.exists() else None

        # Start pywebview event loop (using edgechromium / WebView2)
        webview.start(gui="edgechromium", debug=False, icon=icon_arg)

    except ImportError:
        # Fallback to Microsoft Edge App Mode if pywebview is unavailable
        manager_logger.log(
            "warning",
            "general",
            "pywebview not available. Falling back to Microsoft Edge App Mode.",
        )
        try:
            subprocess.Popen(
                [
                    "msedge.exe",
                    f"--app={app_url}",
                    "--window-size=1200,800",
                ]
            )
        except Exception:
            import webbrowser

            webbrowser.open(app_url)


if __name__ == "__main__":
    run_native_app()
