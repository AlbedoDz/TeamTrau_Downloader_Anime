import React, { useState, useEffect } from 'react';
import { downloadStore } from '../state/useDownloadStore';
import { DownloadItem, TaskStatus } from '../types';

export const DownloadQueue: React.FC = () => {
  const [items, setItems] = useState<readonly DownloadItem[]>([]);
  const [filterStatus, setFilterStatus] = useState<TaskStatus | 'all'>('all');

  useEffect(() => {
    // RAII Subscription
    const unsubscribe = downloadStore.subscribe(() => {
      setItems(downloadStore.getState().downloadItems);
    });

    return () => {
      unsubscribe();
    };
  }, []);

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
  };

  const formatEta = (seconds: number): string => {
    if (seconds <= 0 || !isFinite(seconds)) return '--';
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}m ${s}s`;
  };

  const filteredItems = items.filter((item) => {
    if (filterStatus === 'all') return true;
    return item.status === filterStatus;
  });

  const getStatusBadge = (status: TaskStatus) => {
    switch (status) {
      case 'downloading':
        return { bg: 'bg-cyan-950/80 border-cyan-500/30', text: 'text-cyan-400', label: 'Downloading' };
      case 'completed':
        return { bg: 'bg-emerald-950/80 border-emerald-500/30', text: 'text-emerald-400', label: 'Completed' };
      case 'paused':
        return { bg: 'bg-amber-950/80 border-amber-500/30', text: 'text-amber-400', label: 'Paused' };
      case 'failed':
        return { bg: 'bg-rose-950/80 border-rose-500/30', text: 'text-rose-400', label: 'Failed' };
      default:
        return { bg: 'bg-slate-900 border-slate-700', text: 'text-slate-400', label: 'Queued' };
    }
  };

  return (
    <div className="w-full max-w-5xl mx-auto my-4 px-4 flex flex-col gap-4">
      {/* Header & Filter Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-white/10">
        <div>
          <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
            <span>Tiến Trình Tải Đa Luồng (Active Task Queue)</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">
              {items.length} tác vụ
            </span>
          </h2>
        </div>

        <div className="flex items-center gap-1.5">
          {(['all', 'downloading', 'completed', 'paused', 'failed'] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setFilterStatus(tab)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-all ${
                filterStatus === tab
                  ? 'bg-cyan-500/15 border border-cyan-500/40 text-cyan-300'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {/* Empty State */}
      {filteredItems.length === 0 && (
        <div className="p-12 text-center rounded-2xl bg-[#161F30]/40 border border-white/5 flex flex-col items-center justify-center gap-3">
          <div className="w-12 h-12 rounded-full bg-slate-800/80 flex items-center justify-center text-slate-400">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </div>
          <p className="text-sm text-slate-400">Chưa có tác vụ tải nào trong hàng đợi.</p>
          <span className="text-xs text-slate-500">Dán link anime ở trên và nhấn 1-Click Parse để bắt đầu.</span>
        </div>
      )}

      {/* Task Card List */}
      <div className="flex flex-col gap-3">
        {filteredItems.map((item) => {
          const badge = getStatusBadge(item.status);
          const isDownloading = item.status === 'downloading';

          return (
            <div
              key={item.id}
              className="p-4 rounded-xl bg-[#161F30]/75 backdrop-blur-md border border-white/10 hover:border-cyan-500/30 transition-all duration-200 shadow-md flex flex-col gap-3"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-2.5">
                  <span className="text-sm font-bold text-slate-100">{item.animeTitle}</span>
                  <span className="text-xs font-mono px-2 py-0.5 rounded bg-[#0B0F17] text-cyan-400 border border-white/5">
                    Tập {item.episodeNum}
                  </span>
                  <span className="text-xs font-mono text-slate-400">{item.quality}</span>
                </div>

                <div className="flex items-center gap-2">
                  <span className={`text-[11px] px-2.5 py-0.5 rounded-full border font-medium ${badge.bg} ${badge.text}`}>
                    {badge.label}
                  </span>

                  {/* Actions */}
                  <div className="flex items-center gap-1">
                    {isDownloading ? (
                      <button
                        type="button"
                        onClick={() => downloadStore.pauseTask(item.id)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-amber-400 hover:bg-amber-500/10 transition-colors"
                        title="Tạm dừng"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6" />
                        </svg>
                      </button>
                    ) : item.status === 'paused' ? (
                      <button
                        type="button"
                        onClick={() => downloadStore.resumeTask(item.id)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-cyan-400 hover:bg-cyan-500/10 transition-colors"
                        title="Tiếp tục"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                        </svg>
                      </button>
                    ) : null}

                    {item.status === 'failed' && (
                      <button
                        type="button"
                        onClick={() => downloadStore.retryTask(item.id)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-emerald-400 hover:bg-emerald-500/10 transition-colors"
                        title="Thử lại"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                      </button>
                    )}

                    <button
                      type="button"
                      onClick={() => downloadStore.cancelTask(item.id)}
                      className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                      title="Hủy / Xóa"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>

              {/* Progress bar container */}
              <div className="w-full bg-[#0B0F17] rounded-full h-2 overflow-hidden border border-white/5">
                <div
                  className={`h-full transition-all duration-300 ${
                    item.status === 'completed'
                      ? 'bg-emerald-500'
                      : item.status === 'failed'
                      ? 'bg-rose-500'
                      : isDownloading
                      ? 'pulse-gradient-bar bg-gradient-to-r from-emerald-500 via-cyan-500 to-emerald-500'
                      : 'bg-slate-600'
                  }`}
                  style={{ width: `${item.progressPercentage}%` }}
                />
              </div>

              {/* Subtitle & metrics row */}
              <div className="flex flex-wrap items-center justify-between text-xs text-slate-400 font-mono gap-2">
                <div className="flex items-center gap-3">
                  <span>
                    {formatBytes(item.downloadedBytes)} / {formatBytes(item.totalBytes)} ({item.progressPercentage}%)
                  </span>
                  {item.targetSubLangs.length > 0 && (
                    <span className="text-[11px] text-slate-500">
                      Sub: [{item.targetSubLangs.join(', ')}]
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-4">
                  {isDownloading && (
                    <>
                      <span className="text-cyan-400 font-semibold">{formatBytes(item.speedBytesPerSec)}/s</span>
                      <span>ETA: {formatEta(item.etaSeconds)}</span>
                      <span className="text-slate-500">({item.currentWorkerCount} luồng)</span>
                    </>
                  )}
                  {item.status === 'completed' && <span className="text-emerald-400">Tải & Muxing Xong</span>}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
