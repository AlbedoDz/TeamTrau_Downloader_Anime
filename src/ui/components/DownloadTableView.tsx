import React, { useState } from 'react';
import { downloadStore } from '../state/useDownloadStore';
import { DownloadTaskRecord } from '../types';

interface ContextMenuState {
  x: number;
  y: number;
  task: DownloadTaskRecord | null;
}

interface DownloadTableViewProps {
  tasks: DownloadTaskRecord[];
}

export const DownloadTableView: React.FC<DownloadTableViewProps> = ({ tasks }) => {
  const [contextMenu, setContextMenu] = useState<ContextMenuState>({ x: 0, y: 0, task: null });

  const handleContextMenu = (e: React.MouseEvent, task: DownloadTaskRecord) => {
    e.preventDefault();
    setContextMenu({
      x: e.clientX,
      y: e.clientY,
      task,
    });
  };

  const closeContextMenu = () => {
    setContextMenu({ x: 0, y: 0, task: null });
  };

  const formatBytes = (bytes: number): string => {
    if (!bytes || bytes <= 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'downloading':
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-emerald-950/70 border border-emerald-500/40 text-emerald-300">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
            Đang Tải
          </span>
        );
      case 'queued':
        return (
          <span className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-amber-950/70 border border-amber-500/40 text-amber-300">
            Hàng Đợi
          </span>
        );
      case 'completed':
        return (
          <span className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-cyan-950/70 border border-cyan-500/40 text-cyan-300">
            Hoàn Thành
          </span>
        );
      case 'paused':
        return (
          <span className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-slate-800 border border-slate-600 text-slate-400">
            Tạm Dừng
          </span>
        );
      case 'failed':
        return (
          <span className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-rose-950/70 border border-rose-500/40 text-rose-300">
            Lỗi
          </span>
        );
      default:
        return <span className="text-slate-400 text-xs">{status}</span>;
    }
  };

  return (
    <div className="flex-1 overflow-x-auto flex flex-col bg-[#0B0F17]" onClick={closeContextMenu}>
      {tasks.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center p-12 text-slate-500 gap-3 select-none">
          <svg className="w-16 h-16 text-slate-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          <span className="text-sm font-medium">Danh sách tác vụ tải trống</span>
          <span className="text-xs text-slate-600">Bấm "+ Thêm URL" trên thanh công cụ để bắt đầu tải anime</span>
        </div>
      ) : (
        <table className="w-full text-left border-collapse select-none">
          <thead>
            <tr className="border-b border-white/10 bg-[#131C2D]/80 text-[11px] font-bold uppercase tracking-wider text-slate-400">
              <th className="py-2.5 px-4">Tên Tác Vụ / Anime</th>
              <th className="py-2.5 px-3">Dung Lượng</th>
              <th className="py-2.5 px-3 w-48">Tiến Độ</th>
              <th className="py-2.5 px-3">Trạng Thái</th>
              <th className="py-2.5 px-3">Tốc Độ</th>
              <th className="py-2.5 px-3">Còn Lại</th>
              <th className="py-2.5 px-3 text-right">Thao Tác</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5 text-xs text-slate-200 font-mono">
            {tasks.map((task) => (
              <tr
                key={task.id}
                onContextMenu={(e) => handleContextMenu(e, task)}
                onDoubleClick={() => downloadStore.openTaskDetail(task.id)}
                className="hover:bg-white/[0.03] transition-colors cursor-pointer group"
              >
                {/* Title and details */}
                <td className="py-3 px-4 font-sans">
                  <div className="flex items-center gap-2.5">
                    <span className="text-base">{task.download_mode === 'sub_only' ? '📝' : '🎬'}</span>
                    <div>
                      <div className="font-semibold text-slate-100 group-hover:text-cyan-300 transition-colors">
                        {task.anime_title} - Tập {task.episode_num}
                      </div>
                      <div className="text-[11px] text-slate-400 font-mono flex items-center gap-2">
                        <span>{task.site.toUpperCase()}</span>
                        <span>•</span>
                        <span>{task.quality}</span>
                        <span>•</span>
                        <span className="text-emerald-400 font-semibold">{task.download_mode.toUpperCase()}</span>
                      </div>
                    </div>
                  </div>
                </td>

                {/* Size */}
                <td className="py-3 px-3 text-slate-400">
                  {task.file_size_bytes > 0 ? formatBytes(task.file_size_bytes) : '--'}
                </td>

                {/* Progress bar */}
                <td className="py-3 px-3">
                  <div className="flex flex-col gap-1">
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-slate-300 font-bold">{task.progress_percent}%</span>
                      {task.total_segments > 0 && (
                        <span className="text-slate-500 text-[10px]">
                          {task.downloaded_segments}/{task.total_segments} segs
                        </span>
                      )}
                    </div>
                    <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
                      <div
                        className={`h-full transition-all duration-300 rounded-full ${
                          task.status === 'downloading'
                            ? 'bg-gradient-to-r from-emerald-500 via-cyan-400 to-emerald-400 pulse-gradient-bar'
                            : task.status === 'completed'
                            ? 'bg-cyan-500'
                            : task.status === 'failed'
                            ? 'bg-rose-500'
                            : 'bg-slate-600'
                        }`}
                        style={{ width: `${task.progress_percent}%` }}
                      />
                    </div>
                  </div>
                </td>

                {/* Status */}
                <td className="py-3 px-3">{getStatusBadge(task.status)}</td>

                {/* Speed */}
                <td className="py-3 px-3 text-emerald-400 font-semibold">
                  {task.status === 'downloading' && task.speed_bytes_per_sec > 0
                    ? `${formatBytes(task.speed_bytes_per_sec)}/s`
                    : '--'}
                </td>

                {/* ETA */}
                <td className="py-3 px-3 text-slate-400">
                  {task.status === 'downloading' && task.eta_seconds > 0 ? `${task.eta_seconds}s` : '--'}
                </td>

                {/* Quick actions */}
                <td className="py-3 px-3 text-right">
                  <div className="flex items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
                    {task.status === 'downloading' ? (
                      <button
                        type="button"
                        onClick={() => downloadStore.pauseTask(task.id)}
                        className="p-1 text-slate-400 hover:text-amber-400 hover:bg-white/5 rounded"
                        title="Tạm dừng"
                      >
                        ⏸
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => downloadStore.resumeTask(task.id)}
                        className="p-1 text-slate-400 hover:text-emerald-400 hover:bg-white/5 rounded"
                        title="Tiếp tục"
                      >
                        ▶
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => downloadStore.openTaskDetail(task.id)}
                      className="p-1 text-slate-400 hover:text-cyan-400 hover:bg-white/5 rounded"
                      title="Chi tiết & Logs"
                    >
                      📜
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Right-click Context Menu */}
      {contextMenu.task && (
        <div
          className="fixed z-50 w-52 bg-[#161F30] border border-white/10 rounded-xl shadow-2xl py-1.5 text-xs text-slate-200 animate-in fade-in zoom-in-95 duration-100"
          style={{ top: `${contextMenu.y}px`, left: `${contextMenu.x}px` }}
          onClick={(e) => e.stopPropagation()}
        >
          {contextMenu.task.status === 'completed' && (
            <button
              type="button"
              onClick={() => {
                downloadStore.openFile(contextMenu.task!.id);
                closeContextMenu();
              }}
              className="w-full text-left px-3.5 py-1.5 hover:bg-white/10 flex items-center gap-2"
            >
              <span>🎬</span> Mở File Video
            </button>
          )}

          <button
            type="button"
            onClick={() => {
              downloadStore.openFolder(contextMenu.task!.id);
              closeContextMenu();
            }}
            className="w-full text-left px-3.5 py-1.5 hover:bg-white/10 flex items-center gap-2"
          >
            <span>📁</span> Mở Thư Mục Chứa
          </button>

          <div className="border-t border-white/5 my-1" />

          {contextMenu.task.status === 'downloading' ? (
            <button
              type="button"
              onClick={() => {
                downloadStore.pauseTask(contextMenu.task!.id);
                closeContextMenu();
              }}
              className="w-full text-left px-3.5 py-1.5 hover:bg-white/10 flex items-center gap-2 text-amber-300"
            >
              <span>⏸</span> Tạm Dừng
            </button>
          ) : (
            <button
              type="button"
              onClick={() => {
                downloadStore.resumeTask(contextMenu.task!.id);
                closeContextMenu();
              }}
              className="w-full text-left px-3.5 py-1.5 hover:bg-white/10 flex items-center gap-2 text-emerald-300"
            >
              <span>▶</span> Tiếp Tục Tải
            </button>
          )}

          <button
            type="button"
            onClick={() => {
              downloadStore.restartTask(contextMenu.task!.id);
              closeContextMenu();
            }}
            className="w-full text-left px-3.5 py-1.5 hover:bg-white/10 flex items-center gap-2 text-cyan-300"
          >
            <span>🔄</span> Tải Lại Từ Đầu
          </button>

          <button
            type="button"
            onClick={() => {
              downloadStore.openTaskDetail(contextMenu.task!.id);
              closeContextMenu();
            }}
            className="w-full text-left px-3.5 py-1.5 hover:bg-white/10 flex items-center gap-2"
          >
            <span>📜</span> Xem Chi Tiết & Logs
          </button>

          <button
            type="button"
            onClick={() => {
              if (navigator.clipboard) {
                navigator.clipboard.writeText(contextMenu.task!.url);
              }
              closeContextMenu();
            }}
            className="w-full text-left px-3.5 py-1.5 hover:bg-white/10 flex items-center gap-2 text-slate-400"
          >
            <span>🔗</span> Sao Chép URL Gốc
          </button>

          <div className="border-t border-white/5 my-1" />

          <button
            type="button"
            onClick={() => {
              downloadStore.deleteTask(contextMenu.task!.id, false);
              closeContextMenu();
            }}
            className="w-full text-left px-3.5 py-1.5 hover:bg-rose-950/40 text-rose-300 flex items-center gap-2"
          >
            <span>🗑</span> Xóa Khỏi Danh Sách
          </button>

          <button
            type="button"
            onClick={() => {
              downloadStore.deleteTask(contextMenu.task!.id, true);
              closeContextMenu();
            }}
            className="w-full text-left px-3.5 py-1.5 hover:bg-rose-950/60 text-rose-400 font-semibold flex items-center gap-2"
          >
            <span>⚠️</span> Xóa Cả File Trên Ổ Đĩa
          </button>
        </div>
      )}
    </div>
  );
};
