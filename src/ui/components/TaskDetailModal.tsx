import React from 'react';
import { downloadStore } from '../state/useDownloadStore';
import { DownloadTaskRecord, TaskLogEntry } from '../types';

interface TaskDetailModalProps {
  task: DownloadTaskRecord | null;
  logs: TaskLogEntry[];
  onClose: () => void;
}

export const TaskDetailModal: React.FC<TaskDetailModalProps> = ({ task, logs, onClose }) => {
  if (!task) return null;

  const handleCopyLogs = () => {
    const text = logs
      .map(
        (l) =>
          `[${new Date(l.timestamp * 1000).toLocaleTimeString()}] [${l.level}] [${l.category.toUpperCase()}] ${l.message}`
      )
      .join('\n');
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text);
      alert('Đã sao chép toàn bộ logs của tác vụ vào clipboard!');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#05080E]/80 backdrop-blur-md">
      <div className="relative w-full max-w-3xl bg-[#161F30] border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh] animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-[#131C2D]/80">
          <div>
            <span className="text-[11px] uppercase tracking-wider font-semibold text-cyan-400 font-mono">
              Task Inspector & Per-Task Log
            </span>
            <h2 className="text-base font-bold text-slate-100">
              {task.anime_title} - Tập {task.episode_num}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-white/5 transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Task Metadata Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-5 bg-[#0E1522]/80 border-b border-white/5 text-xs font-mono">
          <div>
            <span className="text-slate-500 block text-[10px]">TRẠNG THÁI</span>
            <span className="font-bold text-emerald-400 uppercase">{task.status}</span>
          </div>
          <div>
            <span className="text-slate-500 block text-[10px]">SITE NGUỒN</span>
            <span className="text-slate-200 uppercase">{task.site}</span>
          </div>
          <div>
            <span className="text-slate-500 block text-[10px]">CHẾ ĐỘ TẢI</span>
            <span className="text-cyan-300 uppercase">{task.download_mode}</span>
          </div>
          <div>
            <span className="text-slate-500 block text-[10px]">TIẾN ĐỘ</span>
            <span className="text-amber-300 font-bold">{task.progress_percent}%</span>
          </div>
          <div className="col-span-2 sm:col-span-4">
            <span className="text-slate-500 block text-[10px]">ĐƯỜNG DẪN LƯU</span>
            <span className="text-slate-300 truncate block">{task.save_path || '--'}</span>
          </div>
        </div>

        {/* Per-Task Live Logs */}
        <div className="flex-1 flex flex-col p-5 overflow-hidden gap-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
              Nhật Ký Tác Vụ ({logs.length} entries)
            </span>
            <button
              type="button"
              onClick={handleCopyLogs}
              className="px-2.5 py-1 text-[11px] rounded bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30 border border-cyan-500/40 transition-all flex items-center gap-1 font-mono"
            >
              📋 Sao Chép Logs Tác Vụ
            </button>
          </div>

          <div className="flex-1 overflow-y-auto bg-[#070A10] border border-white/5 rounded-xl p-3 font-mono text-[11px] space-y-1 select-text">
            {logs.length === 0 ? (
              <div className="text-slate-600">Chưa có nhật ký cho tác vụ này.</div>
            ) : (
              logs.map((l) => (
                <div key={l.id} className="flex items-start gap-2 hover:bg-white/[0.03] px-1.5 py-0.5 rounded">
                  <span className="text-slate-500 shrink-0">
                    [{new Date(l.timestamp * 1000).toLocaleTimeString()}]
                  </span>
                  <span
                    className={`font-semibold shrink-0 uppercase ${
                      l.level === 'ERROR'
                        ? 'text-rose-400'
                        : l.level === 'WARN'
                        ? 'text-amber-400'
                        : l.level === 'SUCCESS'
                        ? 'text-emerald-400'
                        : 'text-cyan-400'
                    }`}
                  >
                    [{l.level}]
                  </span>
                  <span className="text-slate-300 break-all">{l.message}</span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-3 border-t border-white/10 bg-[#131C2D]/80">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => downloadStore.openFolder(task.id)}
              className="px-3 py-1.5 text-xs text-slate-300 hover:text-white bg-[#161F30] hover:bg-white/10 border border-white/10 rounded-lg transition-all"
            >
              📁 Mở Thư Mục
            </button>
            {task.status === 'completed' && (
              <button
                type="button"
                onClick={() => downloadStore.openFile(task.id)}
                className="px-3 py-1.5 text-xs text-emerald-300 hover:text-emerald-200 bg-emerald-950/40 border border-emerald-500/40 rounded-lg transition-all"
              >
                🎬 Mở Video
              </button>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 text-xs font-semibold text-white bg-slate-800 hover:bg-slate-700 rounded-lg transition-all"
          >
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
};
