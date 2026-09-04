import json
import sqlite3
import sys
import threading
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import ClassVar

from data.models import DownloadMode, DownloadTaskRecord, TaskLogEntry, TaskStatus

if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DEFAULT_DB_PATH = PROJECT_ROOT / "app_data" / "sessions.db"


class DatabaseManager:
    """Thread-safe SQLite Database Manager for Download Manager sessions."""

    _instances: ClassVar[dict[str, "DatabaseManager"]] = {}
    _lock = threading.Lock()

    def __new__(cls, db_path: str | Path = DEFAULT_DB_PATH):
        resolved_path = str(Path(db_path).resolve())
        with cls._lock:
            if resolved_path not in cls._instances:
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instances[resolved_path] = instance
            return cls._instances[resolved_path]

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        if getattr(self, "_initialized", False):
            return
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_lock = threading.RLock()
        self._init_db()
        self._recover_interrupted_tasks()
        self._initialized = True

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """RAII Context Manager providing a thread-safe SQLite connection."""
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=30.0,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize database schema with WAL mode enabled."""
        with self._db_lock, self.get_connection() as conn:
            cursor = conn.cursor()
            # Enable WAL mode for high concurrency
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA foreign_keys=ON;")

            # Tasks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    anime_title TEXT NOT NULL,
                    episode_num TEXT NOT NULL,
                    site TEXT NOT NULL,
                    quality TEXT NOT NULL,
                    download_mode TEXT NOT NULL,
                    target_sub_langs TEXT NOT NULL,
                    save_path TEXT DEFAULT '',
                    file_size_bytes INTEGER DEFAULT 0,
                    downloaded_bytes INTEGER DEFAULT 0,
                    total_segments INTEGER DEFAULT 0,
                    downloaded_segments INTEGER DEFAULT 0,
                    status TEXT NOT NULL,
                    speed_bytes_per_sec REAL DEFAULT 0.0,
                    eta_seconds INTEGER DEFAULT 0,
                    priority INTEGER DEFAULT 0,
                    error_message TEXT,
                    created_at REAL NOT NULL,
                    completed_at REAL
                );
            """)

            # Task logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS task_logs (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    level TEXT NOT NULL,
                    category TEXT NOT NULL,
                    message TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE
                );
            """)

            # Indices for rapid querying & high-scale batch operations
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status);")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks (created_at DESC);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_queue_lookup ON tasks (status, priority DESC, created_at DESC);"
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_title ON tasks (anime_title);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_mode ON tasks (download_mode);")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_task_logs_task_id ON task_logs (task_id);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_task_logs_lookup ON task_logs (task_id, timestamp ASC);"
            )

            conn.commit()

    def _recover_interrupted_tasks(self) -> None:
        """Auto-recovery: On startup, change any interrupted DOWNLOADING tasks to PAUSED."""
        with self._db_lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE tasks SET status = ?, speed_bytes_per_sec = 0.0, eta_seconds = 0 WHERE status = ?",
                (TaskStatus.PAUSED.value, TaskStatus.DOWNLOADING.value),
            )
            conn.commit()

    def upsert_task(self, task: DownloadTaskRecord) -> None:
        """Insert or update a task record."""
        with self._db_lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO tasks (
                    id, url, anime_title, episode_num, site, quality,
                    download_mode, target_sub_langs, save_path, file_size_bytes,
                    downloaded_bytes, total_segments, downloaded_segments,
                    status, speed_bytes_per_sec, eta_seconds, priority,
                    error_message, created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    url = excluded.url,
                    anime_title = excluded.anime_title,
                    episode_num = excluded.episode_num,
                    site = excluded.site,
                    quality = excluded.quality,
                    download_mode = excluded.download_mode,
                    target_sub_langs = excluded.target_sub_langs,
                    save_path = excluded.save_path,
                    file_size_bytes = excluded.file_size_bytes,
                    downloaded_bytes = excluded.downloaded_bytes,
                    total_segments = excluded.total_segments,
                    downloaded_segments = excluded.downloaded_segments,
                    status = excluded.status,
                    speed_bytes_per_sec = excluded.speed_bytes_per_sec,
                    eta_seconds = excluded.eta_seconds,
                    priority = excluded.priority,
                    error_message = excluded.error_message,
                    completed_at = excluded.completed_at;
            """,
                (
                    task.id,
                    task.url,
                    task.anime_title,
                    task.episode_num,
                    task.site,
                    task.quality,
                    task.download_mode.value,
                    json.dumps(task.target_sub_langs),
                    task.save_path,
                    task.file_size_bytes,
                    task.downloaded_bytes,
                    task.total_segments,
                    task.downloaded_segments,
                    task.status.value,
                    task.speed_bytes_per_sec,
                    task.eta_seconds,
                    task.priority,
                    task.error_message,
                    task.created_at,
                    task.completed_at,
                ),
            )
            conn.commit()

    def upsert_tasks_batch(self, tasks: list[DownloadTaskRecord]) -> None:
        """Efficient atomic batch insertion/update for dozens to hundreds of tasks."""
        if not tasks:
            return

        stmt = """
            INSERT INTO tasks (
                id, url, anime_title, episode_num, site, quality,
                download_mode, target_sub_langs, save_path, file_size_bytes,
                downloaded_bytes, total_segments, downloaded_segments,
                status, speed_bytes_per_sec, eta_seconds, priority,
                error_message, created_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                url = excluded.url,
                anime_title = excluded.anime_title,
                episode_num = excluded.episode_num,
                site = excluded.site,
                quality = excluded.quality,
                download_mode = excluded.download_mode,
                target_sub_langs = excluded.target_sub_langs,
                save_path = excluded.save_path,
                file_size_bytes = excluded.file_size_bytes,
                downloaded_bytes = excluded.downloaded_bytes,
                total_segments = excluded.total_segments,
                downloaded_segments = excluded.downloaded_segments,
                status = excluded.status,
                speed_bytes_per_sec = excluded.speed_bytes_per_sec,
                eta_seconds = excluded.eta_seconds,
                priority = excluded.priority,
                error_message = excluded.error_message,
                completed_at = excluded.completed_at;
        """
        records_params = [
            (
                t.id,
                t.url,
                t.anime_title,
                t.episode_num,
                t.site,
                t.quality,
                t.download_mode.value,
                json.dumps(t.target_sub_langs),
                t.save_path,
                t.file_size_bytes,
                t.downloaded_bytes,
                t.total_segments,
                t.downloaded_segments,
                t.status.value,
                t.speed_bytes_per_sec,
                t.eta_seconds,
                t.priority,
                t.error_message,
                t.created_at,
                t.completed_at,
            )
            for t in tasks
        ]
        with self._db_lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(stmt, records_params)
            conn.commit()

    def get_task(self, task_id: str) -> DownloadTaskRecord | None:
        """Fetch a single task record by ID."""
        with self._db_lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_task(row)

    def get_all_tasks(
        self,
        status_filter: str | None = None,
        category_filter: str | None = None,
        search_query: str | None = None,
    ) -> list[DownloadTaskRecord]:
        """Fetch all tasks with optional status/category/search filtering."""
        query = "SELECT * FROM tasks WHERE 1=1"
        params: list[str | int] = []

        if status_filter and status_filter != "all":
            query += " AND status = ?"
            params.append(status_filter)

        if category_filter and category_filter != "all":
            if category_filter == "subtitle":
                query += " AND download_mode = ?"
                params.append(DownloadMode.SUB_ONLY.value)
            elif category_filter == "video":
                query += " AND download_mode = ?"
                params.append(DownloadMode.VIDEO_ONLY.value)
            elif category_filter == "anime":
                query += " AND download_mode = ?"
                params.append(DownloadMode.FULL.value)

        if search_query:
            query += " AND (anime_title LIKE ? OR url LIKE ? OR episode_num LIKE ?)"
            wildcard = f"%{search_query}%"
            params.extend([wildcard, wildcard, wildcard])

        query += " ORDER BY priority DESC, created_at DESC"

        with self._db_lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_task(row) for row in rows]

    def update_task_progress(
        self,
        task_id: str,
        downloaded_bytes: int,
        file_size_bytes: int,
        downloaded_segments: int,
        total_segments: int,
        speed_bytes_per_sec: float,
        eta_seconds: int,
    ) -> None:
        """Optimized partial update for progress during active downloads."""
        with self._db_lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE tasks SET
                    downloaded_bytes = ?,
                    file_size_bytes = ?,
                    downloaded_segments = ?,
                    total_segments = ?,
                    speed_bytes_per_sec = ?,
                    eta_seconds = ?
                WHERE id = ?
            """,
                (
                    downloaded_bytes,
                    file_size_bytes,
                    downloaded_segments,
                    total_segments,
                    speed_bytes_per_sec,
                    eta_seconds,
                    task_id,
                ),
            )
            conn.commit()

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        error_message: str | None = None,
        completed_at: float | None = None,
        save_path: str | None = None,
    ) -> None:
        """Update status and optional completion timestamp/error/save_path."""
        with self._db_lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE tasks SET
                    status = ?,
                    error_message = ?,
                    completed_at = COALESCE(?, completed_at),
                    save_path = COALESCE(?, save_path),
                    speed_bytes_per_sec = CASE WHEN ? IN ('paused', 'completed', 'failed', 'cancelled') THEN 0.0 ELSE speed_bytes_per_sec END,
                    eta_seconds = CASE WHEN ? IN ('paused', 'completed', 'failed', 'cancelled') THEN 0 ELSE eta_seconds END
                WHERE id = ?
            """,
                (
                    status.value,
                    error_message,
                    completed_at,
                    save_path,
                    status.value,
                    status.value,
                    task_id,
                ),
            )
            conn.commit()

    def delete_task(self, task_id: str) -> None:
        """Delete a task and its associated logs from SQLite."""
        with self._db_lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM task_logs WHERE task_id = ?", (task_id,))
            cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()

    def clear_completed_tasks(self) -> None:
        """Clear all tasks marked as completed."""
        with self._db_lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM task_logs WHERE task_id IN (SELECT id FROM tasks WHERE status = ?)",
                (TaskStatus.COMPLETED.value,),
            )
            cursor.execute("DELETE FROM tasks WHERE status = ?", (TaskStatus.COMPLETED.value,))
            conn.commit()

    def add_task_log(self, entry: TaskLogEntry) -> None:
        """Add a log entry for a specific task."""
        with self._db_lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO task_logs (id, task_id, timestamp, level, category, message)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    entry.id,
                    entry.task_id,
                    entry.timestamp,
                    entry.level,
                    entry.category,
                    entry.message,
                ),
            )
            conn.commit()

    def get_task_logs(self, task_id: str, limit: int = 200) -> list[TaskLogEntry]:
        """Fetch per-task logs in chronological order."""
        with self._db_lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM task_logs WHERE task_id = ? ORDER BY timestamp ASC LIMIT ?",
                (task_id, limit),
            )
            rows = cursor.fetchall()
            return [
                TaskLogEntry(
                    id=row["id"],
                    task_id=row["task_id"],
                    timestamp=row["timestamp"],
                    level=row["level"],
                    category=row["category"],
                    message=row["message"],
                )
                for row in rows
            ]

    def prune_task_logs(self, max_logs_per_task: int = 150) -> int:
        """Prune older task logs to keep database size compact and queries fast."""
        with self._db_lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM task_logs
                WHERE id IN (
                    SELECT id FROM (
                        SELECT id,
                               ROW_NUMBER() OVER (PARTITION BY task_id ORDER BY timestamp DESC) as rn
                        FROM task_logs
                    ) WHERE rn > ?
                )
            """,
                (max_logs_per_task,),
            )
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count

    def checkpoint_wal(self) -> None:
        """Run passive WAL checkpoint to truncate WAL log safely without locking readers."""
        with self._db_lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA wal_checkpoint(PASSIVE);")
            conn.commit()

    def get_completed_tasks_history(
        self, limit: int = 100, offset: int = 0
    ) -> list[DownloadTaskRecord]:
        """Fetch paginated completed tasks history sorted by completion date."""
        query = """
            SELECT * FROM tasks
            WHERE status = ?
            ORDER BY completed_at DESC, created_at DESC
            LIMIT ? OFFSET ?
        """
        with self._db_lock, self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (TaskStatus.COMPLETED.value, limit, offset))
            rows = cursor.fetchall()
            return [self._row_to_task(row) for row in rows]

    def _row_to_task(self, row: sqlite3.Row) -> DownloadTaskRecord:
        """Convert a database row into a strict DownloadTaskRecord instance."""
        target_subs = []
        try:
            target_subs = json.loads(row["target_sub_langs"])
        except Exception:
            target_subs = []

        return DownloadTaskRecord(
            id=row["id"],
            url=row["url"],
            anime_title=row["anime_title"],
            episode_num=row["episode_num"],
            site=row["site"],
            quality=row["quality"],
            download_mode=DownloadMode(row["download_mode"]),
            target_sub_langs=target_subs,
            save_path=row["save_path"] or "",
            file_size_bytes=row["file_size_bytes"] or 0,
            downloaded_bytes=row["downloaded_bytes"] or 0,
            total_segments=row["total_segments"] or 0,
            downloaded_segments=row["downloaded_segments"] or 0,
            status=TaskStatus(row["status"]),
            speed_bytes_per_sec=row["speed_bytes_per_sec"] or 0.0,
            eta_seconds=row["eta_seconds"] or 0,
            priority=row["priority"] or 0,
            error_message=row["error_message"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        )
