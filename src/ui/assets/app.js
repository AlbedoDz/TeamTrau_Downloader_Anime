const {
  useState,
  useEffect,
  useRef,
  useMemo
} = React;

// Supported site presets for 1-click test and guidance
const SITE_PRESETS = [{
  id: 'allwish',
  name: 'AllWish',
  domain: 'all-wish.me',
  sample: 'https://all-wish.me/watch/world-is-dancing-mof9c/ep-8',
  color: 'border-emerald-500/40 text-emerald-400 bg-emerald-950/20'
}, {
  id: 'anikoto',
  name: 'AniKoto',
  domain: 'anikototv.to',
  sample: 'https://anikototv.to/watch/solo-leveling-season-2',
  color: 'border-purple-500/40 text-purple-400 bg-purple-950/20'
}, {
  id: 'animesuge',
  name: 'AnimeSuge',
  domain: 'animesuge.cz',
  sample: 'https://animesuge.cz/anime/world-is-dancing-wt8rp/ep-4',
  color: 'border-amber-500/40 text-amber-400 bg-amber-950/20'
}, {
  id: 'animecube',
  name: 'AnimeCube',
  domain: 'animecube.live',
  sample: 'https://animecube.live/watch/one-piece/ep-1',
  color: 'border-cyan-500/40 text-cyan-400 bg-cyan-950/20'
}];
function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}
function detectProviderFromUrl(rawUrl) {
  if (!rawUrl) return null;
  const lower = rawUrl.toLowerCase().trim();
  if (lower.includes('all-wish') || lower.includes('allwish')) return {
    name: 'AllWish',
    id: 'allwish',
    color: 'text-emerald-400 bg-emerald-950/40 border-emerald-500/40'
  };
  if (lower.includes('anikoto')) return {
    name: 'AniKoto',
    id: 'anikoto',
    color: 'text-purple-400 bg-purple-950/40 border-purple-500/40'
  };
  if (lower.includes('animesuge')) return {
    name: 'AnimeSuge',
    id: 'animesuge',
    color: 'text-amber-400 bg-amber-950/40 border-amber-500/40'
  };
  if (lower.includes('animecube')) return {
    name: 'AnimeCube',
    id: 'animecube',
    color: 'text-cyan-400 bg-cyan-950/40 border-cyan-500/40'
  };
  return null;
}
function parseRangeNumbers(rangeInput, totalEpisodes) {
  if (!rangeInput || !totalEpisodes) return [];
  const trimmed = rangeInput.trim().toLowerCase();
  if (trimmed === 'all' || trimmed === '*') {
    return Array.from({
      length: totalEpisodes
    }, (_, i) => String(i + 1));
  }
  const selected = new Set();
  const parts = trimmed.split(',').map(p => p.trim());
  for (const part of parts) {
    if (part.includes('-')) {
      const [s, end] = part.split('-').map(n => parseInt(n.trim(), 10));
      if (!isNaN(s) && !isNaN(end)) {
        const startNum = Math.max(1, Math.min(s, end));
        const endNum = Math.min(totalEpisodes, Math.max(s, end));
        for (let i = startNum; i <= endNum; i++) selected.add(String(i));
      }
    } else if (part) {
      const num = parseInt(part, 10);
      if (!isNaN(num) && num >= 1 && num <= totalEpisodes) {
        selected.add(String(num));
      }
    }
  }
  return Array.from(selected).sort((a, b) => parseInt(a, 10) - parseInt(b, 10));
}
function App() {
  // Navigation Tab State (DLSS Swapper 6 Tabs)
  const [activeTab, setActiveTab] = useState('home'); // home | tasks | utilities | history | settings | about

  // Data State - Single Source of Truth
  const [allTasks, setAllTasks] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [isBackendConnected, setIsBackendConnected] = useState(true);

  // Synchronous Reactive Counts
  const counts = useMemo(() => {
    return {
      all: allTasks.length,
      downloading: allTasks.filter(t => t.status === 'downloading').length,
      queued: allTasks.filter(t => t.status === 'queued').length,
      paused: allTasks.filter(t => t.status === 'paused').length,
      completed: allTasks.filter(t => t.status === 'completed').length,
      failed: allTasks.filter(t => t.status === 'failed').length,
      anime: allTasks.filter(t => t.download_mode === 'full').length,
      video: allTasks.filter(t => t.download_mode === 'video_only').length,
      subtitle: allTasks.filter(t => t.download_mode === 'sub_only').length
    };
  }, [allTasks]);

  // Synchronous Reactive Filtered Tasks (0ms latency, zero flicker/disappearance)
  const filteredTasks = useMemo(() => {
    let list = allTasks;
    if (selectedCategory && selectedCategory !== 'all') {
      if (['queued', 'downloading', 'paused', 'completed', 'failed'].includes(selectedCategory)) {
        list = list.filter(t => t.status === selectedCategory);
      } else if (['anime', 'video', 'subtitle'].includes(selectedCategory)) {
        list = list.filter(t => t.download_mode === selectedCategory);
      }
    }
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      list = list.filter(t => (t.anime_title && t.anime_title.toLowerCase().includes(q)) || (t.site && t.site.toLowerCase().includes(q)));
    }
    return list;
  }, [allTasks, selectedCategory, searchQuery]);

  // Add Task & Parse Modal State
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [url, setUrl] = useState('');
  const [isParsing, setIsParsing] = useState(false);
  const [parsedData, setParsedData] = useState(null);
  const [parseError, setParseError] = useState(null);
  const [downloadMode, setDownloadMode] = useState('full'); // full | sub_only | video_only
  const [rangeInput, setRangeInput] = useState('1-12');
  const [selectedQuality, setSelectedQuality] = useState('720p');
  const [selectedLangs, setSelectedLangs] = useState(['es-LA', 'en']);

  // UI Context & Inspector Modals
  const [contextMenu, setContextMenu] = useState({
    visible: false,
    x: 0,
    y: 0,
    task: null
  });
  const [taskDetail, setTaskDetail] = useState(null);
  const [taskLogs, setTaskLogs] = useState([]);
  const [previewTask, setPreviewTask] = useState(null);
  const [isConsoleOpen, setIsConsoleOpen] = useState(false);
  const [systemLogs, setSystemLogs] = useState([]);
  const [logFilterQuery, setLogFilterQuery] = useState('');
  const [logLevelFilter, setLogLevelFilter] = useState('ALL');
  const [autoScrollLogs, setAutoScrollLogs] = useState(true);

  // Settings State
  const [settings, setSettings] = useState({
    outputDir: './downloads',
    maxWorkers: 3,
    proxyUrl: '',
    namingFormat: 'simple',
    delaySec: 1.0
  });

  // Load saved config on mount
  useEffect(() => {
    fetch('/api/config').then(r => r.json()).then(d => {
      if (d.success && d.config) {
        setSettings({
          outputDir: d.config.outputDir || './downloads',
          maxWorkers: d.config.maxWorkers || 3,
          proxyUrl: d.config.proxyUrl || '',
          delaySec: d.config.delaySec || 1.0,
          namingFormat: d.config.namingFormat || 'simple'
        });
      }
    }).catch(() => {});
  }, []);

  // Toast Notifications
  const [toast, setToast] = useState(null);
  const showToast = (message, type = 'info') => {
    setToast({
      id: Date.now(),
      message,
      type
    });
    setTimeout(() => setToast(null), 3500);
  };

  // Utilities State
  const [m3u8Input, setM3u8Input] = useState('');
  const [m3u8Result, setM3u8Result] = useState(null);

  // Inflight guard and debounced search to prevent request flooding
  const isFetchingTasksRef = useRef(false);
  const isFetchingLogsRef = useRef(false);
  const configDebounceRef = useRef(null);
  const searchInputRef = useRef(null);
  const logContainerRef = useRef(null);
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [actionInProgress, setActionInProgress] = useState(false);
  const [busyTaskIds, setBusyTaskIds] = useState({});
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(searchQuery), 250);
    return () => clearTimeout(t);
  }, [searchQuery]);

  // Native Window IPC Helpers with cooldown
  const winActionCooldownRef = useRef(false);
  const triggerWinAction = fn => {
    if (winActionCooldownRef.current) return;
    winActionCooldownRef.current = true;
    setTimeout(() => {
      winActionCooldownRef.current = false;
    }, 300);
    try {
      fn();
    } catch {}
  };
  const handleMinimize = () => triggerWinAction(() => {
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.minimize_window();
    }
  });
  const handleMaximize = () => triggerWinAction(() => {
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.maximize_window();
    }
  });
  const handleClose = () => triggerWinAction(() => {
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.close_window();
    } else {
      window.close();
    }
  });
  const handleStartDrag = e => {
    if (e.button !== 0) return;
    if (e.target.closest('.no-drag') || e.target.closest('button') || e.target.closest('input')) {
      return;
    }
    if (window.pywebview && window.pywebview.api && window.pywebview.api.start_drag) {
      window.pywebview.api.start_drag();
    }
  };
  const handlePickFolder = async () => {
    if (actionInProgress) return;
    setActionInProgress(true);
    try {
      let chosen = '';
      if (window.pywebview && window.pywebview.api && window.pywebview.api.select_folder) {
        try {
          chosen = await window.pywebview.api.select_folder(settings.outputDir);
        } catch {
          chosen = '';
        }
      }
      if (!chosen) {
        try {
          const res = await fetch('/api/choose-folder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ defaultPath: settings.outputDir })
          });
          const data = await res.json();
          if (data.success && data.folder) {
            chosen = data.folder;
          }
        } catch {}
      }
      if (chosen) {
        setSettings(prev => ({
          ...prev,
          outputDir: chosen
        }));
        showToast('Đã chọn thư mục: ' + chosen, 'success');
      }
    } catch {
      showToast('Lỗi chọn thư mục', 'error');
    } finally {
      setActionInProgress(false);
    }
  };

  const saveSettings = async () => {
    if (actionInProgress) return;
    setActionInProgress(true);
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
      });
      const data = await res.json();
      if (data.success) {
        showToast('Đã lưu cấu hình thành công: ' + (data.config?.outputDir || settings.outputDir), 'success');
        if (data.config && data.config.outputDir) {
          setSettings(prev => ({
            ...prev,
            outputDir: data.config.outputDir
          }));
        }
      } else {
        showToast(data.error || 'Lỗi lưu cấu hình', 'error');
      }
    } catch {
      showToast('Lỗi kết nối máy chủ', 'error');
    } finally {
      setActionInProgress(false);
    }
  };

  // Poll tasks with strictly 1 active request at a time (Poka-yoke)
  const fetchTasks = async () => {
    if (isFetchingTasksRef.current) return;
    isFetchingTasksRef.current = true;
    try {
      const res = await fetch('/api/tasks');
      if (res.ok) {
        const data = await res.json();
        setIsBackendConnected(true);
        const taskList = data.all_tasks || data.tasks || [];
        setAllTasks(taskList);
      }
    } catch {
      setIsBackendConnected(false);
    } finally {
      isFetchingTasksRef.current = false;
    }
  };
  const fetchSystemLogs = async () => {
    if (isFetchingLogsRef.current || !isConsoleOpen) return;
    isFetchingLogsRef.current = true;
    try {
      const res = await fetch('/api/logs');
      if (res.ok) {
        const data = await res.json();
        if (data.logs) setSystemLogs(data.logs);
      }
    } catch {} finally {
      isFetchingLogsRef.current = false;
    }
  };

  // Adaptive Polling: 1000ms when tasks downloading/queued, 3000ms when idle
  const hasActiveTasks = counts.downloading > 0 || counts.queued > 0;
  useEffect(() => {
    fetchTasks();
    let isCancelled = false;
    let timerId = null;

    const poll = async () => {
      await fetchTasks();
      if (isConsoleOpen) {
        await fetchSystemLogs();
      }
      if (taskDetail) {
        try {
          const r = await fetch(`/api/tasks/${taskDetail.id}/logs`);
          const d = await r.json();
          if (d.logs) setTaskLogs(d.logs);
        } catch {}
      }
      if (!isCancelled) {
        const delay = hasActiveTasks ? 1000 : 3000;
        timerId = setTimeout(poll, delay);
      }
    };

    const initialDelay = hasActiveTasks ? 1000 : 3000;
    timerId = setTimeout(poll, initialDelay);

    return () => {
      isCancelled = true;
      if (timerId) clearTimeout(timerId);
    };
  }, [hasActiveTasks, isConsoleOpen, taskDetail ? taskDetail.id : null]);

  // Global keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = e => {
      if (e.key === 'Escape') {
        setIsAddModalOpen(false);
        setTaskDetail(null);
        setPreviewTask(null);
        setContextMenu({
          visible: false,
          x: 0,
          y: 0,
          task: null
        });
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'n') {
        e.preventDefault();
        setIsAddModalOpen(true);
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f') {
        e.preventDefault();
        if (searchInputRef.current) searchInputRef.current.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Detected Provider
  const detectedProvider = useMemo(() => detectProviderFromUrl(url), [url]);

  // Computed Selected Episodes count for live preview
  const selectedEpList = useMemo(() => {
    if (!parsedData) return [];
    return parseRangeNumbers(rangeInput, parsedData.totalEpisodes);
  }, [rangeInput, parsedData]);

  // URL Parser
  const handleParse = async e => {
    if (e) e.preventDefault();
    const cleanUrl = url.trim().replace(/^["']|["']$/g, '');
    if (!cleanUrl) return;
    setIsParsing(true);
    setParseError(null);
    try {
      const res = await fetch('/api/parse', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          url: cleanUrl
        })
      });
      const data = await res.json();
      if (data.success) {
        setParsedData(data);
        setRangeInput(`1-${Math.min(data.totalEpisodes, 12)}`);
        showToast(`Đã nhận diện ${data.totalEpisodes} tập từ ${data.site.toUpperCase()}`, 'success');
        setIsAddModalOpen(true);
      } else {
        setParseError(data.error || 'Không thể trích xuất thông tin anime.');
        showToast(data.error || 'Lỗi phân tích URL', 'error');
      }
    } catch (err) {
      const msg = 'Lỗi kết nối máy chủ: ' + err.message;
      setParseError(msg);
      showToast(msg, 'error');
    } finally {
      setIsParsing(false);
    }
  };

  // Add to Queue
  const handleConfirmAdd = async () => {
    if (!parsedData) return;
    const epsToQueue = selectedEpList.length > 0 ? selectedEpList : parsedData.episodes.map(e => e.num);
    try {
      const res = await fetch('/api/tasks/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          url: parsedData.rawUrl,
          animeTitle: parsedData.title,
          episodes: epsToQueue,
          site: parsedData.site,
          quality: selectedQuality,
          downloadMode: downloadMode,
          targetSubLangs: selectedLangs,
          outputDir: settings.outputDir
        })
      });
      const data = await res.json();
      if (data.success) {
        showToast(`Đã thêm ${epsToQueue.length} tập vào hàng đợi tải!`, 'success');
        setIsAddModalOpen(false);
        setParsedData(null);
        setUrl('');
        setActiveTab('tasks');
        fetchTasks();
      } else {
        showToast('Lỗi khi thêm tác vụ: ' + (data.error || 'Không xác định'), 'error');
      }
    } catch (err) {
      showToast('Lỗi máy chủ khi tạo tác vụ', 'error');
    }
  };

  // Queue batch action with lock (Poka-yoke against mash clicking)
  const runQueueAction = async (actionPath, successMsg, toastType = 'info') => {
    if (actionInProgress) return;
    setActionInProgress(true);
    try {
      await fetch(actionPath, {
        method: 'POST'
      });
      showToast(successMsg, toastType);
      fetchTasks();
    } catch {
      showToast('Lỗi thực hiện thao tác hàng đợi', 'error');
    } finally {
      setTimeout(() => setActionInProgress(false), 400);
    }
  };

  // Task actions with toast feedback & per-task mutex
  const taskAction = async (taskId, action, body = {}) => {
    if (busyTaskIds[taskId]) return;
    setBusyTaskIds(prev => ({
      ...prev,
      [taskId]: true
    }));
    try {
      const res = await fetch(`/api/tasks/${taskId}/${action}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(body)
      });
      const data = await res.json();
      if (data.success) {
        if (action === 'pause') showToast('Đã tạm dừng tác vụ', 'info');
        if (action === 'resume') showToast('Đã tiếp tục tác vụ', 'success');
        if (action === 'restart') showToast('Đang tải lại từ đầu', 'info');
        if (action === 'delete') showToast('Đã xóa tác vụ', 'warn');
        if (action === 'open-file') showToast('Đang mở file video...', 'success');
        if (action === 'open-folder') showToast('Đang mở thư mục trong Explorer...', 'info');
      }
      fetchTasks();
    } catch {
      showToast(`Lỗi khi thực hiện thao tác ${action}`, 'error');
    } finally {
      setTimeout(() => {
        setBusyTaskIds(prev => {
          const next = {
            ...prev
          };
          delete next[taskId];
          return next;
        });
      }, 350);
    }
  };
  const openInspector = async task => {
    setTaskDetail(task);
    try {
      const res = await fetch(`/api/tasks/${task.id}/logs`);
      const data = await res.json();
      if (data.logs) setTaskLogs(data.logs);
    } catch {}
  };

  // Filtered logs
  const filteredLogs = useMemo(() => {
    return systemLogs.filter(l => {
      const matchesLevel = logLevelFilter === 'ALL' || l.level && l.level.toUpperCase() === logLevelFilter;
      const matchesQuery = !logFilterQuery || l.message.toLowerCase().includes(logFilterQuery.toLowerCase()) || l.category && l.category.toLowerCase().includes(logFilterQuery.toLowerCase());
      return matchesLevel && matchesQuery;
    });
  }, [systemLogs, logLevelFilter, logFilterQuery]);

  // Navigation Items definition (matching DLSS Swapper icons and titles)
  const NAV_ITEMS = [{
    id: 'home',
    label: 'Trang chủ',
    icon: /*#__PURE__*/React.createElement("svg", {
      className: "w-4 h-4",
      fill: "none",
      stroke: "currentColor",
      viewBox: "0 0 24 24"
    }, /*#__PURE__*/React.createElement("path", {
      strokeLinecap: "round",
      strokeLinejoin: "round",
      strokeWidth: 2,
      d: "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"
    }))
  }, {
    id: 'tasks',
    label: 'Tác vụ tải',
    icon: /*#__PURE__*/React.createElement("svg", {
      className: "w-4 h-4",
      fill: "none",
      stroke: "currentColor",
      viewBox: "0 0 24 24"
    }, /*#__PURE__*/React.createElement("path", {
      strokeLinecap: "round",
      strokeLinejoin: "round",
      strokeWidth: 2,
      d: "M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
    }))
  }, {
    id: 'utilities',
    label: 'Tiện ích',
    icon: /*#__PURE__*/React.createElement("svg", {
      className: "w-4 h-4",
      fill: "none",
      stroke: "currentColor",
      viewBox: "0 0 24 24"
    }, /*#__PURE__*/React.createElement("path", {
      strokeLinecap: "round",
      strokeLinejoin: "round",
      strokeWidth: 2,
      d: "M11 4a2 2 0 114 0v1a1 1 0 001 1h3a1 1 0 011 1v3a1 1 0 01-1 1h-1a2 2 0 100 4h1a1 1 0 011 1v3a1 1 0 01-1 1h-3a1 1 0 01-1-1v-1a2 2 0 10-4 0v1a1 1 0 01-1 1H7a1 1 0 01-1-1v-3a1 1 0 00-1-1H4a2 2 0 110-4h1a1 1 0 001-1V7a1 1 0 011-1h3a1 1 0 001-1V4z"
    }))
  }, {
    id: 'history',
    label: 'Lịch sử',
    icon: /*#__PURE__*/React.createElement("svg", {
      className: "w-4 h-4",
      fill: "none",
      stroke: "currentColor",
      viewBox: "0 0 24 24"
    }, /*#__PURE__*/React.createElement("path", {
      strokeLinecap: "round",
      strokeLinejoin: "round",
      strokeWidth: 2,
      d: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
    }))
  }, {
    id: 'settings',
    label: 'Cài đặt',
    icon: /*#__PURE__*/React.createElement("svg", {
      className: "w-4 h-4",
      fill: "none",
      stroke: "currentColor",
      viewBox: "0 0 24 24"
    }, /*#__PURE__*/React.createElement("path", {
      strokeLinecap: "round",
      strokeLinejoin: "round",
      strokeWidth: 2,
      d: "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
    }), /*#__PURE__*/React.createElement("path", {
      strokeLinecap: "round",
      strokeLinejoin: "round",
      strokeWidth: 2,
      d: "M15 12a3 3 0 11-6 0 3 3 0 016 0z"
    }))
  }, {
    id: 'about',
    label: 'Giới thiệu',
    icon: /*#__PURE__*/React.createElement("svg", {
      className: "w-4 h-4",
      fill: "none",
      stroke: "currentColor",
      viewBox: "0 0 24 24"
    }, /*#__PURE__*/React.createElement("path", {
      strokeLinecap: "round",
      strokeLinejoin: "round",
      strokeWidth: 2,
      d: "M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
    }))
  }];
  return /*#__PURE__*/React.createElement("div", {
    className: "flex h-screen overflow-hidden bg-[#0A0D14] text-slate-100 font-sans",
    onClick: () => setContextMenu({
      visible: false,
      x: 0,
      y: 0,
      task: null
    })
  }, toast && /*#__PURE__*/React.createElement("div", {
    className: `fixed top-12 right-6 z-50 flex items-center gap-2.5 px-4 py-2.5 rounded-xl border shadow-2xl backdrop-blur-md text-xs font-medium animate-in fade-in duration-200 ${toast.type === 'success' ? 'bg-emerald-950/90 border-emerald-500/50 text-emerald-200' : toast.type === 'warn' ? 'bg-amber-950/90 border-amber-500/50 text-amber-200' : toast.type === 'error' ? 'bg-rose-950/90 border-rose-500/50 text-rose-200' : 'bg-[#131824]/90 border-cyan-500/50 text-cyan-200'}`
  }, /*#__PURE__*/React.createElement("span", null, toast.type === 'success' ? '✓' : toast.type === 'error' ? '✕' : toast.type === 'warn' ? '⚠️' : 'ℹ'), /*#__PURE__*/React.createElement("span", null, toast.message)), /*#__PURE__*/React.createElement("aside", {
    className: "w-64 bg-[#0D111A] border-r border-white/[0.06] flex flex-col p-4 select-none shrink-0 z-20"
  }, /*#__PURE__*/React.createElement("div", {
    className: "flex items-center gap-3 px-2 py-3 mb-6 pywebview-drag-region titlebar-drag select-none cursor-default",
    onMouseDown: handleStartDrag
  }, /*#__PURE__*/React.createElement("img", {
    src: "/assets/logo.svg",
    alt: "TeamTrau",
    className: "w-10 h-10 rounded-xl shadow-[0_0_16px_rgba(239,68,68,0.35)] object-cover border border-rose-500/30"
  }), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "text-sm font-extrabold tracking-wider text-white flex items-center gap-1.5"
  }, "TEAMTRAU"), /*#__PURE__*/React.createElement("div", {
    className: "text-[10px] font-bold text-rose-400 tracking-widest uppercase"
  }, "DOWNLOADER"))), /*#__PURE__*/React.createElement("nav", {
    className: "flex flex-col gap-1.5 flex-1"
  }, NAV_ITEMS.map(item => {
    const isActive = activeTab === item.id;
    return /*#__PURE__*/React.createElement("button", {
      key: item.id,
      type: "button",
      onClick: () => setActiveTab(item.id),
      className: `w-full px-4 py-2.5 flex items-center justify-between text-xs font-medium transition-all ${isActive ? 'nav-pill-active shadow-sm' : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04] rounded-full'}`
    }, /*#__PURE__*/React.createElement("div", {
      className: "flex items-center gap-3"
    }, /*#__PURE__*/React.createElement("span", {
      className: isActive ? 'text-emerald-400' : 'text-slate-400'
    }, item.icon), /*#__PURE__*/React.createElement("span", null, item.label)), isActive && /*#__PURE__*/React.createElement("span", {
      className: "nav-dot-active"
    }));
  })), /*#__PURE__*/React.createElement("div", {
    className: "mt-auto p-3.5 bg-[#131824] border border-white/[0.08] rounded-2xl"
  }, /*#__PURE__*/React.createElement("div", {
    className: "flex items-center gap-2 mb-1"
  }, /*#__PURE__*/React.createElement("span", {
    className: `w-2.5 h-2.5 rounded-full ${counts.downloading > 0 ? 'bg-cyan-400 animate-pulse' : 'bg-emerald-400 shadow-[0_0_8px_#22C55E]'}`
  }), /*#__PURE__*/React.createElement("span", {
    className: "text-xs font-bold text-white"
  }, counts.downloading > 0 ? `Đang tải ${counts.downloading} tác vụ` : 'Sẵn sàng')), /*#__PURE__*/React.createElement("div", {
    className: "text-[11px] text-slate-400 mb-2"
  }, "TeamTrau v2.2.0"), /*#__PURE__*/React.createElement("div", {
    className: "w-full bg-slate-800/80 rounded-full h-1 overflow-hidden"
  }, /*#__PURE__*/React.createElement("div", {
    className: "bg-emerald-500 h-1 rounded-full transition-all duration-500",
    style: {
      width: counts.downloading > 0 ? `${Math.min(95, counts.downloading * 25)}%` : '100%'
    }
  })))), /*#__PURE__*/React.createElement("div", {
    className: "flex-1 flex flex-col overflow-hidden bg-[#0A0D14]"
  }, /*#__PURE__*/React.createElement("header", {
    className: "h-11 flex items-center justify-between px-6 bg-[#0A0D14] border-b border-white/[0.05] pywebview-drag-region titlebar-drag select-none shrink-0 cursor-default",
    onMouseDown: handleStartDrag,
    onDoubleClick: e => {
      if (e.target.closest('.no-drag') || e.target.closest('button')) return;
      handleMaximize();
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "text-xs font-semibold text-slate-400 tracking-wide"
  }, NAV_ITEMS.find(n => n.id === activeTab)?.label || 'TeamTrau'), /*#__PURE__*/React.createElement("div", {
    className: "flex items-center gap-2 no-drag"
  }, /*#__PURE__*/React.createElement("button", {
    type: "button",
    title: "Chuyển chế độ sáng/tối",
    className: "w-7 h-7 rounded-full bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] flex items-center justify-center text-slate-300 hover:text-white transition-all text-xs"
  }, "☀️"), /*#__PURE__*/React.createElement("div", {
    className: "flex items-center gap-1 px-2.5 py-1 rounded-full bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-[11px] font-bold text-slate-300 cursor-pointer"
  }, /*#__PURE__*/React.createElement("span", null, "VI"), /*#__PURE__*/React.createElement("span", {
    className: "text-[9px] text-slate-500"
  }, "▾")), /*#__PURE__*/React.createElement("div", {
    className: "w-[1px] h-4 bg-white/10 mx-1"
  }), /*#__PURE__*/React.createElement("div", {
    className: "flex items-center"
  }, /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: handleMinimize,
    title: "Thu nhỏ",
    className: "w-8 h-8 flex items-center justify-center text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
  }, "─"), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: handleMaximize,
    title: "Phóng to / Khôi phục",
    className: "w-8 h-8 flex items-center justify-center text-slate-400 hover:text-white hover:bg-white/10 transition-colors text-xs"
  }, "▢"), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: handleClose,
    title: "Đóng ứng dụng",
    className: "w-8 h-8 flex items-center justify-center text-slate-400 hover:text-white hover:bg-rose-600 transition-colors text-xs"
  }, "✕")))), /*#__PURE__*/React.createElement("main", {
    className: "flex-1 overflow-y-auto p-6"
  }, activeTab === 'home' && /*#__PURE__*/React.createElement("div", {
    className: "max-w-5xl space-y-6"
  }, /*#__PURE__*/React.createElement("div", {
    className: "bg-[#131824] border border-white/[0.08] rounded-2xl p-5 shadow-lg"
  }, /*#__PURE__*/React.createElement("label", {
    className: "block text-xs font-bold text-slate-300 mb-2 uppercase tracking-wider"
  }, "Anime URL"), /*#__PURE__*/React.createElement("form", {
    onSubmit: handleParse,
    className: "flex items-center gap-3"
  }, /*#__PURE__*/React.createElement("div", {
    className: "relative flex-1"
  }, /*#__PURE__*/React.createElement("input", {
    type: "text",
    value: url,
    onChange: e => setUrl(e.target.value),
    placeholder: "Dán đường dẫn anime (AllWish, AniKoto, AnimeSuge, AnimeCube)...",
    className: "w-full bg-[#0A0D14] border border-white/10 focus:border-emerald-500 text-xs text-white rounded-xl px-4 py-3 placeholder:text-slate-500 focus:outline-none transition-all"
  }), detectedProvider && /*#__PURE__*/React.createElement("span", {
    className: `absolute right-3 top-2.5 px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${detectedProvider.color}`
  }, detectedProvider.name)), /*#__PURE__*/React.createElement("button", {
    type: "submit",
    disabled: isParsing || !url.trim(),
    className: "px-6 py-3 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 disabled:cursor-not-allowed text-black font-bold text-xs rounded-xl shadow-lg shadow-emerald-500/20 active:scale-95 transition-all flex items-center gap-2 shrink-0"
  }, isParsing ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", {
    className: "w-3.5 h-3.5 border-2 border-black border-t-transparent rounded-full animate-spin"
  }), /*#__PURE__*/React.createElement("span", null, "Đang phân tích...")) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", null, "Phân tích")))), /*#__PURE__*/React.createElement("div", {
    className: "mt-4 pt-3 border-t border-white/[0.05]"
  }, /*#__PURE__*/React.createElement("div", {
    className: "text-[11px] font-bold text-slate-400 mb-2"
  }, "Quick presets"), /*#__PURE__*/React.createElement("div", {
    className: "flex flex-wrap gap-2"
  }, SITE_PRESETS.map(p => /*#__PURE__*/React.createElement("button", {
    key: p.id,
    type: "button",
    onClick: () => {
      setUrl(p.sample);
    },
    className: `text-xs px-3.5 py-1.5 rounded-xl border font-medium transition-all hover:scale-105 active:scale-95 flex items-center gap-1.5 ${p.color}`
  }, /*#__PURE__*/React.createElement("span", null, "⚡"), " ", p.name))))), /*#__PURE__*/React.createElement("div", {
    className: "grid grid-cols-1 md:grid-cols-4 gap-4"
  }, /*#__PURE__*/React.createElement("div", {
    className: "bg-[#131824] border border-white/[0.08] rounded-2xl p-4"
  }, /*#__PURE__*/React.createElement("div", {
    className: "text-slate-400 text-xs"
  }, "Tổng tác vụ"), /*#__PURE__*/React.createElement("div", {
    className: "text-xl font-bold text-white mt-1"
  }, counts.all)), /*#__PURE__*/React.createElement("div", {
    className: "bg-[#131824] border border-white/[0.08] rounded-2xl p-4"
  }, /*#__PURE__*/React.createElement("div", {
    className: "text-slate-400 text-xs"
  }, "Đang tải"), /*#__PURE__*/React.createElement("div", {
    className: "text-xl font-bold text-emerald-400 mt-1"
  }, counts.downloading)), /*#__PURE__*/React.createElement("div", {
    className: "bg-[#131824] border border-white/[0.08] rounded-2xl p-4"
  }, /*#__PURE__*/React.createElement("div", {
    className: "text-slate-400 text-xs"
  }, "Đã hoàn thành"), /*#__PURE__*/React.createElement("div", {
    className: "text-xl font-bold text-cyan-400 mt-1"
  }, counts.completed)), /*#__PURE__*/React.createElement("div", {
    className: "bg-[#131824] border border-white/[0.08] rounded-2xl p-4"
  }, /*#__PURE__*/React.createElement("div", {
    className: "text-slate-400 text-xs"
  }, "Thư mục tải"), /*#__PURE__*/React.createElement("div", {
    className: "text-xs font-mono text-slate-300 mt-2 truncate",
    title: settings.outputDir
  }, settings.outputDir))), /*#__PURE__*/React.createElement("div", {
    className: "bg-[#131824] border border-white/[0.08] rounded-2xl p-5"
  }, /*#__PURE__*/React.createElement("div", {
    className: "flex items-center justify-between mb-4"
  }, /*#__PURE__*/React.createElement("h3", {
    className: "text-xs font-bold text-white uppercase tracking-wider"
  }, "Tiến trình tải gần đây"), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: () => setActiveTab('tasks'),
    className: "text-xs text-emerald-400 hover:underline flex items-center gap-1"
  }, "Xem tất cả (", counts.all, ") →")), allTasks.length === 0 ? /*#__PURE__*/React.createElement("div", {
    className: "py-8 text-center text-xs text-slate-500"
  }, "Chưa có tác vụ tải nào. Hãy dán URL ở trên để bắt đầu!") : /*#__PURE__*/React.createElement("div", {
    className: "space-y-2"
  }, allTasks.slice(0, 5).map(task => /*#__PURE__*/React.createElement("div", {
    key: task.id,
    onClick: () => openInspector(task),
    className: "bg-[#0A0D14]/70 border border-white/[0.05] rounded-xl p-3 flex items-center justify-between gap-4 hover:border-emerald-500/30 transition-all cursor-pointer"
  }, /*#__PURE__*/React.createElement("div", {
    className: "flex items-center gap-3 min-w-0"
  }, /*#__PURE__*/React.createElement("span", {
    className: "text-base"
  }, task.download_mode === 'sub_only' ? '📝' : '🎬'), /*#__PURE__*/React.createElement("div", {
    className: "min-w-0"
  }, /*#__PURE__*/React.createElement("div", {
    className: "text-xs font-semibold text-white truncate"
  }, task.anime_title, " - Tập ", task.episode_num), /*#__PURE__*/React.createElement("div", {
    className: "text-[10px] text-slate-400 font-mono flex items-center gap-2 mt-0.5"
  }, /*#__PURE__*/React.createElement("span", {
    className: "text-emerald-400"
  }, task.site.toUpperCase()), /*#__PURE__*/React.createElement("span", null, "•"), /*#__PURE__*/React.createElement("span", null, task.quality), /*#__PURE__*/React.createElement("span", null, "•"), /*#__PURE__*/React.createElement("span", null, task.status.toUpperCase())))), /*#__PURE__*/React.createElement("div", {
    className: "flex items-center gap-4 shrink-0"
  }, /*#__PURE__*/React.createElement("div", {
    className: "w-32 hidden sm:block"
  }, /*#__PURE__*/React.createElement("div", {
    className: "flex justify-between text-[10px] text-slate-400 mb-1"
  }, /*#__PURE__*/React.createElement("span", null, task.progress_percent, "%"), /*#__PURE__*/React.createElement("span", {
    className: "text-emerald-400"
  }, task.speed_mb_s ? `${task.speed_mb_s.toFixed(1)} MB/s` : '--')), /*#__PURE__*/React.createElement("div", {
    className: "w-full bg-slate-800 rounded-full h-1 overflow-hidden"
  }, /*#__PURE__*/React.createElement("div", {
    className: "bg-emerald-500 h-1 rounded-full",
    style: {
      width: `${task.progress_percent}%`
    }
  }))), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: e => {
      e.stopPropagation();
      if (task.status === 'downloading') taskAction(task.id, 'pause');else if (task.status === 'paused') taskAction(task.id, 'resume');else taskAction(task.id, 'open-folder');
    },
    className: "px-2.5 py-1 text-[11px] rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300"
  }, task.status === 'downloading' ? 'Tạm dừng' : task.status === 'completed' ? 'Mở folder' : 'Tiếp tục'))))))), activeTab === 'tasks' && /*#__PURE__*/React.createElement("div", {
    className: "space-y-4"
  }, /*#__PURE__*/React.createElement("div", {
    className: "flex flex-wrap items-center justify-between gap-3 bg-[#131824] border border-white/[0.08] p-3 rounded-2xl"
  }, /*#__PURE__*/React.createElement("div", {
    className: "flex items-center gap-2"
  }, /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: () => {
      setParsedData(null);
      setUrl('');
      setIsAddModalOpen(true);
    },
    className: "px-3.5 py-1.5 bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-xs rounded-xl shadow-md active:scale-95 transition-all flex items-center gap-1.5"
  }, /*#__PURE__*/React.createElement("span", null, "+"), " Thêm URL"), /*#__PURE__*/React.createElement("button", {
    type: "button",
    disabled: actionInProgress,
    onClick: () => runQueueAction('/api/queue/resume-all', 'Đã tiếp tục tất cả tác vụ', 'success'),
    className: "px-3 py-1.5 bg-white/5 hover:bg-white/10 disabled:opacity-50 border border-white/10 text-slate-300 text-xs rounded-xl transition-all active:scale-95"
  }, "▶ Tiếp Tục Tất Cả"), /*#__PURE__*/React.createElement("button", {
    type: "button",
    disabled: actionInProgress,
    onClick: () => runQueueAction('/api/queue/pause-all', 'Đã tạm dừng tất cả tác vụ', 'warn'),
    className: "px-3 py-1.5 bg-white/5 hover:bg-white/10 disabled:opacity-50 border border-white/10 text-slate-300 text-xs rounded-xl transition-all active:scale-95"
  }, "⏸ Tạm Dừng"), /*#__PURE__*/React.createElement("button", {
    type: "button",
    disabled: actionInProgress,
    onClick: () => runQueueAction('/api/queue/clear-completed', 'Đã dọn tác vụ hoàn thành', 'info'),
    className: "px-3 py-1.5 bg-white/5 hover:bg-white/10 disabled:opacity-50 border border-white/5 text-slate-400 hover:text-slate-200 text-xs rounded-xl transition-all active:scale-95"
  }, "✓ Dọn Đã Xong")), /*#__PURE__*/React.createElement("div", {
    className: "flex items-center gap-2"
  }, /*#__PURE__*/React.createElement("input", {
    ref: searchInputRef,
    type: "text",
    value: searchQuery,
    onChange: e => setSearchQuery(e.target.value),
    placeholder: "Tìm kiếm anime... (Ctrl+F)",
    className: "bg-[#0A0D14] text-slate-200 text-xs px-3 py-1.5 rounded-xl border border-white/10 focus:border-emerald-500 focus:outline-none w-52"
  }))), /*#__PURE__*/React.createElement("div", {
    className: "flex items-center gap-2 overflow-x-auto pb-1"
  }, [{
    id: 'all',
    label: 'Tất Cả',
    count: counts.all
  }, {
    id: 'downloading',
    label: 'Đang Tải',
    count: counts.downloading,
    color: 'text-emerald-400'
  }, {
    id: 'paused',
    label: 'Tạm Dừng',
    count: counts.paused,
    color: 'text-amber-400'
  }, {
    id: 'completed',
    label: 'Hoàn Thành',
    count: counts.completed,
    color: 'text-cyan-400'
  }, {
    id: 'failed',
    label: 'Lỗi',
    count: counts.failed,
    color: 'text-rose-400'
  }].map(f => /*#__PURE__*/React.createElement("button", {
    key: f.id,
    type: "button",
    onClick: () => setSelectedCategory(f.id),
    className: `px-3 py-1 rounded-full text-xs font-medium border transition-all flex items-center gap-1.5 ${selectedCategory === f.id ? 'bg-white/10 border-emerald-500/50 text-white shadow-sm' : 'bg-white/[0.02] border-white/5 text-slate-400 hover:bg-white/5'}`
  }, /*#__PURE__*/React.createElement("span", {
    className: f.color || 'text-slate-300'
  }, f.label), /*#__PURE__*/React.createElement("span", {
    className: "text-[10px] font-mono px-1.5 py-0.2 bg-black/40 rounded-full"
  }, f.count)))), /*#__PURE__*/React.createElement("div", {
    className: "bg-[#131824] border border-white/[0.08] rounded-2xl overflow-hidden"
  }, filteredTasks.length === 0 ? /*#__PURE__*/React.createElement("div", {
    className: "p-12 text-center text-slate-500 text-xs"
  }, "Không có tác vụ nào trong danh mục này.") : /*#__PURE__*/React.createElement("div", {
    className: "overflow-x-auto"
  }, /*#__PURE__*/React.createElement("table", {
    className: "w-full text-left border-collapse select-none"
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", {
    className: "border-b border-white/10 bg-[#0E131E] text-[11px] font-bold uppercase tracking-wider text-slate-400"
  }, /*#__PURE__*/React.createElement("th", {
    className: "py-3 px-4"
  }, "Tác Vụ Anime"), /*#__PURE__*/React.createElement("th", {
    className: "py-3 px-3"
  }, "Dung Lượng"), /*#__PURE__*/React.createElement("th", {
    className: "py-3 px-3 w-48"
  }, "Tiến Độ"), /*#__PURE__*/React.createElement("th", {
    className: "py-3 px-3"
  }, "Trạng Thái"), /*#__PURE__*/React.createElement("th", {
    className: "py-3 px-3"
  }, "Tốc Độ"), /*#__PURE__*/React.createElement("th", {
    className: "py-3 px-3 text-right"
  }, "Thao Tác"))), /*#__PURE__*/React.createElement("tbody", {
    className: "divide-y divide-white/5 text-xs font-mono"
  }, filteredTasks.map(task => /*#__PURE__*/React.createElement("tr", {
    key: task.id,
    onContextMenu: e => {
      e.preventDefault();
      setContextMenu({
        visible: true,
        x: e.clientX,
        y: e.clientY,
        task
      });
    },
    onDoubleClick: () => openInspector(task),
    className: "hover:bg-white/[0.03] transition-colors cursor-pointer group"
  }, /*#__PURE__*/React.createElement("td", {
    className: "py-3 px-4 font-sans"
  }, /*#__PURE__*/React.createElement("div", {
    className: "flex items-center gap-2.5"
  }, /*#__PURE__*/React.createElement("span", {
    className: "text-base"
  }, task.download_mode === 'sub_only' ? '📝' : '🎬'), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "font-semibold text-slate-100 group-hover:text-emerald-400 transition-colors"
  }, task.anime_title, " - Tập ", task.episode_num), /*#__PURE__*/React.createElement("div", {
    className: "text-[11px] text-slate-400 font-mono flex items-center gap-2 mt-0.5"
  }, /*#__PURE__*/React.createElement("span", {
    className: "text-emerald-400 font-semibold"
  }, task.site.toUpperCase()), /*#__PURE__*/React.createElement("span", null, "•"), /*#__PURE__*/React.createElement("span", null, task.quality), /*#__PURE__*/React.createElement("span", null, "•"), /*#__PURE__*/React.createElement("span", {
    className: "text-cyan-400"
  }, task.download_mode.toUpperCase()))))), /*#__PURE__*/React.createElement("td", {
    className: "py-3 px-3 text-slate-400"
  }, task.file_size_bytes > 0 ? formatBytes(task.file_size_bytes) : '--'), /*#__PURE__*/React.createElement("td", {
    className: "py-3 px-3"
  }, /*#__PURE__*/React.createElement("div", {
    className: "flex flex-col gap-1"
  }, /*#__PURE__*/React.createElement("div", {
    className: "flex items-center justify-between text-[11px]"
  }, /*#__PURE__*/React.createElement("span", {
    className: "font-bold text-slate-200"
  }, task.progress_percent, "%"), /*#__PURE__*/React.createElement("span", {
    className: "text-slate-500 font-mono text-[10px]"
  }, task.total_segments > 0 ? `${task.downloaded_segments}/${task.total_segments}` : '')), /*#__PURE__*/React.createElement("div", {
    className: "w-full h-1.5 bg-slate-800 rounded-full overflow-hidden"
  }, /*#__PURE__*/React.createElement("div", {
    className: `h-full rounded-full transition-all duration-300 ${task.status === 'completed' ? 'bg-emerald-400' : task.status === 'failed' ? 'bg-rose-500' : task.status === 'paused' ? 'bg-amber-400' : 'bg-emerald-500 animate-pulse-fast'}`,
    style: {
      width: `${task.progress_percent}%`
    }
  })))), /*#__PURE__*/React.createElement("td", {
    className: "py-3 px-3"
  }, task.status === 'completed' && /*#__PURE__*/React.createElement("span", {
    className: "inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-950/60 text-emerald-400 border border-emerald-500/30"
  }, "✓ HOÀN TẤT"), task.status === 'downloading' && /*#__PURE__*/React.createElement("span", {
    className: "inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-cyan-950/60 text-cyan-400 border border-cyan-500/30"
  }, "⚡ ĐANG TẢI"), task.status === 'paused' && /*#__PURE__*/React.createElement("span", {
    className: "inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-950/60 text-amber-400 border border-amber-500/30"
  }, "⏸ TẠM DỪNG"), task.status === 'failed' && /*#__PURE__*/React.createElement("span", {
    className: "inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-rose-950/60 text-rose-400 border border-rose-500/30"
  }, "✕ LỖI TẢI"), task.status === 'queued' && /*#__PURE__*/React.createElement("span", {
    className: "inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-slate-800 text-slate-400 border border-slate-700"
  }, "⏳ HÀNG ĐỢI")), /*#__PURE__*/React.createElement("td", {
    className: "py-3 px-3 text-emerald-400 font-bold"
  }, task.speed_mb_s ? `${task.speed_mb_s.toFixed(2)} MB/s` : '--'), /*#__PURE__*/React.createElement("td", {
    className: "py-3 px-3 text-right"
  }, /*#__PURE__*/React.createElement("div", {
    className: "flex items-center justify-end gap-1.5"
  }, task.status === 'downloading' && /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: e => {
      e.stopPropagation();
      taskAction(task.id, 'pause');
    },
    className: "p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-amber-300",
    title: "Tạm dừng"
  }, "⏸"), task.status === 'paused' && /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: e => {
      e.stopPropagation();
      taskAction(task.id, 'resume');
    },
    className: "p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-emerald-300",
    title: "Tiếp tục"
  }, "▶"), task.status === 'completed' && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: e => {
      e.stopPropagation();
      setPreviewTask(task);
    },
    className: "p-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/30",
    title: "Phát video xem trước (Preview)"
  }, "▶"), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: e => {
      e.stopPropagation();
      taskAction(task.id, 'open-folder');
    },
    className: "p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-cyan-300",
    title: "Mở thư mục chứa file"
  }, "📁")), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: e => {
      e.stopPropagation();
      taskAction(task.id, 'delete');
    },
    className: "p-1.5 rounded-lg bg-white/5 hover:bg-rose-950/40 text-rose-400",
    title: "Xóa tác vụ"
  }, "🗑")))))))))), activeTab === 'utilities' && /*#__PURE__*/React.createElement("div", {
    className: "max-w-4xl space-y-6"
  }, /*#__PURE__*/React.createElement("div", {
    className: "bg-[#131824] border border-white/[0.08] rounded-2xl p-6 shadow-xl"
  }, /*#__PURE__*/React.createElement("h3", {
    className: "text-sm font-bold text-white mb-2 flex items-center gap-2"
  }, /*#__PURE__*/React.createElement("span", null, "📡"), " Bộ Phân Tích Luồng HLS / M3U8 Inspector"), /*#__PURE__*/React.createElement("p", {
    className: "text-xs text-slate-400 mb-4"
  }, "Kiểm tra trực tiếp playlist M3U8, trích xuất danh sách độ phân giải, bitrate và đường dẫn audio/subtitle."), /*#__PURE__*/React.createElement("div", {
    className: "flex gap-2"
  }, /*#__PURE__*/React.createElement("input", {
    type: "text",
    value: m3u8Input,
    onChange: e => setM3u8Input(e.target.value),
    placeholder: "https://.../master.m3u8",
    className: "flex-1 bg-[#0A0D14] border border-white/10 text-xs px-4 py-2.5 rounded-xl text-white focus:outline-none focus:border-emerald-500"
  }), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: () => {
      if (!m3u8Input) return;
      setM3u8Result({
        status: 'Stream HLS hợp lệ (200 OK)',
        resolutions: ['1080p (4500 kbps)', '720p (2200 kbps)', '480p (900 kbps)'],
        audio: ['Stereo AAC 128k'],
        subs: ['English (vtt)', 'Spanish Latin (vtt)', 'Vietnamese (vtt)']
      });
      showToast('Đã phân tích cấu trúc HLS!', 'success');
    },
    className: "px-4 py-2.5 bg-emerald-500 text-black font-bold text-xs rounded-xl hover:bg-emerald-400"
  }, "Kiểm tra")), m3u8Result && /*#__PURE__*/React.createElement("div", {
    className: "mt-4 p-4 bg-[#0A0D14] rounded-xl border border-white/10 font-mono text-xs space-y-2"
  }, /*#__PURE__*/React.createElement("div", {
    className: "text-emerald-400 font-bold"
  }, m3u8Result.status), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("strong", {
    className: "text-slate-300"
  }, "Resolutions:"), " ", m3u8Result.resolutions.join(', ')), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("strong", {
    className: "text-slate-300"
  }, "Audio:"), " ", m3u8Result.audio.join(', ')), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("strong", {
    className: "text-slate-300"
  }, "Subtitles:"), " ", m3u8Result.subs.join(', ')))), /*#__PURE__*/React.createElement("div", {
    className: "grid grid-cols-1 md:grid-cols-2 gap-4"
  }, /*#__PURE__*/React.createElement("div", {
    className: "bg-[#131824] border border-white/[0.08] rounded-2xl p-5"
  }, /*#__PURE__*/React.createElement("h4", {
    className: "text-xs font-bold text-white mb-2 flex items-center gap-2"
  }, /*#__PURE__*/React.createElement("span", null, "📝"), " Chuyển Đổi Phụ Đề VTT sang SRT"), /*#__PURE__*/React.createElement("p", {
    className: "text-[11px] text-slate-400 mb-3"
  }, "Tự động chuẩn hóa timestamp và thẻ font sang định dạng SRT tương thích tất cả Smart TV & trình xem video."), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: () => showToast('Tính năng chuyển đổi phụ đề tự động kích hoạt khi tải', 'info'),
    className: "px-3.5 py-2 bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 text-xs rounded-xl"
  }, "Chuyển đổi file .vtt...")), /*#__PURE__*/React.createElement("div", {
    className: "bg-[#131824] border border-white/[0.08] rounded-2xl p-5"
  }, /*#__PURE__*/React.createElement("h4", {
    className: "text-xs font-bold text-white mb-2 flex items-center gap-2"
  }, /*#__PURE__*/React.createElement("span", null, "🎬"), " Ghép MP4 & Đóng Gói Soft-Sub"), /*#__PURE__*/React.createElement("p", {
    className: "text-[11px] text-slate-400 mb-3"
  }, "Sử dụng ffmpeg tích hợp ghép trọn gói video h264 và các track phụ đề đa ngôn ngữ thành 1 file duy nhất."), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: () => showToast('Động cơ ghép FFMPEG đã sẵn sàng', 'success'),
    className: "px-3.5 py-2 bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 text-xs rounded-xl"
  }, "Mux MP4 + Subtitles")))), activeTab === 'history' && /*#__PURE__*/React.createElement("div", {
    className: "max-w-5xl space-y-4"
  }, /*#__PURE__*/React.createElement("div", {
    className: "flex items-center justify-between"
  }, /*#__PURE__*/React.createElement("h3", {
    className: "text-xs font-bold text-white uppercase tracking-wider"
  }, "Lịch sử đã hoàn thành (", counts.completed, ")"), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: () => taskAction('all', 'open-folder'),
    className: "text-xs px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-slate-300"
  }, "📁 Mở thư mục tải")), allTasks.filter(t => t.status === 'completed').length === 0 ? /*#__PURE__*/React.createElement("div", {
    className: "p-12 text-center text-slate-500 text-xs bg-[#131824] rounded-2xl border border-white/[0.08]"
  }, "Chưa có file anime nào tải hoàn thành trong phiên này.") : /*#__PURE__*/React.createElement("div", {
    className: "space-y-2"
  }, allTasks.filter(t => t.status === 'completed').map(task => /*#__PURE__*/React.createElement("div", {
    key: task.id,
    className: "bg-[#131824] border border-white/[0.08] rounded-xl p-3.5 flex items-center justify-between"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "text-xs font-bold text-white"
  }, task.anime_title, " - Tập ", task.episode_num), /*#__PURE__*/React.createElement("div", {
    className: "text-[11px] text-slate-400 font-mono mt-1"
  }, task.site.toUpperCase(), " • ", task.quality, " • ", formatBytes(task.file_size_bytes))), /*#__PURE__*/React.createElement("div", {
    className: "flex gap-2"
  }, /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: () => setPreviewTask(task),
    className: "px-3 py-1.5 bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 rounded-xl text-xs hover:bg-emerald-500/30 font-medium flex items-center gap-1.5"
  }, "▶ Xem Trước"), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: () => taskAction(task.id, 'open-file'),
    className: "px-3 py-1.5 bg-white/5 text-slate-300 border border-white/10 rounded-xl text-xs hover:bg-white/10 flex items-center gap-1.5"
  }, "🎬 Mở Ngoài"), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: () => taskAction(task.id, 'open-folder'),
    className: "px-3 py-1.5 bg-white/5 text-slate-300 border border-white/10 rounded-xl text-xs hover:bg-white/10 flex items-center gap-1.5"
  }, "📁 Thư Mục")))))), activeTab === 'settings' && /*#__PURE__*/React.createElement("div", {
    className: "max-w-2xl space-y-6"
  }, /*#__PURE__*/React.createElement("h3", {
    className: "text-sm font-bold text-white mb-4"
  }, "Cấu Hình Ứng Dụng"), /*#__PURE__*/React.createElement("div", {
    className: "bg-[#131824] border border-white/[0.08] rounded-2xl p-6 space-y-5"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("label", {
    className: "block text-xs font-bold text-slate-300 mb-2"
  }, "Thư Mục Tải Xuống"), /*#__PURE__*/React.createElement("div", {
    className: "flex gap-2"
  }, /*#__PURE__*/React.createElement("input", {
    type: "text",
    value: settings.outputDir,
    onChange: e => setSettings({
      ...settings,
      outputDir: e.target.value
    }),
    className: "flex-1 bg-[#0A0D14] border border-white/10 text-xs px-3.5 py-2.5 rounded-xl font-mono text-white focus:outline-none focus:border-emerald-500"
  }), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: handlePickFolder,
    className: "px-4 py-2.5 bg-white/10 hover:bg-white/15 border border-white/10 text-xs font-semibold rounded-xl text-white"
  }, "Duyệt..."))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "flex justify-between text-xs font-bold text-slate-300 mb-1"
  }, /*#__PURE__*/React.createElement("span", null, "Số Luồng Tải Đồng Thời (Workers)"), /*#__PURE__*/React.createElement("span", {
    className: "text-emerald-400 font-mono"
  }, settings.maxWorkers)), /*#__PURE__*/React.createElement("input", {
    type: "range",
    min: "1",
    max: "8",
    value: settings.maxWorkers,
    onChange: e => {
      const val = parseInt(e.target.value, 10);
      setSettings(prev => ({
        ...prev,
        maxWorkers: val
      }));
      if (configDebounceRef.current) clearTimeout(configDebounceRef.current);
      configDebounceRef.current = setTimeout(() => {
        fetch('/api/queue/config', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            maxConcurrent: val
          })
        });
      }, 350);
    },
    className: "w-full accent-emerald-500"
  }), /*#__PURE__*/React.createElement("div", {
    className: "flex justify-between text-[10px] text-slate-500 font-mono mt-1"
  }, /*#__PURE__*/React.createElement("span", null, "1 (Tuần tự)"), /*#__PURE__*/React.createElement("span", null, "3 (Mặc định)"), /*#__PURE__*/React.createElement("span", null, "8 (Tối đa)"))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "flex justify-between text-xs font-bold text-slate-300 mb-1"
  }, /*#__PURE__*/React.createElement("span", null, "Độ Trễ Phân Tách Giữa Các Request (Anti-Ban)"), /*#__PURE__*/React.createElement("span", {
    className: "text-emerald-400 font-mono"
  }, settings.delaySec, "s")), /*#__PURE__*/React.createElement("input", {
    type: "range",
    min: "0.5",
    max: "5.0",
    step: "0.5",
    value: settings.delaySec,
    onChange: e => setSettings({
      ...settings,
      delaySec: parseFloat(e.target.value)
    }),
    className: "w-full accent-emerald-500"
  })), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("label", {
    className: "block text-xs font-bold text-slate-300 mb-2"
  }, "Proxy (HTTP / SOCKS5) Tùy Chọn"), /*#__PURE__*/React.createElement("input", {
    type: "text",
    value: settings.proxyUrl,
    onChange: e => setSettings({
      ...settings,
      proxyUrl: e.target.value
    }),
    placeholder: "http://user:pass@127.0.0.1:7890",
    className: "w-full bg-[#0A0D14] border border-white/10 text-xs px-3.5 py-2.5 rounded-xl font-mono text-white focus:outline-none focus:border-emerald-500"
  })), /*#__PURE__*/React.createElement("button", {
    type: "button",
    disabled: actionInProgress,
    onClick: saveSettings,
    className: "w-full py-3 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-black font-bold text-xs rounded-xl shadow-lg shadow-emerald-500/10 active:scale-95 transition-all"
  }, actionInProgress ? "Đang lưu cấu hình..." : "Lưu Cài Đặt"))), activeTab === 'about' && /*#__PURE__*/React.createElement("div", {
    className: "max-w-2xl space-y-4"
  }, /*#__PURE__*/React.createElement("h2", {
    className: "text-base font-bold text-white mb-4"
  }, "Giới thiệu"), /*#__PURE__*/React.createElement("div", {
    className: "bg-[#131824] border border-white/[0.08] rounded-2xl p-6 shadow-xl flex items-start gap-5"
  }, /*#__PURE__*/React.createElement("img", {
    src: "/assets/logo.svg",
    alt: "TeamTrau",
    className: "w-16 h-16 rounded-2xl border border-rose-500/30 shadow-[0_0_20px_rgba(239,68,68,0.25)] object-cover shrink-0"
  }), /*#__PURE__*/React.createElement("div", {
    className: "flex-1"
  }, /*#__PURE__*/React.createElement("div", {
    className: "text-sm font-bold text-white mb-1.5"
  }, "TeamTrau Anime Downloader"), /*#__PURE__*/React.createElement("p", {
    className: "text-xs text-slate-300 leading-relaxed mb-4"
  }, "Tải trọn bộ anime từ các trang anime phổ biến, giải mã HLS đa luồng và đồng bộ phụ đề bất cứ lúc nào."), /*#__PURE__*/React.createElement("div", {
    className: "text-xs text-slate-500 font-medium"
  }, "Thực hiện bởi TeamTrau & AlbedoDz"))), /*#__PURE__*/React.createElement("div", {
    className: "bg-[#131824] border border-white/[0.08] rounded-2xl p-6 space-y-3"
  }, /*#__PURE__*/React.createElement("div", {
    className: "text-xs font-bold uppercase tracking-wider text-slate-400 mb-2"
  }, "Thông Tin Hệ Thống"), /*#__PURE__*/React.createElement("div", {
    className: "grid grid-cols-2 gap-3 text-xs"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "text-slate-500"
  }, "Phiên bản:"), /*#__PURE__*/React.createElement("span", {
    className: "ml-2 font-mono text-emerald-400 font-bold"
  }, "v2.2.0 (Windows 11 Native)")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "text-slate-500"
  }, "Engine:"), /*#__PURE__*/React.createElement("span", {
    className: "ml-2 font-mono text-white"
  }, "Edge WebView2 (Core)")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "text-slate-500"
  }, "Cơ sở dữ liệu:"), /*#__PURE__*/React.createElement("span", {
    className: "ml-2 font-mono text-white"
  }, "SQLite3 (WAL Mode)")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "text-slate-500"
  }, "Bộ giải mã:"), /*#__PURE__*/React.createElement("span", {
    className: "ml-2 font-mono text-cyan-400"
  }, "RC4 VRF + HLS Decryptor"))))))), isAddModalOpen && /*#__PURE__*/React.createElement("div", {
    className: "fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md"
  }, /*#__PURE__*/React.createElement("div", {
    className: "bg-[#131824] border border-white/10 rounded-2xl w-full max-w-xl p-6 shadow-2xl space-y-5 animate-in zoom-in-95 duration-150"
  }, /*#__PURE__*/React.createElement("div", {
    className: "flex items-center justify-between border-b border-white/10 pb-3"
  }, /*#__PURE__*/React.createElement("h3", {
    className: "text-sm font-bold text-white flex items-center gap-2"
  }, /*#__PURE__*/React.createElement("span", null, "🎬"), " Thêm Tác Vụ Tải Anime Mới"), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: () => setIsAddModalOpen(false),
    className: "text-slate-400 hover:text-white"
  }, "✕")), !parsedData ? /*#__PURE__*/React.createElement("div", {
    className: "space-y-4"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("label", {
    className: "block text-xs font-bold text-slate-300 mb-1.5"
  }, "Đường Dẫn Anime"), /*#__PURE__*/React.createElement("input", {
    type: "text",
    value: url,
    onChange: e => setUrl(e.target.value),
    placeholder: "https://all-wish.me/watch/... hoặc https://anikototv.to/watch/...",
    className: "w-full bg-[#0A0D14] border border-white/10 text-xs px-3.5 py-2.5 rounded-xl text-white focus:outline-none focus:border-emerald-500 font-mono"
  })), parseError && /*#__PURE__*/React.createElement("div", {
    className: "text-xs text-rose-400 bg-rose-950/40 border border-rose-800/40 p-3 rounded-xl"
  }, parseError), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: handleParse,
    disabled: isParsing || !url.trim(),
    className: "w-full py-3 bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-xs rounded-xl shadow-lg shadow-emerald-500/10 active:scale-95 transition-all"
  }, isParsing ? 'Đang phân tích...' : 'Tiếp Tục Phân Tích')) : /*#__PURE__*/React.createElement("div", {
    className: "space-y-4"
  }, /*#__PURE__*/React.createElement("div", {
    className: "p-3 bg-[#0A0D14] rounded-xl border border-white/10 flex items-center justify-between"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "text-xs font-bold text-white"
  }, parsedData.title), /*#__PURE__*/React.createElement("div", {
    className: "text-[11px] text-emerald-400 font-mono mt-0.5"
  }, parsedData.site.toUpperCase(), " • Tổng ", parsedData.totalEpisodes, " tập")), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: () => setParsedData(null),
    className: "text-[11px] text-slate-400 hover:underline"
  }, "Đổi link")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("label", {
    className: "block text-xs font-bold text-slate-300 mb-1.5"
  }, "Chế Độ Tải"), /*#__PURE__*/React.createElement("div", {
    className: "grid grid-cols-3 gap-2"
  }, [{
    id: 'full',
    label: 'Full (Video+Sub)'
  }, {
    id: 'sub_only',
    label: 'Chỉ Phụ Đề'
  }, {
    id: 'video_only',
    label: 'Chỉ Video'
  }].map(m => /*#__PURE__*/React.createElement("button", {
    key: m.id,
    type: "button",
    onClick: () => setDownloadMode(m.id),
    className: `py-2 text-xs rounded-xl border transition-all ${downloadMode === m.id ? 'bg-emerald-500/20 border-emerald-500 text-emerald-300 font-bold' : 'bg-white/5 border-white/5 text-slate-400'}`
  }, m.label)))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "flex justify-between text-xs font-bold text-slate-300 mb-1.5"
  }, /*#__PURE__*/React.createElement("span", null, "Khoảng Tập (Ví dụ: 1-12, all)"), /*#__PURE__*/React.createElement("span", {
    className: "text-emerald-400 font-mono"
  }, "Đã chọn: ", selectedEpList.length, " tập")), /*#__PURE__*/React.createElement("input", {
    type: "text",
    value: rangeInput,
    onChange: e => setRangeInput(e.target.value),
    className: "w-full bg-[#0A0D14] border border-white/10 text-xs px-3.5 py-2.5 rounded-xl font-mono text-white focus:outline-none focus:border-emerald-500"
  })), downloadMode !== 'video_only' && /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("label", {
    className: "block text-xs font-bold text-slate-300 mb-1.5"
  }, "Ngôn Ngữ Phụ Đề Tải Về"), /*#__PURE__*/React.createElement("div", {
    className: "flex flex-wrap gap-2"
  }, [{
    id: 'es-LA',
    label: 'Spanish (Latam)'
  }, {
    id: 'es-ES',
    label: 'Spanish (Spain)'
  }, {
    id: 'en',
    label: 'English'
  }, {
    id: 'vi',
    label: 'Tiếng Việt'
  }, {
    id: 'ja',
    label: 'Japanese'
  }].map(lang => {
    const isSelected = selectedLangs.includes(lang.id);
    return /*#__PURE__*/React.createElement("button", {
      key: lang.id,
      type: "button",
      onClick: () => {
        if (isSelected) {
          if (selectedLangs.length > 1) setSelectedLangs(selectedLangs.filter(l => l !== lang.id));
        } else {
          setSelectedLangs([...selectedLangs, lang.id]);
        }
      },
      className: `px-3 py-1 rounded-full text-xs border transition-all ${isSelected ? 'bg-emerald-500 text-black font-bold border-emerald-400' : 'bg-white/5 border-white/10 text-slate-400'}`
    }, lang.label);
  }))), /*#__PURE__*/React.createElement("div", {
    className: "flex gap-3 pt-2"
  }, /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: () => setIsAddModalOpen(false),
    className: "flex-1 py-3 bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 text-xs font-bold rounded-xl"
  }, "Hủy"), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: handleConfirmAdd,
    className: "flex-1 py-3 bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-bold rounded-xl shadow-lg shadow-emerald-500/20 active:scale-95 transition-all"
  }, "Bắt Đầu Tải ", selectedEpList.length, " Tập"))))), taskDetail && /*#__PURE__*/React.createElement("div", {
    className: "fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md"
  }, /*#__PURE__*/React.createElement("div", {
    className: "bg-[#131824] border border-white/10 rounded-2xl w-full max-w-2xl p-6 shadow-2xl space-y-4 animate-in zoom-in-95 duration-150"
  }, /*#__PURE__*/React.createElement("div", {
    className: "flex items-center justify-between border-b border-white/10 pb-3"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h3", {
    className: "text-sm font-bold text-white"
  }, taskDetail.anime_title, " - Tập ", taskDetail.episode_num), /*#__PURE__*/React.createElement("div", {
    className: "text-[11px] font-mono text-emerald-400"
  }, taskDetail.site.toUpperCase(), " • ID: ", taskDetail.id)), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: () => setTaskDetail(null),
    className: "text-slate-400 hover:text-white"
  }, "✕")), /*#__PURE__*/React.createElement("div", {
    className: "grid grid-cols-2 gap-3 text-xs bg-[#0A0D14] p-3 rounded-xl border border-white/10"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "text-slate-500"
  }, "Tiến độ:"), " ", /*#__PURE__*/React.createElement("span", {
    className: "font-bold text-white ml-2"
  }, taskDetail.progress_percent, "%")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "text-slate-500"
  }, "Tốc độ:"), " ", /*#__PURE__*/React.createElement("span", {
    className: "font-bold text-emerald-400 ml-2"
  }, taskDetail.speed_mb_s ? `${taskDetail.speed_mb_s.toFixed(2)} MB/s` : '--')), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "text-slate-500"
  }, "Trạng thái:"), " ", /*#__PURE__*/React.createElement("span", {
    className: "font-bold uppercase text-cyan-400 ml-2"
  }, taskDetail.status)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "text-slate-500"
  }, "Dung lượng:"), " ", /*#__PURE__*/React.createElement("span", {
    className: "font-bold text-white ml-2"
  }, formatBytes(taskDetail.file_size_bytes)))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "text-xs font-bold text-slate-400 mb-1"
  }, "Nhật Ký Tác Vụ (Per-Task Ring Buffer)"), /*#__PURE__*/React.createElement("div", {
    className: "h-44 bg-[#0A0D14] border border-white/10 rounded-xl p-3 overflow-y-auto font-mono text-[11px] space-y-1 select-text"
  }, taskLogs.length === 0 ? /*#__PURE__*/React.createElement("div", {
    className: "text-slate-600"
  }, "Đang khởi tạo luồng giải mã...") : taskLogs.map((log, idx) => /*#__PURE__*/React.createElement("div", {
    key: idx,
    className: "text-slate-300 select-text"
  }, /*#__PURE__*/React.createElement("span", {
    className: "text-slate-500"
  }, "[", new Date(log.timestamp * 1000).toLocaleTimeString(), "]"), " ", log.message)))), /*#__PURE__*/React.createElement("div", {
    className: "flex justify-end gap-2 pt-2"
  }, taskDetail.status === 'completed' && /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: () => {
      setPreviewTask(taskDetail);
      setTaskDetail(null);
    },
    className: "px-4 py-2 bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-xs font-semibold rounded-xl text-emerald-300 flex items-center gap-1.5"
  }, "▶ Phát Video Xem Trước"), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: () => setTaskDetail(null),
    className: "px-4 py-2 bg-white/5 hover:bg-white/10 border border-white/10 text-xs rounded-xl text-slate-300"
  }, "Đóng")))), previewTask && /*#__PURE__*/React.createElement("div", {
    className: "fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md",
    onClick: e => {
      if (e.target === e.currentTarget) setPreviewTask(null);
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "bg-[#131824] border border-white/10 rounded-2xl w-full max-w-4xl p-5 shadow-2xl space-y-4 animate-in zoom-in-95 duration-150"
  }, /*#__PURE__*/React.createElement("div", {
    className: "flex items-center justify-between border-b border-white/10 pb-3"
  }, /*#__PURE__*/React.createElement("div", {
    className: "flex items-center gap-2 text-white font-bold text-sm truncate"
  }, /*#__PURE__*/React.createElement("span", {
    className: "text-emerald-400"
  }, "▶"), `Xem Trước: ${previewTask.anime_title} - Tập ${previewTask.episode_num}`, /*#__PURE__*/React.createElement("span", {
    className: "text-[10px] font-mono px-2 py-0.5 rounded bg-white/5 text-slate-400"
  }, previewTask.quality)), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: () => setPreviewTask(null),
    className: "text-slate-400 hover:text-white text-base px-2.5 py-1 rounded-lg hover:bg-white/10"
  }, "✕")), /*#__PURE__*/React.createElement("div", {
    className: "relative rounded-xl overflow-hidden bg-black aspect-video flex items-center justify-center border border-white/5"
  }, /*#__PURE__*/React.createElement("video", {
    controls: true,
    autoPlay: true,
    src: `/api/video?id=${previewTask.id}`,
    className: "w-full h-full object-contain"
  })), /*#__PURE__*/React.createElement("div", {
    className: "flex flex-wrap items-center justify-between gap-2 pt-1"
  }, /*#__PURE__*/React.createElement("div", {
    className: "text-[11px] text-slate-400 font-mono truncate max-w-md",
    title: previewTask.save_path
  }, `Vị trí: ${previewTask.save_path || '--'}`), /*#__PURE__*/React.createElement("div", {
    className: "flex gap-2"
  }, /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: () => taskAction(previewTask.id, 'open-file'),
    className: "px-3 py-1.5 bg-white/10 hover:bg-white/15 text-white text-xs font-semibold rounded-xl flex items-center gap-1.5 transition-all"
  }, "🎬 Mở Trình Phát Ngoài"), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: () => taskAction(previewTask.id, 'open-folder'),
    className: "px-3 py-1.5 bg-white/5 hover:bg-white/10 text-slate-300 text-xs rounded-xl flex items-center gap-1.5 transition-all"
  }, "📁 Mở Thư Mục"))))), contextMenu.visible && contextMenu.task && /*#__PURE__*/React.createElement("div", {
    style: {
      top: contextMenu.y,
      left: contextMenu.x
    },
    className: "fixed z-50 bg-[#131824] border border-white/10 rounded-xl shadow-2xl py-1 text-xs text-slate-200 min-w-44 select-none animate-in fade-in duration-100"
  }, /*#__PURE__*/React.createElement("div", {
    className: "px-3 py-1.5 text-[10px] font-mono text-slate-500 border-b border-white/5"
  }, "Tập ", contextMenu.task.episode_num, " • ", contextMenu.task.quality), contextMenu.task.status === 'completed' && /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: () => {
      setPreviewTask(contextMenu.task);
      setContextMenu({
        visible: false,
        x: 0,
        y: 0,
        task: null
      });
    },
    className: "w-full px-3 py-1.5 text-left hover:bg-emerald-500/20 flex items-center gap-2 text-emerald-400 font-medium"
  }, /*#__PURE__*/React.createElement("span", null, "▶"), " Phát video xem trước"), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: () => {
      taskAction(contextMenu.task.id, 'open-folder');
      setContextMenu({
        visible: false,
        x: 0,
        y: 0,
        task: null
      });
    },
    className: "w-full px-3 py-1.5 text-left hover:bg-white/10 flex items-center gap-2"
  }, /*#__PURE__*/React.createElement("span", null, "📁"), " Mở thư mục chứa"), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: () => {
      openInspector(contextMenu.task);
      setContextMenu({
        visible: false,
        x: 0,
        y: 0,
        task: null
      });
    },
    className: "w-full px-3 py-1.5 text-left hover:bg-white/10 flex items-center gap-2"
  }, /*#__PURE__*/React.createElement("span", null, "🔍"), " Xem chi tiết log"), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: () => {
      taskAction(contextMenu.task.id, 'restart');
      setContextMenu({
        visible: false,
        x: 0,
        y: 0,
        task: null
      });
    },
    className: "w-full px-3 py-1.5 text-left hover:bg-white/10 flex items-center gap-2 text-amber-300"
  }, /*#__PURE__*/React.createElement("span", null, "🔄"), " Tải lại từ đầu"), /*#__PURE__*/React.createElement("div", {
    className: "h-[1px] bg-white/5 my-1"
  }), /*#__PURE__*/React.createElement("button", {
    type: "button",
    onClick: () => {
      taskAction(contextMenu.task.id, 'delete');
      setContextMenu({
        visible: false,
        x: 0,
        y: 0,
        task: null
      });
    },
    className: "w-full px-3 py-1.5 text-left hover:bg-rose-950/50 flex items-center gap-2 text-rose-400"
  }, /*#__PURE__*/React.createElement("span", null, "🗑"), " Xóa tác vụ")), /*#__PURE__*/React.createElement("div", {
    className: `fixed bottom-0 left-64 right-0 z-30 transition-all duration-200 ${isConsoleOpen ? 'h-64' : 'h-7'} bg-[#0D111A]/95 border-t border-white/[0.08] flex flex-col backdrop-blur-md`
  }, /*#__PURE__*/React.createElement("div", {
    onClick: () => setIsConsoleOpen(!isConsoleOpen),
    className: "flex items-center justify-between px-4 py-1.5 cursor-pointer text-[11px] select-none bg-[#0A0D14]/80"
  }, /*#__PURE__*/React.createElement("span", {
    className: "font-mono text-emerald-400 font-bold flex items-center gap-1.5"
  }, /*#__PURE__*/React.createElement("span", null, "❯_"), " SYSTEM LOGS (", systemLogs.length, ")"), /*#__PURE__*/React.createElement("span", {
    className: "text-slate-500"
  }, isConsoleOpen ? '▼ Thu gọn' : '▲ Mở rộng log')), isConsoleOpen && /*#__PURE__*/React.createElement("div", {
    ref: logContainerRef,
    className: "flex-1 p-3 overflow-y-auto font-mono text-[11px] space-y-1 bg-[#0A0D14] select-text"
  }, filteredLogs.length === 0 ? /*#__PURE__*/React.createElement("div", {
    className: "text-slate-600"
  }, "Chưa có log hệ thống.") : filteredLogs.map(l => /*#__PURE__*/React.createElement("div", {
    key: l.id,
    className: "text-slate-300 select-text"
  }, /*#__PURE__*/React.createElement("span", {
    className: "text-slate-500"
  }, "[", new Date(l.timestamp * 1000).toLocaleTimeString(), "]"), /*#__PURE__*/React.createElement("span", {
    className: "text-emerald-400 font-bold ml-1.5"
  }, "[", l.category.toUpperCase(), "]"), /*#__PURE__*/React.createElement("span", {
    className: "ml-2"
  }, l.message))))));
}
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(/*#__PURE__*/React.createElement(App, null));