export type StreamQuality = '1080p' | '720p' | '480p' | 'source';

export type SubtitleFormat = 'vtt' | 'ass' | 'srt';

export type SubtitleLanguageCode = 'es-LA' | 'es-ES' | 'en' | 'vi' | string;

export type ExtractorSite = 'allwish' | 'anikoto' | 'animesuge' | 'animecube' | 'unknown';

export type DownloadMode = 'full' | 'sub_only' | 'video_only';

export type NamingFormat = 'simple' | 'anikoto' | 'tvdb';

export type TaskStatus = 'queued' | 'downloading' | 'paused' | 'completed' | 'failed' | 'cancelled';

export type DownloadCategory = 'all' | 'anime' | 'video' | 'subtitle';

export interface TaskLogEntry {
  id: string;
  task_id?: string | null;
  timestamp: number;
  level: string; // 'DEBUG' | 'INFO' | 'WARN' | 'ERROR' | 'SUCCESS'
  category: string; // 'm3u8_stream' | 'vrf_decrypt' | 'waf_bypass' | 'subtitle' | 'general'
  message: string;
}

export interface DownloadTaskRecord {
  id: string;
  url: string;
  anime_title: string;
  episode_num: string;
  site: string;
  quality: string;
  download_mode: DownloadMode;
  target_sub_langs: string[];
  save_path: string;
  file_size_bytes: number;
  downloaded_bytes: number;
  total_segments: number;
  downloaded_segments: number;
  status: TaskStatus;
  speed_bytes_per_sec: number;
  eta_seconds: number;
  priority: number;
  error_message?: string | null;
  created_at: number;
  completed_at?: number | null;
  progress_percent: number;
  category: DownloadCategory;
}

export interface DownloadCounts {
  all: number;
  downloading: number;
  queued: number;
  completed: number;
  paused: number;
  failed: number;
}

export interface QueueConfig {
  max_concurrent_downloads: number;
  speed_limit_kb_per_sec: number;
  auto_retry_failed: boolean;
  max_retries: number;
  delay_between_downloads: number;
}

export interface SubtitleTrack {
  id: string;
  langCode: SubtitleLanguageCode;
  label: string;
  format: SubtitleFormat;
  url: string;
  isSelected: boolean;
}

export interface ServerOption {
  id: string;
  name: string;
  serverId: string;
  isPreferred: boolean;
}

export interface EpisodeMetadata {
  num: string;
  title: string;
  slug: string;
  url: string;
  selected: boolean;
}

export interface ParsedAnimeDetails {
  rawUrl: string;
  site: ExtractorSite;
  title: string;
  totalEpisodes: number;
  episodes: EpisodeMetadata[];
  availableServers: ServerOption[];
  availableSubtitles: SubtitleTrack[];
}

export interface ServerFilterConfig {
  serverPriority?: string[];
  excludeServers?: string[];
  onlyServer?: string;
}

export interface BatchOptions {
  episodeRange: string;
  quality: StreamQuality;
  downloadMode: DownloadMode;
  namingFormat: NamingFormat;
  tvdbId?: string;
  serverFilter?: ServerFilterConfig;
  selectedSubtitles: SubtitleLanguageCode[];
  delayRange?: [number, number];
  useBrowserSniffer?: boolean;
}

export interface SettingsConfig {
  outputDirectory: string;
  maxConcurrentWorkers: number;
  defaultQuality: StreamQuality;
  preferredSubtitles: SubtitleLanguageCode[];
  namingFormat: NamingFormat;
  proxyUrl?: string;
  antiBanDelayRange: [number, number];
  enableHeadlessSniffer: boolean;
  theme: 'dark' | 'glass';
}
