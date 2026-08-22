import json
import os
import subprocess
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

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
STATIC_DIR = Path(__file__).resolve().parent


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

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)

        # GET /api/tasks (Download Manager Master Table View)
        if path == "/api/tasks":
            db = DatabaseManager()
            status_filter = query_params.get("status", ["all"])[0]
            category_filter = query_params.get("category", ["all"])[0]
            search_query = query_params.get("q", [None])[0]

            tasks = db.get_all_tasks(
                status_filter=status_filter,
                category_filter=category_filter,
                search_query=search_query,
            )

            # Compute category counts
            all_tasks = db.get_all_tasks(status_filter="all")
            counts = {
                "all": len(all_tasks),
                "downloading": sum(1 for t in all_tasks if t.status == TaskStatus.DOWNLOADING),
                "queued": sum(1 for t in all_tasks if t.status == TaskStatus.QUEUED),
                "completed": sum(1 for t in all_tasks if t.status == TaskStatus.COMPLETED),
                "paused": sum(1 for t in all_tasks if t.status == TaskStatus.PAUSED),
                "failed": sum(1 for t in all_tasks if t.status == TaskStatus.FAILED),
            }

            self.send_json(
                {
                    "success": True,
                    "tasks": [t.to_dict() for t in tasks],
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
            self.send_json({"success": True, "message": "Tất cả tác vụ đã tạm dừng."})
        elif path == "/api/queue/resume-all":
            queue_manager.resume_all()
            self.send_json({"success": True, "message": "Tất cả tác vụ đã tiếp tục."})
        elif path == "/api/queue/clear-completed":
            queue_manager.clear_completed()
            self.send_json({"success": True, "message": "Đã dọn dẹp các tác vụ hoàn thành."})
        elif path == "/api/queue/config":
            limit = int(payload.get("maxConcurrent", 3))
            queue_manager.set_concurrency_limit(limit)
            self.send_json({"success": True, "config": queue_manager.config.to_dict()})
        elif path == "/api/cancel":
            queue_manager.pause_all()
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
        quality = payload.get("quality", "1080p")
        mode_str = payload.get("downloadMode", "full")
        target_subs = payload.get("targetSubLangs", ["es-LA", "en"])
        output_dir = payload.get("outputDir", "./downloads")

        mode = DownloadMode.FULL
        if mode_str == "sub_only":
            mode = DownloadMode.SUB_ONLY
        elif mode_str == "video_only":
            mode = DownloadMode.VIDEO_ONLY

        created_tasks = []
        for ep_num in episodes:
            save_path = str(Path(output_dir) / title / f"{title} - S01E{str(ep_num).zfill(2)}.mp4")
            task = queue_manager.add_task(
                url=url,
                anime_title=title,
                episode_num=str(ep_num),
                site=site,
                quality=quality,
                download_mode=mode,
                target_sub_langs=target_subs,
                save_path=save_path,
            )
            created_tasks.append(task.to_dict())

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
            self.send_json({"success": True, "message": f"Tác vụ {task_id} đã tạm dừng."})
        elif action == "resume":
            queue_manager.resume_task(task_id)
            self.send_json({"success": True, "message": f"Tác vụ {task_id} đã tiếp tục."})
        elif action == "restart":
            queue_manager.restart_task(task_id)
            self.send_json({"success": True, "message": f"Tác vụ {task_id} đã đặt lại để tải lại."})
        elif action == "delete":
            delete_file = payload.get("deleteFile", False)
            queue_manager.delete_task(task_id, delete_file=delete_file)
            self.send_json({"success": True, "message": f"Đã xóa tác vụ {task_id}."})
        elif action == "open-file":
            task = DatabaseManager().get_task(task_id)
            if task and task.save_path and Path(task.save_path).exists():
                try:
                    if sys.platform == "win32":
                        os.startfile(task.save_path)
                    else:
                        subprocess.Popen(["xdg-open", task.save_path])
                    self.send_json({"success": True, "message": "Đã mở file."})
                except Exception as e:
                    self.send_json({"success": False, "error": str(e)}, status_code=500)
            else:
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
