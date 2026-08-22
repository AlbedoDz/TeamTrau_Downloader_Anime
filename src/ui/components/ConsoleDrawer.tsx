import React, { useState, useEffect, useRef } from 'react';
import { downloadStore } from '../state/useDownloadStore';
import { LogCategory, LogEntry, LogLevel } from '../types';

export const ConsoleDrawer: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [logs, setLogs] = useState<readonly LogEntry[]>([]);
  const [categoryFilter, setCategoryFilter] = useState<LogCategory | 'all'>('all');
  const [levelFilter, setLevelFilter] = useState<LogLevel | 'all'>('all');
  const logsEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    // RAII Subscription
    const unsubscribe = downloadStore.subscribe(() => {
      const state = downloadStore.getState();
      setIsOpen(state.isConsoleOpen);
      setLogs(state.logs);
      setCategoryFilter(state.logFilterCategory);
      setLevelFilter(state.logFilterLevel);
    });

    return () => {
      unsubscribe();
    };
  }, []);

  useEffect(() => {
    if (isOpen && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, isOpen]);

  const filteredLogs = logs.filter((log) => {
    if (categoryFilter !== 'all' && log.category !== categoryFilter) return false;
    if (levelFilter !== 'all' && log.level !== levelFilter) return false;
    return true;
  });

  const handleCopyLogs = () => {
    const text = filteredLogs
      .map((l) => `[${new Date(l.timestamp).toISOString()}] [${l.level.toUpperCase()}] [${l.category}] ${l.message}`)
      .join('\n');
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(text);
      downloadStore.addLog('info', 'general', 'Đã sao chép nhật ký hệ thống vào clipboard.');
    }
  };

  const getLevelColor = (level: LogLevel) => {
    switch (level) {
      case 'error':
        return 'text-rose-400 font-semibold';
      case 'warn':
        return 'text-amber-400 font-semibold';
      case 'success':
        return 'text-emerald-400 font-semibold';
      case 'debug':
        return 'text-slate-500';
      default:
        return 'text-slate-300';
    }
  };

  const getCategoryBadge = (cat: LogCategory) => {
    switch (cat) {
      case 'm3u8_stream':
        return 'text-cyan-400 bg-cyan-950/60 border-cyan-800/40';
      case 'vrf_decrypt':
        return 'text-purple-400 bg-purple-950/60 border-purple-800/40';
      case 'waf_bypass':
        return 'text-amber-400 bg-amber-950/60 border-amber-800/40';
      case 'subtitle':
        return 'text-emerald-400 bg-emerald-950/60 border-emerald-800/40';
      case 'ffmpeg':
        return 'text-indigo-400 bg-indigo-950/60 border-indigo-800/40';
      default:
        return 'text-slate-400 bg-slate-800/60 border-slate-700/40';
    }
  };

  return (
    <div
      className={`fixed bottom-0 left-0 right-0 z-40 transition-all duration-300 ${
        isOpen ? 'h-80' : 'h-10'
      } bg-[#0B0F17]/95 backdrop-blur-xl border-t border-white/10 shadow-2xl flex flex-col`}
    >
      {/* Drawer Bar Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-[#161F30] border-b border-white/5 cursor-pointer select-none">
        <div
          onClick={() => downloadStore.toggleConsole()}
          className="flex items-center gap-3 text-xs font-semibold text-slate-300 hover:text-white"
        >
          <div className="flex items-center gap-1.5 font-mono text-cyan-400">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3" />
            </svg>
            <span>CONSOLE LOGS</span>
          </div>
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-[#0B0F17] text-slate-400 border border-white/5 font-mono">
            {filteredLogs.length} entries
          </span>
        </div>

        <div className="flex items-center gap-2">
          {isOpen && (
            <>
              {/* Category Filter */}
              <select
                value={categoryFilter}
                onChange={(e) => downloadStore.setLogFilters(e.target.value as LogCategory | 'all', levelFilter)}
                className="bg-[#0B0F17] text-slate-300 text-[11px] px-2 py-1 rounded border border-white/10 outline-none"
              >
                <option value="all">Tất Cả Module</option>
                <option value="m3u8_stream">M3U8 Stream</option>
                <option value="vrf_decrypt">VRF Decrypt</option>
                <option value="waf_bypass">WAF Bypass</option>
                <option value="subtitle">Subtitles</option>
                <option value="ffmpeg">FFmpeg Remux</option>
              </select>

              {/* Copy & Clear */}
              <button
                type="button"
                onClick={handleCopyLogs}
                className="text-[11px] px-2.5 py-1 text-slate-300 hover:text-white bg-white/5 hover:bg-white/10 rounded transition-colors"
              >
                Sao Chép
              </button>
              <button
                type="button"
                onClick={() => downloadStore.clearLogs()}
                className="text-[11px] px-2.5 py-1 text-rose-400 hover:text-rose-300 bg-rose-950/30 hover:bg-rose-950/60 rounded transition-colors"
              >
                Xóa Log
              </button>
            </>
          )}

          <button
            type="button"
            onClick={() => downloadStore.toggleConsole()}
            className="text-slate-400 hover:text-white p-1"
          >
            <svg
              className={`w-4 h-4 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
            </svg>
          </button>
        </div>
      </div>

      {/* Log Console Content */}
      {isOpen && (
        <div className="flex-1 p-3 overflow-y-auto font-mono text-xs space-y-1.5 select-text bg-[#070A10]">
          {filteredLogs.length === 0 ? (
            <div className="text-slate-600 text-center py-6">Không có log nào phù hợp với bộ lọc hiện hành.</div>
          ) : (
            filteredLogs.map((log) => (
              <div key={log.id} className="flex items-start gap-2 leading-relaxed hover:bg-white/[0.02] px-2 py-0.5 rounded">
                <span className="text-slate-500 shrink-0 text-[11px]">
                  {new Date(log.timestamp).toLocaleTimeString()}
                </span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded border uppercase tracking-wider ${getCategoryBadge(log.category)}`}>
                  {log.category}
                </span>
                <span className={`shrink-0 uppercase text-[11px] ${getLevelColor(log.level)}`}>
                  [{log.level}]
                </span>
                <span className="text-slate-300 break-all">{log.message}</span>
              </div>
            ))
          )}
          <div ref={logsEndRef} />
        </div>
      )}
    </div>
  );
};
