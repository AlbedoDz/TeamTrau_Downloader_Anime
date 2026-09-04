import concurrent.futures
import threading
import time
from pathlib import Path

from core.logger import manager_logger
from data.db import DatabaseManager
from data.models import DownloadMode, DownloadTaskRecord, QueueConfig, TaskStatus
from downloader.core import BatchDownloader


class QueueManager:
    """Central Download Queue Controller managing task lifecycles, concurrency, and persistence."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._db = None
        self.config = QueueConfig(max_concurrent_downloads=3)
        self._active_tasks: dict[str, threading.Event] = {}  # task_id -> stop_event
        self._pool_lock = threading.RLock()
        self._wake_event = threading.Event()
        self._is_running = True
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.max_concurrent_downloads,
            thread_name_prefix="DLManagerWorker",
        )
        self._dispatcher_thread = None
        self._initialized = True

    @property
    def db(self) -> DatabaseManager:
        """Lazy load DatabaseManager on first access to prevent blocking UI thread at app startup."""
        if self._db is None:
            with self._pool_lock:
                if self._db is None:
                    self._db = DatabaseManager()
                    # Start background dispatcher loop once DB is ready
                    self._dispatcher_thread = threading.Thread(
                        target=self._queue_dispatch_loop,
                        daemon=True,
                        name="QueueDispatcher",
                    )
                    self._dispatcher_thread.start()
                    manager_logger.log("info", "general", "Queue Manager Controller initialized.")
        return self._db

    def add_task(
        self,
        url: str,
        anime_title: str,
        episode_num: str,
        site: str,
        quality: str,
        download_mode: DownloadMode,
        target_sub_langs: list[str] | None = None,
        save_path: str = "",
        priority: int = 0,
    ) -> DownloadTaskRecord:
        """Create and enqueue a new download task in SQLite database."""
        task_id = f"task_{int(time.time() * 1000)}_{episode_num}"
        record = DownloadTaskRecord(
            id=task_id,
            url=url,
            anime_title=anime_title,
            episode_num=episode_num,
            site=site,
            quality=quality,
            download_mode=download_mode,
            target_sub_langs=target_sub_langs or ["es-LA", "en"],
            save_path=save_path or f"./downloads/{anime_title}/{anime_title} - E{episode_num}.mp4",
            status=TaskStatus.QUEUED,
            priority=priority,
            created_at=time.time(),
        )
        self.db.upsert_task(record)
        self._wake_event.set()
        manager_logger.log(
            "info",
            "general",
            f"Đã thêm vào hàng đợi: {anime_title} Tập {episode_num}",
            task_id=task_id,
        )
        return record

    def add_tasks_batch(self, task_specs: list[dict]) -> list[DownloadTaskRecord]:
        """Create and atomically enqueue multiple download tasks in SQLite database."""
        if not task_specs:
            return []

        base_time = time.time()
        created_records: list[DownloadTaskRecord] = []
        for i, spec in enumerate(task_specs):
            ep_num = str(spec.get("episode_num", "1"))
            task_id = f"task_{int(base_time * 1000) + i}_{ep_num}"
            title = spec.get("anime_title", "Anime Series")
            record = DownloadTaskRecord(
                id=task_id,
                url=spec.get("url", ""),
                anime_title=title,
                episode_num=ep_num,
                site=spec.get("site", "allwish"),
                quality=spec.get("quality", "720p"),
                download_mode=spec.get("download_mode", DownloadMode.FULL),
                target_sub_langs=spec.get("target_sub_langs") or ["es-LA", "en"],
                save_path=spec.get("save_path") or f"./downloads/{title}/{title} - E{ep_num}.mp4",
                status=TaskStatus.QUEUED,
                priority=spec.get("priority", 0),
                created_at=base_time + (i * 0.001),
            )
            created_records.append(record)

        self.db.upsert_tasks_batch(created_records)
        self._wake_event.set()
        manager_logger.log(
            "info",
            "general",
            f"Đã thêm hàng loạt {len(created_records)} tập vào hàng đợi tải.",
        )
        return created_records

    def pause_task(self, task_id: str) -> bool:
        """Pause an active downloading or queued task."""
        with self._pool_lock:
            stop_event = self._active_tasks.get(task_id)
            if stop_event:
                stop_event.set()
                self._active_tasks.pop(task_id, None)

            self.db.update_task_status(task_id, TaskStatus.PAUSED)
            self._wake_event.set()
            manager_logger.log("warn", "general", "Tác vụ đã được tạm dừng.", task_id=task_id)
            return True

    def resume_task(self, task_id: str) -> bool:
        """Resume a paused or failed task by returning it to QUEUED status."""
        with self._pool_lock:
            self.db.update_task_status(task_id, TaskStatus.QUEUED, error_message=None)
            self._wake_event.set()
            manager_logger.log(
                "info", "general", "Tác vụ đã chuyển về hàng đợi để tiếp tục tải.", task_id=task_id
            )
            return True

    def restart_task(self, task_id: str) -> bool:
        """Reset progress and redownload from scratch."""
        with self._pool_lock:
            self.pause_task(task_id)
            task = self.db.get_task(task_id)
            if task:
                task.downloaded_bytes = 0
                task.downloaded_segments = 0
                task.total_segments = 0
                task.status = TaskStatus.QUEUED
                task.error_message = None
                self.db.upsert_task(task)
                self._wake_event.set()
                manager_logger.log(
                    "info", "general", "Đã đặt lại tiến trình để tải lại từ đầu.", task_id=task_id
                )
                return True
        return False

    def delete_task(self, task_id: str, delete_file: bool = False) -> bool:
        """Remove a task from queue and database, optionally deleting downloaded file."""
        with self._pool_lock:
            self.pause_task(task_id)
            task = self.db.get_task(task_id)
            if delete_file and task and task.save_path:
                try:
                    f_path = Path(task.save_path)
                    if f_path.exists():
                        f_path.unlink()
                except Exception as e:
                    manager_logger.log("error", "general", f"Không thể xóa file: {e}")

            self.db.delete_task(task_id)
            self._wake_event.set()
            manager_logger.log("info", "general", f"Đã xóa tác vụ {task_id}.")
            return True

    def pause_all(self) -> None:
        """Stop all running tasks and update DB status to PAUSED."""
        with self._pool_lock:
            for task_id, stop_event in list(self._active_tasks.items()):
                stop_event.set()
                self.db.update_task_status(task_id, TaskStatus.PAUSED)
            self._active_tasks.clear()
            self._wake_event.set()
            manager_logger.log("warn", "general", "Đã tạm dừng tất cả tác vụ đang chạy.")

    def resume_all(self) -> None:
        """Enqueue all paused or failed tasks back into QUEUED status."""
        with self._pool_lock:
            tasks = self.db.get_all_tasks(status_filter="all")
            for t in tasks:
                if t.status in (TaskStatus.PAUSED, TaskStatus.FAILED):
                    self.db.update_task_status(t.id, TaskStatus.QUEUED)
            self._wake_event.set()
            manager_logger.log(
                "info", "general", "Đã tiếp tục tất cả các tác vụ tạm dừng/thất bại."
            )

    def clear_completed(self) -> None:
        """Delete all completed task records from DB."""
        with self._pool_lock:
            self.db.clear_completed_tasks()
            manager_logger.log("info", "general", "Đã dọn dẹp các tác vụ hoàn thành.")

    def set_concurrency_limit(self, limit: int) -> None:
        """Dynamically adjust max parallel download worker count."""
        with self._pool_lock:
            self.config.max_concurrent_downloads = max(1, min(limit, 8))
            self._executor._max_workers = self.config.max_concurrent_downloads
            self._wake_event.set()
            manager_logger.log(
                "info",
                "general",
                f"Đã cập nhật giới hạn tải đồng thời: {self.config.max_concurrent_downloads}",
            )

    def _queue_dispatch_loop(self) -> None:
        """Continuous background thread picking queued items according to priority and concurrency."""
        while self._is_running:
            try:
                self._wake_event.wait(timeout=3.0)
                self._wake_event.clear()

                if not self._is_running:
                    break

                with self._pool_lock:
                    active_count = len(self._active_tasks)
                    slots_available = self.config.max_concurrent_downloads - active_count

                    if slots_available <= 0:
                        continue

                    # Query queued tasks
                    queued_tasks = self.db.get_all_tasks(status_filter=TaskStatus.QUEUED.value)
                    if not queued_tasks:
                        continue

                    for task in queued_tasks[:slots_available]:
                        stop_event = threading.Event()
                        self._active_tasks[task.id] = stop_event
                        self.db.update_task_status(task.id, TaskStatus.DOWNLOADING)
                        self._executor.submit(self._execute_download_task, task, stop_event)

            except Exception as e:
                manager_logger.log("error", "general", f"Lỗi vòng lặp điều phối hàng đợi: {e}")

    def _execute_download_task(self, task: DownloadTaskRecord, stop_event: threading.Event) -> None:
        """Worker executing an individual download task."""
        task_id = task.id
        manager_logger.log(
            "info",
            "general",
            f"Bắt đầu tải: {task.anime_title} Tập {task.episode_num}",
            task_id=task_id,
        )

        try:
            sub_only = task.download_mode == DownloadMode.SUB_ONLY
            video_only = task.download_mode == DownloadMode.VIDEO_ONLY

            # Determine base output directory (avoiding double anime title nesting)
            if task.save_path:
                p = Path(task.save_path).resolve()
                # If path has Season XX, parent is Season XX, parent.parent is Anime Title, parent.parent.parent is base
                if p.parent.name.lower().startswith("season "):
                    base_output_dir = str(p.parent.parent.parent)
                elif p.parent.name == task.anime_title:
                    base_output_dir = str(p.parent.parent)
                else:
                    base_output_dir = str(p.parent)
            else:
                base_output_dir = "./downloads"

            last_db_progress_time = 0.0

            def on_task_progress(
                downloaded_segs: int,
                total_segs: int,
                downloaded_bytes: int,
                speed: float,
                eta: int,
            ) -> None:
                nonlocal last_db_progress_time
                if stop_event.is_set():
                    return

                now = time.time()
                is_finished = downloaded_segs >= total_segs and total_segs > 0
                # Rate limit DB write to at most once per 0.5s or on completion (saves 90% IOPS)
                if not is_finished and (now - last_db_progress_time < 0.5):
                    return
                last_db_progress_time = now

                approx_file_size = (
                    int(downloaded_bytes / (downloaded_segs / total_segs))
                    if downloaded_segs > 0 and total_segs > 0
                    else downloaded_bytes
                )
                self.db.update_task_progress(
                    task_id=task_id,
                    downloaded_bytes=downloaded_bytes,
                    file_size_bytes=approx_file_size,
                    downloaded_segments=downloaded_segs,
                    total_segments=total_segs,
                    speed_bytes_per_sec=speed,
                    eta_seconds=eta,
                )

            def on_task_log(level: str, category: str, message: str) -> None:
                manager_logger.log(level=level, category=category, message=message, task_id=task_id)

            downloader = BatchDownloader(
                output_dir=base_output_dir,
                delay_range=(1.0, 2.0),
                progress_callback=on_task_progress,
                log_callback=on_task_log,
            )

            # Route download execution (multi-sub or standalone sub support)
            target_langs = task.target_sub_langs if task.target_sub_langs else ["es-LA", "en"]
            last_download_result: dict[str, list[str]] = {"videos": [], "subtitles": []}
            for i, lang_code in enumerate(target_langs):
                if stop_event.is_set():
                    break
                is_first = i == 0
                current_video_only = video_only
                current_sub_only = sub_only or (not is_first)

                res = downloader.download_anime(
                    anime_url=task.url,
                    episode_range=task.episode_num,
                    lang=lang_code,
                    sub_only=current_sub_only,
                    video_only=current_video_only,
                    naming_format="simple",
                )
                if isinstance(res, dict):
                    last_download_result["videos"].extend(res.get("videos", []))
                    last_download_result["subtitles"].extend(res.get("subtitles", []))

            if stop_event.is_set():
                self.db.update_task_status(task_id, TaskStatus.PAUSED)
                manager_logger.log(
                    "warn", "general", "Tác vụ đã dừng theo yêu cầu người dùng.", task_id=task_id
                )
            else:
                # Rigorous file verification on disk (Poka-Yoke)
                target_file_exists = False
                final_size = 0
                verified_save_path = None

                if sub_only:
                    # 1. Check direct paths returned by BatchDownloader
                    for sub_file in reversed(last_download_result.get("subtitles", [])):
                        sp = Path(sub_file)
                        if sp.exists() and sp.stat().st_size > 100:
                            target_file_exists = True
                            final_size = sp.stat().st_size
                            verified_save_path = str(sp.resolve())
                            break

                    # 2. Fallback recursive search in base_output_dir
                    if not target_file_exists and Path(base_output_dir).exists():
                        ep_clean = task.episode_num.zfill(2)
                        for sub_ext in ("*.srt", "*.vtt", "*.ass"):
                            for f in Path(base_output_dir).rglob(f"*{ep_clean}*{sub_ext}"):
                                if f.stat().st_size > 100:
                                    target_file_exists = True
                                    final_size = f.stat().st_size
                                    verified_save_path = str(f.resolve())
                                    break
                            if target_file_exists:
                                break
                else:
                    # 1. Check direct paths returned by BatchDownloader
                    for vid_file in reversed(last_download_result.get("videos", [])):
                        vp = Path(vid_file)
                        if vp.exists() and vp.stat().st_size > 1024 * 1024:
                            target_file_exists = True
                            final_size = vp.stat().st_size
                            verified_save_path = str(vp.resolve())
                            break

                    # 2. Check task.save_path if it directly exists
                    if not target_file_exists and task.save_path and Path(task.save_path).exists():
                        sz = Path(task.save_path).stat().st_size
                        if sz > 1024 * 1024:
                            target_file_exists = True
                            final_size = sz
                            verified_save_path = str(Path(task.save_path).resolve())

                    # 3. Fallback recursive search in base_output_dir
                    if not target_file_exists and Path(base_output_dir).exists():
                        ep_clean = task.episode_num.zfill(2)
                        for ext in ("*.mp4", "*.mkv"):
                            for f in Path(base_output_dir).rglob(f"*{ep_clean}*{ext}"):
                                sz = f.stat().st_size
                                if sz > 1024 * 1024:
                                    target_file_exists = True
                                    final_size = sz
                                    verified_save_path = str(f.resolve())
                                    break
                            if target_file_exists:
                                break

                if not target_file_exists or final_size == 0 or not verified_save_path:
                    err_msg = "Không tìm thấy file tải về hợp lệ hoặc file rỗng (0 bytes)."
                    self.db.update_task_status(task_id, TaskStatus.FAILED, error_message=err_msg)
                    manager_logger.log(
                        "error",
                        "general",
                        f"Tải thất bại tập {task.episode_num}: {err_msg}",
                        task_id=task_id,
                    )
                else:
                    task.save_path = verified_save_path
                    self.db.update_task_progress(
                        task_id=task_id,
                        downloaded_bytes=final_size,
                        file_size_bytes=final_size,
                        downloaded_segments=task.total_segments,
                        total_segments=task.total_segments,
                        speed_bytes_per_sec=0.0,
                        eta_seconds=0,
                    )
                    self.db.update_task_status(
                        task_id,
                        TaskStatus.COMPLETED,
                        completed_at=time.time(),
                        save_path=verified_save_path,
                    )
                    manager_logger.log(
                        "success",
                        "m3u8_stream",
                        f"Tải hoàn tất: {task.anime_title} Tập {task.episode_num}",
                        task_id=task_id,
                    )

        except Exception as e:
            if stop_event.is_set():
                self.db.update_task_status(task_id, TaskStatus.PAUSED)
            else:
                err_msg = str(e)
                self.db.update_task_status(task_id, TaskStatus.FAILED, error_message=err_msg)
                manager_logger.log(
                    "error",
                    "general",
                    f"Lỗi khi tải tập {task.episode_num}: {err_msg}",
                    task_id=task_id,
                )
        finally:
            with self._pool_lock:
                self._active_tasks.pop(task_id, None)

    def shutdown(self) -> None:
        """RAII cleanup of background executor and dispatcher."""
        self._is_running = False
        self.pause_all()
        self._executor.shutdown(wait=False)
        manager_logger.log("info", "general", "Queue Manager đã đóng an toàn.")


# Global singleton queue manager
queue_manager = QueueManager()
