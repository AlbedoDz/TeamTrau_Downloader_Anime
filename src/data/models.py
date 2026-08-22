import time
from dataclasses import asdict, dataclass, field
from enum import StrEnum


class TaskStatus(StrEnum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DownloadCategory(StrEnum):
    ALL = "all"
    ANIME = "anime"
    VIDEO = "video"
    SUBTITLE = "subtitle"


class DownloadMode(StrEnum):
    FULL = "full"
    SUB_ONLY = "sub_only"
    VIDEO_ONLY = "video_only"


@dataclass
class TaskLogEntry:
    id: str
    task_id: str
    timestamp: float
    level: str  # DEBUG, INFO, WARN, ERROR, SUCCESS
    category: str  # m3u8_stream, vrf_decrypt, waf_bypass, subtitle, general
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DownloadTaskRecord:
    id: str
    url: str
    anime_title: str
    episode_num: str
    site: str
    quality: str
    download_mode: DownloadMode
    target_sub_langs: list[str] = field(default_factory=list)
    save_path: str = ""
    file_size_bytes: int = 0
    downloaded_bytes: int = 0
    total_segments: int = 0
    downloaded_segments: int = 0
    status: TaskStatus = TaskStatus.QUEUED
    speed_bytes_per_sec: float = 0.0
    eta_seconds: int = 0
    priority: int = 0  # Higher = earlier download
    error_message: str | None = None
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None

    @property
    def progress_percent(self) -> float:
        if self.status == TaskStatus.COMPLETED:
            return 100.0
        if self.total_segments > 0:
            return round((self.downloaded_segments / self.total_segments) * 100, 1)
        if self.file_size_bytes > 0:
            return round((self.downloaded_bytes / self.file_size_bytes) * 100, 1)
        return 0.0

    @property
    def category(self) -> DownloadCategory:
        if self.download_mode == DownloadMode.SUB_ONLY:
            return DownloadCategory.SUBTITLE
        if self.download_mode == DownloadMode.VIDEO_ONLY:
            return DownloadCategory.VIDEO
        return DownloadCategory.ANIME

    def to_dict(self) -> dict:
        data = asdict(self)
        data["download_mode"] = self.download_mode.value
        data["status"] = self.status.value
        data["category"] = self.category.value
        data["progress_percent"] = self.progress_percent
        return data


@dataclass
class QueueConfig:
    max_concurrent_downloads: int = 3
    speed_limit_kb_per_sec: int = 0  # 0 = unlimited
    auto_retry_failed: bool = True
    max_retries: int = 3
    delay_between_downloads: float = 3.0

    def to_dict(self) -> dict:
        return asdict(self)
