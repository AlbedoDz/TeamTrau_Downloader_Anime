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
        self.db = DatabaseManager()
        self.config = QueueConfig(max_concurrent_downloads=3)
        self._active_tasks: dict[str, threading.Event] = {}  # task_id -> stop_event
        self._pool_lock = threading.RLock()
        self._is_running = True
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.max_concurrent_downloads,
            thread_name_prefix="DLManagerWorker",
        )

        # Start background dispatcher loop
        self._dispatcher_thread = threading.Thread(
            target=self._queue_dispatch_loop,
            daemon=True,
            name="QueueDispatcher",
        )
        self._dispatcher_thread.start()
        self._initialized = True
        manager_logger.log("info", "general", "Queue Manager Controller initialized.")

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
        manager_logger.log(
            "info",
            "general",
            f"Đã thêm vào hàng đợi: {anime_title} Tập {episode_num} [{download_mode.value.upper()}]",
            task_id=task_id,
        )
        return record

    def pause_task(self, task_id: str) -> bool:
        """Pause an active or queued task."""
        with self._pool_lock:
            stop_event = self._active_tasks.get(task_id)
            if stop_event:
                stop_event.set()
                self._active_tasks.pop(task_id, None)

            self.db.update_task_status(task_id, TaskStatus.PAUSED)
            manager_logger.log("warn", "general", "Tác vụ đã được tạm dừng.", task_id=task_id)
            return True

    def resume_task(self, task_id: str) -> bool:
        """Resume a paused or failed task by returning it to QUEUED status."""
        with self._pool_lock:
            self.db.update_task_status(task_id, TaskStatus.QUEUED, error_message=None)
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
                manager_logger.log(
                    "info", "general", "Đã đặt lại tiến trình để tải lại từ đầu.", task_id=task_id
                )
                return True
        return False

    def delete_task(self, task_id: str, delete_file: bool = False) -> bool:
        """Delete task from queue and database, optionally deleting the downloaded file."""
        with self._pool_lock:
            self.pause_task(task_id)
            task = self.db.get_task(task_id)
            if task and delete_file and task.save_path:
                p = Path(task.save_path)
                if p.exists() and p.is_file():
                    try:
                        p.unlink()
                        manager_logger.log(
                            "info", "general", f"Đã xóa file: {task.save_path}", task_id=task_id
                        )
                    except Exception as e:
                        manager_logger.log(
                            "error", "general", f"Không thể xóa file: {e}", task_id=task_id
                        )

            self.db.delete_task(task_id)
            manager_logger.log("info", "general", f"Đã xóa tác vụ {task_id} khỏi cơ sở dữ liệu.")
            return True

    def pause_all(self) -> None:
        """Pause all currently active and queued tasks."""
        with self._pool_lock:
            tasks = self.db.get_all_tasks(status_filter="all")
            for t in tasks:
                if t.status in (TaskStatus.DOWNLOADING, TaskStatus.QUEUED):
                    self.pause_task(t.id)

    def resume_all(self) -> None:
        """Resume all paused or failed tasks."""
        with self._pool_lock:
            tasks = self.db.get_all_tasks(status_filter="all")
            for t in tasks:
                if t.status in (TaskStatus.PAUSED, TaskStatus.FAILED):
                    self.resume_task(t.id)

    def clear_completed(self) -> None:
        """Purge completed tasks."""
        self.db.clear_completed_tasks()
        manager_logger.log("info", "general", "Đã dọn dẹp tất cả tác vụ hoàn thành.")

    def set_concurrency_limit(self, limit: int) -> None:
        """Dynamically adjust worker concurrency limit."""
        with self._pool_lock:
            self.config.max_concurrent_downloads = max(1, min(limit, 16))
            manager_logger.log(
                "info",
                "general",
                f"Đã cấu hình giới hạn luồng tải đồng thời: {self.config.max_concurrent_downloads}",
            )

    def _queue_dispatch_loop(self) -> None:
        """Continuous background thread picking queued items according to priority and concurrency."""
        while self._is_running:
            try:
                time.sleep(1.0)
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
            output_dir = str(Path(task.save_path).parent) if task.save_path else "./downloads"

            def on_task_progress(
                downloaded_segs: int,
                total_segs: int,
                downloaded_bytes: int,
                speed: float,
                eta: int,
            ) -> None:
                if stop_event.is_set():
                    return
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
                output_dir=output_dir,
                delay_range=(1.0, 2.0),
                progress_callback=on_task_progress,
                log_callback=on_task_log,
            )

            # Route download execution
            downloader.download_anime(
                anime_url=task.url,
                episode_range=task.episode_num,
                lang=task.target_sub_langs[0] if task.target_sub_langs else "es-LA",
                sub_only=sub_only,
                video_only=video_only,
                naming_format="simple",
            )

            if stop_event.is_set():
                self.db.update_task_status(task_id, TaskStatus.PAUSED)
                manager_logger.log(
                    "warn", "general", "Tác vụ đã dừng theo yêu cầu người dùng.", task_id=task_id
                )
            else:
                # Update final file size if file exists on disk
                final_size = 0
                if task.save_path and Path(task.save_path).exists():
                    final_size = Path(task.save_path).stat().st_size
                elif Path(output_dir).exists():
                    for f in Path(output_dir).glob(f"*{task.episode_num}*.mp4"):
                        final_size = f.stat().st_size
                        task.save_path = str(f)
                        break

                if final_size > 0:
                    self.db.update_task_progress(
                        task_id=task_id,
                        downloaded_bytes=final_size,
                        file_size_bytes=final_size,
                        downloaded_segments=task.total_segments,
                        total_segments=task.total_segments,
                        speed_bytes_per_sec=0.0,
                        eta_seconds=0,
                    )

                self.db.update_task_status(task_id, TaskStatus.COMPLETED, completed_at=time.time())
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
