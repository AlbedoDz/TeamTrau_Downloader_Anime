import {
  DownloadCategory,
  DownloadCounts,
  DownloadMode,
  DownloadTaskRecord,
  ParsedAnimeDetails,
  QueueConfig,
  SettingsConfig,
  TaskLogEntry,
  TaskStatus,
} from '../types';

export interface ManagerState {
  tasks: DownloadTaskRecord[];
  counts: DownloadCounts;
  selectedCategory: DownloadCategory | TaskStatus | 'all';
  searchQuery: string;
  selectedTaskId: string | null;
  taskLogs: TaskLogEntry[];
  isTaskDetailOpen: boolean;
  systemLogs: TaskLogEntry[];
  isConsoleOpen: boolean;
  isSettingsOpen: boolean;
  isAddModalOpen: boolean;
  isBatchModalOpen: boolean;
  parsedDetails: ParsedAnimeDetails | null;
  isParsing: boolean;
  parseError: string | null;
  isBackendConnected: boolean;
  queueConfig: QueueConfig;
  settings: SettingsConfig;
}

type Listener = () => void;

class DownloadManagerStore {
  private state: ManagerState = {
    tasks: [],
    counts: { all: 0, downloading: 0, queued: 0, completed: 0, paused: 0, failed: 0 },
    selectedCategory: 'all',
    searchQuery: '',
    selectedTaskId: null,
    taskLogs: [],
    isTaskDetailOpen: false,
    systemLogs: [],
    isConsoleOpen: false,
    isSettingsOpen: false,
    isAddModalOpen: false,
    isBatchModalOpen: false,
    parsedDetails: null,
    isParsing: false,
    parseError: null,
    isBackendConnected: false,
    queueConfig: {
      max_concurrent_downloads: 3,
      speed_limit_kb_per_sec: 0,
      auto_retry_failed: true,
      max_retries: 3,
      delay_between_downloads: 3.0,
    },
    settings: {
      outputDirectory: './downloads',
      maxConcurrentWorkers: 3,
      defaultQuality: '1080p',
      preferredSubtitles: ['es-LA', 'en'],
      namingFormat: 'simple',
      antiBanDelayRange: [3, 7],
      enableHeadlessSniffer: false,
      theme: 'glass',
    },
  };

  private listeners: Set<Listener> = new Set();
  private pollingTimer: number | null = null;

  constructor() {
    this.startPolling();
  }

  public getState(): ManagerState {
    return this.state;
  }

  public subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private notify(): void {
    this.listeners.forEach((listener) => listener());
  }

  public setState(partial: Partial<ManagerState>): void {
    this.state = { ...this.state, ...partial };
    this.notify();
  }

  public setSelectedCategory(category: DownloadCategory | TaskStatus | 'all'): void {
    this.setState({ selectedCategory: category });
    this.fetchTasks();
  }

  public setSearchQuery(query: string): void {
    this.setState({ searchQuery: query });
    this.fetchTasks();
  }

  public openTaskDetail(taskId: string): void {
    this.setState({ selectedTaskId: taskId, isTaskDetailOpen: true });
    this.fetchTaskLogs(taskId);
  }

  public closeTaskDetail(): void {
    this.setState({ isTaskDetailOpen: false, selectedTaskId: null, taskLogs: [] });
  }

  public async fetchTasks(): Promise<void> {
    try {
      const { selectedCategory, searchQuery } = this.state;
      let url = '/api/tasks?';
      if (['queued', 'downloading', 'paused', 'completed', 'failed'].includes(selectedCategory)) {
        url += `status=${selectedCategory}&`;
      } else if (['anime', 'video', 'subtitle'].includes(selectedCategory)) {
        url += `category=${selectedCategory}&`;
      }
      if (searchQuery.trim()) {
        url += `q=${encodeURIComponent(searchQuery.trim())}&`;
      }

      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        if (data.success) {
          this.setState({
            tasks: data.tasks,
            counts: data.counts,
            queueConfig: data.config || this.state.queueConfig,
            isBackendConnected: true,
          });
        }
      }
    } catch {
      this.setState({ isBackendConnected: false });
    }
  }

  public async fetchTaskLogs(taskId: string): Promise<void> {
    try {
      const res = await fetch(`/api/tasks/${taskId}/logs`);
      if (res.ok) {
        const data = await res.json();
        if (data.success) {
          this.setState({ taskLogs: data.logs });
        }
      }
    } catch {
      // Ignored in offline mode
    }
  }

  public async pauseTask(taskId: string): Promise<void> {
    await fetch(`/api/tasks/${taskId}/pause`, { method: 'POST' });
    this.fetchTasks();
  }

  public async resumeTask(taskId: string): Promise<void> {
    await fetch(`/api/tasks/${taskId}/resume`, { method: 'POST' });
    this.fetchTasks();
  }

  public async restartTask(taskId: string): Promise<void> {
    await fetch(`/api/tasks/${taskId}/restart`, { method: 'POST' });
    this.fetchTasks();
  }

  public async deleteTask(taskId: string, deleteFile = false): Promise<void> {
    await fetch(`/api/tasks/${taskId}/delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ deleteFile }),
    });
    this.fetchTasks();
  }

  public async pauseAll(): Promise<void> {
    await fetch('/api/queue/pause-all', { method: 'POST' });
    this.fetchTasks();
  }

  public async resumeAll(): Promise<void> {
    await fetch('/api/queue/resume-all', { method: 'POST' });
    this.fetchTasks();
  }

  public async clearCompleted(): Promise<void> {
    await fetch('/api/queue/clear-completed', { method: 'POST' });
    this.fetchTasks();
  }

  public async openFile(taskId: string): Promise<void> {
    await fetch(`/api/tasks/${taskId}/open-file`, { method: 'POST' });
  }

  public async openFolder(taskId: string): Promise<void> {
    await fetch(`/api/tasks/${taskId}/open-folder`, { method: 'POST' });
  }

  public async addTasks(params: {
    url: string;
    animeTitle: string;
    episodes: string[];
    site: string;
    quality: string;
    downloadMode: DownloadMode;
    targetSubLangs: string[];
  }): Promise<void> {
    await fetch('/api/tasks/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...params,
        outputDir: this.state.settings.outputDirectory,
      }),
    });
    this.fetchTasks();
  }

  private startPolling(): void {
    if (typeof window === 'undefined') return;
    this.fetchTasks();
    this.pollingTimer = window.setInterval(() => {
      this.fetchTasks();
      if (this.state.selectedTaskId && this.state.isTaskDetailOpen) {
        this.fetchTaskLogs(this.state.selectedTaskId);
      }
    }, 1500);
  }

  public destroy(): void {
    if (this.pollingTimer !== null) {
      clearInterval(this.pollingTimer);
      this.pollingTimer = null;
    }
  }
}

export const downloadStore = new DownloadManagerStore();
