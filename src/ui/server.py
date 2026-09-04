import json
import os
import re
import subprocess
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

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

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.logger import manager_logger  # noqa: E402
from core.queue_manager import queue_manager  # noqa: E402
from data.db import DatabaseManager  # noqa: E402
from data.models import DownloadMode, TaskStatus  # noqa: E402
from downloader.extractor import get_extractor_for_url  # noqa: E402
from downloader.utils import HttpClient  # noqa: E402

PORT = 8765

# Robust static directory resolution (supports normal Python, PyInstaller onedir and onefile)
if getattr(sys, "frozen", False):
    candidate_bases = [
        getattr(sys, "_MEIPASS", None),
        Path(sys.executable).parent / "_internal",
        Path(sys.executable).parent,
    ]
    STATIC_DIR = Path(__file__).resolve().parent
    for base in candidate_bases:
        if base:
            b_path = Path(base)
            if (b_path / "ui" / "index.html").exists():
                STATIC_DIR = b_path / "ui"
                break
            elif (b_path / "index.html").exists():
                STATIC_DIR = b_path
                break
else:
    STATIC_DIR = Path(__file__).resolve().parent


# Fast In-Memory Task Cache with 0.4s TTL to eliminate SQLite lock contention on rapid polling
_TASKS_CACHE = {
    "timestamp": 0.0,
    "all_tasks": [],
    "counts": {},
}
_CACHE_LOCK = threading.Lock()


def invalidate_tasks_cache() -> None:
    """Invalidate cached tasks so next poll immediately reflects mutations."""
    with _CACHE_LOCK:
        _TASKS_CACHE["timestamp"] = 0.0


CONFIG_PATH = PROJECT_ROOT / "config.json"


def load_app_settings() -> dict:
    default_settings = {
        "outputDir": str((PROJECT_ROOT / "downloads").resolve()),
        "maxWorkers": 3,
        "proxyUrl": "",
        "delaySec": 1.0,
        "namingFormat": "simple",
        "autoDetectClipboard": False,
    }
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                data = json.load(f)
                default_settings.update(data)
        except Exception:
            pass
    return default_settings


def save_app_settings(settings_dict: dict) -> None:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(settings_dict, f, indent=2, ensure_ascii=False)
    except Exception as e:
        manager_logger.log("error", "general", f"Lỗi lưu file config.json: {e}")


class TeamTrauAPIHandler(SimpleHTTPRequestHandler):
    """Modern Download Manager REST API and Static File Server Handler."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, format, *args):
        # Silence default HTTP server console noise
        pass

    def send_json(self, data: dict | list, status_code: int = 200) -> None:
        """Helper to send JSON response with standard CORS headers."""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        """Handle CORS pre-flight requests."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def end_headers(self):
        """Inject high-performance caching headers for static assets."""
        path_lower = getattr(self, "path", "").lower().split("?")[0]
        if any(
            path_lower.endswith(ext) for ext in (".js", ".css", ".svg", ".ico", ".png", ".woff2")
        ):
            self.send_header("Cache-Control", "public, max-age=86400")
        super().end_headers()

    def stream_video_file(self, file_path: Path):
        """Stream local MP4/MKV video with HTTP Range header support for seeking."""
        file_size = file_path.stat().st_size
        range_header = self.headers.get("Range")

        content_type = "video/mp4"
        if file_path.suffix.lower() == ".mkv":
            content_type = "video/x-matroska"
        elif file_path.suffix.lower() == ".webm":
            content_type = "video/webm"

        if range_header:
            try:
                range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
                if range_match:
                    start_byte = int(range_match.group(1))
                    end_byte = int(range_match.group(2)) if range_match.group(2) else file_size - 1
                    length = end_byte - start_byte + 1

                    self.send_response(206)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Range", f"bytes {start_byte}-{end_byte}/{file_size}")
                    self.send_header("Content-Length", str(length))
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()

                    with open(file_path, "rb") as f:
                        f.seek(start_byte)
                        remaining = length
                        while remaining > 0:
                            chunk_size = min(remaining, 64 * 1024)
                            chunk = f.read(chunk_size)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            remaining -= len(chunk)
                    return
            except Exception:
                pass

        # Full file response
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(file_size))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        with open(file_path, "rb") as f:
            while chunk := f.read(64 * 1024):
                self.wfile.write(chunk)

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)

        # GET /api/tasks (Download Manager Master Table View)
        if path == "/api/tasks":
            status_filter = query_params.get("status", ["all"])[0]
            category_filter = query_params.get("category", ["all"])[0]
            search_query = query_params.get("q", [None])[0]

            now = time.time()
            with _CACHE_LOCK:
                if now - _TASKS_CACHE["timestamp"] < 0.4 and _TASKS_CACHE["all_tasks"]:
                    all_tasks = _TASKS_CACHE["all_tasks"]
                    counts = _TASKS_CACHE["counts"]
                else:
                    db = DatabaseManager()
                    all_tasks = db.get_all_tasks(status_filter="all")
                    counts = {
                        "all": len(all_tasks),
                        "downloading": sum(
                            1 for t in all_tasks if t.status == TaskStatus.DOWNLOADING
                        ),
                        "queued": sum(1 for t in all_tasks if t.status == TaskStatus.QUEUED),
                        "completed": sum(1 for t in all_tasks if t.status == TaskStatus.COMPLETED),
                        "paused": sum(1 for t in all_tasks if t.status == TaskStatus.PAUSED),
                        "failed": sum(1 for t in all_tasks if t.status == TaskStatus.FAILED),
                        "anime": sum(1 for t in all_tasks if t.download_mode.value == "full"),
                        "video": sum(1 for t in all_tasks if t.download_mode.value == "video_only"),
                        "subtitle": sum(
                            1 for t in all_tasks if t.download_mode.value == "sub_only"
                        ),
                    }
                    _TASKS_CACHE["timestamp"] = now
                    _TASKS_CACHE["all_tasks"] = all_tasks
                    _TASKS_CACHE["counts"] = counts

            # In-memory fast filter
            filtered_tasks = all_tasks
            if status_filter != "all":
                filtered_tasks = [t for t in filtered_tasks if t.status.value == status_filter]
            if category_filter != "all":
                filtered_tasks = [
                    t for t in filtered_tasks if t.download_mode.value == category_filter
                ]
            if search_query:
                sq = search_query.lower()
                filtered_tasks = [
                    t for t in filtered_tasks if sq in t.anime_title.lower() or sq in t.site.lower()
                ]

            self.send_json(
                {
                    "success": True,
                    "tasks": [t.to_dict() for t in filtered_tasks],
                    "all_tasks": [t.to_dict() for t in all_tasks],
                    "counts": counts,
                    "config": queue_manager.config.to_dict(),
                }
            )
            return

        # GET /api/tasks/<task_id>/logs
        if path.startswith("/api/tasks/") and path.endswith("/logs"):
            task_id = path.replace("/api/tasks/", "").replace("/logs", "").strip("/")
            logs = manager_logger.get_task_logs(task_id)
            self.send_json({"success": True, "taskId": task_id, "logs": logs})
            return

        # GET /api/logs (System Session Logs)
        if path == "/api/logs":
            level = query_params.get("level", ["ALL"])[0]
            category = query_params.get("category", ["all"])[0]
            logs = manager_logger.get_system_logs(level_filter=level, category_filter=category)
            self.send_json({"success": True, "logs": logs})
            return

        # GET /api/history (High-scale paginated completed batch history)
        if path == "/api/history":
            try:
                limit = int(query_params.get("limit", [100])[0])
                offset = int(query_params.get("offset", [0])[0])
            except ValueError:
                limit, offset = 100, 0
            db = DatabaseManager()
            history_tasks = db.get_completed_tasks_history(limit=limit, offset=offset)
            self.send_json(
                {
                    "success": True,
                    "history": [t.to_dict() for t in history_tasks],
                    "limit": limit,
                    "offset": offset,
                }
            )
            return

        # Legacy /api/status endpoint
        if path == "/api/status":
            db = DatabaseManager()
            all_tasks = db.get_all_tasks(status_filter="all")
            system_logs = manager_logger.get_system_logs(limit=80)
            is_downloading = any(t.status == TaskStatus.DOWNLOADING for t in all_tasks)
            self.send_json(
                {
                    "success": True,
                    "tasks": [t.to_dict() for t in all_tasks],
                    "logs": system_logs,
                    "isDownloading": is_downloading,
                }
            )
        # GET /api/config
        if path == "/api/config":
            self.send_json({"success": True, "config": load_app_settings()})
            return

        # GET /api/video?id=<task_id> or /api/video?path=<encoded_path>
        if path == "/api/video":
            task_id = query_params.get("id", [None])[0]
            raw_path = query_params.get("path", [None])[0]

            file_path = None
            if task_id:
                task = DatabaseManager().get_task(task_id)
                if task and task.save_path:
                    file_path = Path(task.save_path).resolve()
            elif raw_path:
                file_path = Path(raw_path).resolve()

            if not file_path or not file_path.exists() or not file_path.is_file():
                self.send_json({"error": "Video file not found or not ready."}, status_code=404)
                return

            self.stream_video_file(file_path)
            return

        # Static file serving
        if path == "/" or path == "":
            self.path = "/index.html"

        super().do_GET()

    def do_POST(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        content_length = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            payload = json.loads(post_body.decode("utf-8")) if post_body else {}
        except Exception:
            payload = {}

        if path == "/api/parse":
            self.handle_parse_url(payload)
        elif path == "/api/tasks/create":
            self.handle_create_task(payload)
        elif path == "/api/download" or path == "/api/download/batch":
            self.handle_legacy_download(payload)
        elif path == "/api/queue/pause-all":
            queue_manager.pause_all()
            invalidate_tasks_cache()
            self.send_json({"success": True, "message": "Tất cả tác vụ đã tạm dừng."})
        elif path == "/api/queue/resume-all":
            queue_manager.resume_all()
            invalidate_tasks_cache()
            self.send_json({"success": True, "message": "Tất cả tác vụ đã tiếp tục."})
        elif path == "/api/queue/clear-completed":
            queue_manager.clear_completed()
            invalidate_tasks_cache()
            self.send_json({"success": True, "message": "Đã dọn dẹp các tác vụ hoàn thành."})
        elif path == "/api/queue/config":
            limit = int(payload.get("maxConcurrent", 3))
            queue_manager.set_concurrency_limit(limit)
            invalidate_tasks_cache()
            self.send_json({"success": True, "config": queue_manager.config.to_dict()})
        elif path == "/api/config":
            output_dir = payload.get("outputDir")
            max_workers = payload.get("maxWorkers")
            proxy_url = payload.get("proxyUrl")
            delay_sec = payload.get("delaySec")
            naming_format = payload.get("namingFormat")

            current_settings = load_app_settings()
            if output_dir:
                current_settings["outputDir"] = output_dir
            if max_workers is not None:
                current_settings["maxWorkers"] = int(max_workers)
                queue_manager.set_concurrency_limit(int(max_workers))
            if proxy_url is not None:
                current_settings["proxyUrl"] = proxy_url
            if delay_sec is not None:
                current_settings["delaySec"] = float(delay_sec)
            if naming_format:
                current_settings["namingFormat"] = naming_format
            if "autoDetectClipboard" in payload:
                current_settings["autoDetectClipboard"] = bool(payload["autoDetectClipboard"])

            save_app_settings(current_settings)
            invalidate_tasks_cache()
            self.send_json({"success": True, "config": current_settings})
        elif path == "/api/choose-folder":
            initial_dir = payload.get("defaultPath", "")
            resolved = (
                str(Path(initial_dir).resolve()) if initial_dir else str(Path.home() / "Downloads")
            )
            selected = ""
            try:
                import tkinter as tk
                from tkinter import filedialog

                root = tk.Tk()
                root.withdraw()
                root.attributes("-topmost", True)
                selected = filedialog.askdirectory(
                    initialdir=resolved, title="Chọn thư mục tải xuống"
                )
                root.destroy()
            except Exception as e:
                manager_logger.log("error", "general", f"Lỗi chọn thư mục: {e}")

            if selected:
                self.send_json({"success": True, "folder": selected})
            else:
                self.send_json({"success": False, "folder": "", "cancelled": True})
        elif path == "/api/cancel":
            queue_manager.pause_all()
            invalidate_tasks_cache()
            self.send_json({"success": True, "message": "Đã tạm dừng tiến trình."})
        elif path == "/api/logs/clear":
            manager_logger.clear_system_logs()
            self.send_json({"success": True})
        elif path.startswith("/api/tasks/"):
            self.handle_task_action(path, payload)
        else:
            self.send_json({"error": f"Endpoint {path} not found"}, status_code=404)

    def handle_parse_url(self, payload: dict):
        """Parse anime metadata and episode list from source URL."""
        url = payload.get("url", "").strip()
        if not url:
            self.send_json({"success": False, "error": "URL cannot be empty"}, status_code=400)
            return

        manager_logger.log("info", "waf_bypass", f"Nhận yêu cầu phân tích URL: {url}")
        try:
            http_client = HttpClient()
            extractor = get_extractor_for_url(url, http_client)
            if not extractor:
                msg = "Không tìm thấy module trích xuất phù hợp cho URL này."
                manager_logger.log("error", "general", msg)
                self.send_json({"success": False, "error": msg}, status_code=400)
                return

            details = extractor.get_anime_details(url)

            # Determine site name
            site_name = "unknown"
            if "anikoto" in url.lower():
                site_name = "anikoto"
            elif "animesuge" in url.lower():
                site_name = "animesuge"
            elif "allwish" in url.lower() or "all-wish" in url.lower():
                site_name = "allwish"
            elif "animecube" in url.lower():
                site_name = "animecube"

            episodes = details.get("episodes", [])
            total_episodes = len(episodes)

            result = {
                "success": True,
                "rawUrl": url,
                "site": site_name,
                "title": details.get("title", "Anime Series"),
                "totalEpisodes": total_episodes,
                "episodes": [
                    {
                        "num": ep.get("num", str(i + 1)),
                        "title": f"Tập {ep.get('num', str(i + 1))}",
                        "slug": ep.get("slug", ""),
                        "url": ep.get("url", ""),
                        "selected": True,
                    }
                    for i, ep in enumerate(episodes)
                ],
                "availableQualities": [
                    {
                        "id": "720p",
                        "label": "720p (HD - Mặc Định Khuyên Dùng)",
                        "resolution": "1280x720",
                        "isRecommended": True,
                    },
                    {
                        "id": "1080p",
                        "label": "1080p (Full HD)",
                        "resolution": "1920x1080",
                        "isRecommended": False,
                    },
                    {
                        "id": "480p",
                        "label": "480p (SD - Tiêu Chuẩn)",
                        "resolution": "854x480",
                        "isRecommended": False,
                    },
                    {
                        "id": "360p",
                        "label": "360p (Low - Nhẹ Nhất)",
                        "resolution": "640x360",
                        "isRecommended": False,
                    },
                    {
                        "id": "auto",
                        "label": "Auto (Tự Động Chọn Cao Nhất)",
                        "resolution": "Best",
                        "isRecommended": False,
                    },
                ],
                "availableServers": [
                    {
                        "id": "srv_auto",
                        "name": "Auto Default",
                        "serverId": "auto",
                        "isPreferred": True,
                    },
                    {
                        "id": "srv_megaplay",
                        "name": "MegaPlay Server",
                        "serverId": "megaplay",
                        "isPreferred": False,
                    },
                ],
                "availableSubtitles": [
                    {
                        "id": "sub_es_la",
                        "langCode": "es-LA",
                        "label": "Spanish (Latin America - es-LA)",
                        "format": "vtt",
                        "isSelected": True,
                    },
                    {
                        "id": "sub_es_es",
                        "langCode": "es-ES",
                        "label": "Spanish (Spain - es-ES)",
                        "format": "vtt",
                        "isSelected": False,
                    },
                    {
                        "id": "sub_en",
                        "langCode": "en",
                        "label": "English",
                        "format": "ass",
                        "isSelected": True,
                    },
                    {
                        "id": "sub_vi",
                        "langCode": "vi",
                        "label": "Tiếng Việt",
                        "format": "vtt",
                        "isSelected": False,
                    },
                ],
            }
            manager_logger.log(
                "success",
                "vrf_decrypt",
                f"Đã trích xuất thành công {total_episodes} tập của '{result['title']}' ({site_name.upper()}).",
            )
            self.send_json(result)
        except Exception as e:
            err_str = str(e)
            manager_logger.log("error", "vrf_decrypt", f"Lỗi giải mã/trích xuất: {err_str}")
            self.send_json({"success": False, "error": err_str}, status_code=500)

    def handle_create_task(self, payload: dict):
        """Add new tasks to SQLite Download Manager Queue."""
        url = payload.get("url", "").strip()
        title = payload.get("animeTitle", "Anime Series")
        episodes = payload.get("episodes", ["1"])
        site = payload.get("site", "allwish")
        quality = payload.get("quality", "720p")
        mode_str = payload.get("downloadMode", "full")
        target_subs = payload.get("targetSubLangs", ["es-LA", "en"])
        output_dir = payload.get("outputDir") or load_app_settings()["outputDir"]

        mode = DownloadMode.FULL
        if mode_str == "sub_only":
            mode = DownloadMode.SUB_ONLY
        elif mode_str == "video_only":
            mode = DownloadMode.VIDEO_ONLY

        task_specs = []
        for ep_num in episodes:
            ep_str = str(ep_num).zfill(2)
            save_path = str(Path(output_dir) / title / "Season 01" / f"{title} - S01E{ep_str}.mp4")
            task_specs.append(
                {
                    "url": url,
                    "anime_title": title,
                    "episode_num": str(ep_num),
                    "site": site,
                    "quality": quality,
                    "download_mode": mode,
                    "target_sub_langs": target_subs,
                    "save_path": save_path,
                }
            )

        created_records = queue_manager.add_tasks_batch(task_specs)
        created_tasks = [r.to_dict() for r in created_records]

        invalidate_tasks_cache()
        self.send_json(
            {
                "success": True,
                "message": f"Đã thêm {len(created_tasks)} tập vào hàng đợi tải.",
                "tasks": created_tasks,
            }
        )

    def handle_task_action(self, path: str, payload: dict):
        """Route task actions: pause, resume, restart, delete, open-file, open-folder."""
        parts = path.strip("/").split("/")
        # /api/tasks/<task_id>/<action>
        if len(parts) < 4:
            self.send_json({"error": "Đường dẫn không hợp lệ"}, status_code=400)
            return

        task_id = parts[2]
        action = parts[3]

        if action == "pause":
            queue_manager.pause_task(task_id)
            invalidate_tasks_cache()
            self.send_json({"success": True, "message": f"Tác vụ {task_id} đã tạm dừng."})
        elif action == "resume":
            queue_manager.resume_task(task_id)
            invalidate_tasks_cache()
            self.send_json({"success": True, "message": f"Tác vụ {task_id} đã tiếp tục."})
        elif action == "restart":
            queue_manager.restart_task(task_id)
            invalidate_tasks_cache()
            self.send_json({"success": True, "message": f"Tác vụ {task_id} đã đặt lại để tải lại."})
        elif action == "delete":
            delete_file = payload.get("deleteFile", False)
            queue_manager.delete_task(task_id, delete_file=delete_file)
            invalidate_tasks_cache()
            self.send_json({"success": True, "message": f"Đã xóa tác vụ {task_id}."})
        elif action == "open-file":
            task = DatabaseManager().get_task(task_id)
            if task and task.save_path:
                res_path = Path(task.save_path).resolve()
                if res_path.exists():
                    try:
                        if sys.platform == "win32":
                            os.startfile(str(res_path))
                        else:
                            subprocess.Popen(["xdg-open", str(res_path)])
                        self.send_json({"success": True, "message": "Đã mở file."})
                        return
                    except Exception as e:
                        self.send_json({"success": False, "error": str(e)}, status_code=500)
                        return
            self.send_json(
                {"success": False, "error": "File chưa tồn tại trên ổ đĩa."}, status_code=404
            )
        elif action == "open-folder":
            task = DatabaseManager().get_task(task_id)
            if task and task.save_path:
                target_dir = str(Path(task.save_path).parent)
                try:
                    if sys.platform == "win32":
                        if Path(task.save_path).exists():
                            subprocess.Popen(
                                f'explorer.exe /select,"{Path(task.save_path).resolve()}"'
                            )
                        else:
                            Path(target_dir).mkdir(parents=True, exist_ok=True)
                            os.startfile(target_dir)
                    else:
                        subprocess.Popen(["xdg-open", target_dir])
                    self.send_json({"success": True, "message": "Đã mở thư mục."})
                except Exception as e:
                    self.send_json({"success": False, "error": str(e)}, status_code=500)
            else:
                self.send_json(
                    {"success": False, "error": "Chưa có đường dẫn thư mục."}, status_code=404
                )
        else:
            self.send_json({"error": f"Action {action} không hỗ trợ"}, status_code=404)

    def handle_legacy_download(self, payload: dict):
        """Backward-compatible handler mapping legacy downloads directly to the Queue."""
        url = payload.get("url", "").strip()
        ep_range = payload.get("episodes", "1")
        ep_list = [ep_range]
        if "-" in ep_range:
            parts = ep_range.split("-")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                ep_list = [str(i) for i in range(int(parts[0]), int(parts[1]) + 1)]

        payload_to_create = {
            "url": url,
            "animeTitle": payload.get("animeTitle", "Anime Series"),
            "episodes": ep_list,
            "site": payload.get("site", "allwish"),
            "quality": payload.get("quality", "1080p"),
            "downloadMode": payload.get("downloadMode", "full"),
            "targetSubLangs": [payload.get("lang", "es-LA")],
            "outputDir": payload.get("outputDir", "./downloads"),
        }
        self.handle_create_task(payload_to_create)


def run_server(port: int = PORT):
    """Start local threaded HTTP server."""
    server_address = ("127.0.0.1", port)
    httpd = ThreadingHTTPServer(server_address, TeamTrauAPIHandler)
    manager_logger.log(
        "info",
        "general",
        f"TeamTrau Download Manager Backend đang chạy tại http://127.0.0.1:{port}/",
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        queue_manager.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    run_server()
