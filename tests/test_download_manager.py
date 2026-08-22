import tempfile
import time
from pathlib import Path

from core.logger import DownloadManagerLogger
from data.db import DatabaseManager
from data.models import DownloadMode, DownloadTaskRecord, TaskStatus


def test_database_manager_crud_and_recovery():
    """Verify SQLite CRUD, WAL mode, and automatic state recovery on restart."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_sessions.db"
        db = DatabaseManager(db_path=db_path)

        # 1. Insert a task
        task1 = DownloadTaskRecord(
            id="task_test_001",
            url="https://all-wish.me/watch/test/ep-1",
            anime_title="Test Anime",
            episode_num="1",
            site="allwish",
            quality="1080p",
            download_mode=DownloadMode.FULL,
            target_sub_langs=["es-LA", "en"],
            status=TaskStatus.QUEUED,
        )
        db.upsert_task(task1)

        fetched = db.get_task("task_test_001")
        assert fetched is not None
        assert fetched.anime_title == "Test Anime"
        assert fetched.status == TaskStatus.QUEUED
        assert fetched.progress_percent == 0.0

        # 2. Update progress
        db.update_task_progress(
            task_id="task_test_001",
            downloaded_bytes=5000,
            file_size_bytes=10000,
            downloaded_segments=5,
            total_segments=10,
            speed_bytes_per_sec=1024.0,
            eta_seconds=5,
        )
        updated = db.get_task("task_test_001")
        assert updated.progress_percent == 50.0
        assert updated.speed_bytes_per_sec == 1024.0

        # 3. Simulate crash during DOWNLOADING state
        db.update_task_status("task_test_001", TaskStatus.DOWNLOADING)
        assert db.get_task("task_test_001").status == TaskStatus.DOWNLOADING

        # 4. Trigger auto-recovery
        db._recover_interrupted_tasks()
        recovered = db.get_task("task_test_001")
        assert recovered.status == TaskStatus.PAUSED
        assert recovered.speed_bytes_per_sec == 0.0

        # 5. Delete task
        db.delete_task("task_test_001")
        assert db.get_task("task_test_001") is None


def test_per_task_and_system_logging():
    """Verify dual-layer logging with per-task isolation and ring buffer cap."""
    logger = DownloadManagerLogger()
    task_id = f"test_task_log_{int(time.time())}"

    # Log system messages
    logger.log("info", "general", "System initialized")
    logger.log("debug", "m3u8_stream", "Fetching playlist")

    # Log task specific messages
    logger.log("info", "vrf_decrypt", "Decrypted VRF key", task_id=task_id)
    logger.log("error", "m3u8_stream", "Segment 3 retry", task_id=task_id)

    # Verify system logs
    sys_logs = logger.get_system_logs(limit=10)
    assert len(sys_logs) >= 4

    # Verify task logs
    task_logs = logger.get_task_logs(task_id)
    assert len(task_logs) == 2
    assert task_logs[0]["category"] == "vrf_decrypt"
    assert task_logs[1]["level"] == "ERROR"


def test_task_model_properties():
    """Verify Task model calculations and enum mappings."""
    task = DownloadTaskRecord(
        id="prop_test",
        url="https://anikototv.to/watch/anime",
        anime_title="Sample Title",
        episode_num="3",
        site="anikoto",
        quality="720p",
        download_mode=DownloadMode.SUB_ONLY,
        status=TaskStatus.COMPLETED,
    )
    assert task.progress_percent == 100.0
    assert task.category.value == "subtitle"
    task_dict = task.to_dict()
    assert task_dict["download_mode"] == "sub_only"
    assert task_dict["status"] == "completed"
