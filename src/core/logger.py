import threading
import time
import uuid
from collections import deque

from data.db import DatabaseManager
from data.models import TaskLogEntry


class DownloadManagerLogger:
    """Central logging engine managing both system-wide logs and per-task log routing."""

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
        self._system_logs: deque[dict] = deque(maxlen=1000)
        self._log_lock = threading.RLock()
        self._initialized = True

    def log(
        self,
        level: str,
        category: str,
        message: str,
        task_id: str | None = None,
    ) -> dict:
        """Record a log entry. Routes to system stream and task-specific storage."""
        now = time.time()
        entry_id = str(uuid.uuid4())[:8]

        log_data = {
            "id": entry_id,
            "task_id": task_id,
            "timestamp": now,
            "level": level.upper(),
            "category": category,
            "message": message,
        }

        with self._log_lock:
            self._system_logs.append(log_data)

            if task_id:
                task_entry = TaskLogEntry(
                    id=entry_id,
                    task_id=task_id,
                    timestamp=now,
                    level=level.upper(),
                    category=category,
                    message=message,
                )
                try:
                    self.db.add_task_log(task_entry)
                except Exception:
                    pass

        return log_data

    def get_system_logs(
        self,
        level_filter: str | None = None,
        category_filter: str | None = None,
        limit: int = 200,
    ) -> list[dict]:
        """Fetch system session logs with optional filters."""
        with self._log_lock:
            logs = list(self._system_logs)

        if level_filter and level_filter != "ALL":
            logs = [entry for entry in logs if entry["level"] == level_filter.upper()]

        if category_filter and category_filter != "all":
            logs = [entry for entry in logs if entry["category"] == category_filter]

        return logs[-limit:]

    def get_task_logs(self, task_id: str, limit: int = 200) -> list[dict]:
        """Fetch per-task log entries from database."""
        entries = self.db.get_task_logs(task_id, limit=limit)
        return [e.to_dict() for e in entries]

    def clear_system_logs(self) -> None:
        """Flush the in-memory system log buffer."""
        with self._log_lock:
            self._system_logs.clear()


# Global logger instance
manager_logger = DownloadManagerLogger()
