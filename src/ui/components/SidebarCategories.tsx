import React from 'react';
import { downloadStore } from '../state/useDownloadStore';
import { DownloadCategory, DownloadCounts, TaskStatus } from '../types';

interface SidebarCategoriesProps {
  counts: DownloadCounts;
  selectedCategory: DownloadCategory | TaskStatus | 'all';
}

export const SidebarCategories: React.FC<SidebarCategoriesProps> = ({ counts, selectedCategory }) => {
  const mainItems: Array<{ id: DownloadCategory | TaskStatus | 'all'; label: string; count: number; icon: string; color: string }> = [
    { id: 'all', label: 'Tất Cả Tác Vụ', count: counts.all, icon: '📦', color: 'text-slate-200' },
    { id: 'downloading', label: 'Đang Tải', count: counts.downloading, icon: '⚡', color: 'text-emerald-400' },
    { id: 'queued', label: 'Hàng Đợi', count: counts.queued, icon: '⏳', color: 'text-amber-400' },
    { id: 'completed', label: 'Hoàn Thành', count: counts.completed, icon: '✓', color: 'text-cyan-400' },
    { id: 'paused', label: 'Tạm Dừng', count: counts.paused, icon: '⏸', color: 'text-slate-400' },
    { id: 'failed', label: 'Lỗi / Hỏng', count: counts.failed, icon: '✕', color: 'text-rose-400' },
  ];

  const subItems: Array<{ id: DownloadCategory; label: string; icon: string }> = [
    { id: 'anime', label: 'Anime Series', icon: '🎬' },
    { id: 'video', label: 'Chỉ Video', icon: '📹' },
    { id: 'subtitle', label: 'Chỉ Phụ Đề', icon: '📝' },
  ];

  return (
    <aside className="w-56 shrink-0 bg-[#0E1522]/95 border-r border-white/10 flex flex-col p-3 gap-5 select-none">
      {/* Category Tree */}
      <div className="flex flex-col gap-1">
        <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 px-3 py-1">
          Trạng Thái Tải
        </span>
        {mainItems.map((item) => {
          const isActive = selectedCategory === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => downloadStore.setSelectedCategory(item.id)}
              className={`flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all ${
                isActive
                  ? 'bg-gradient-to-r from-emerald-500/20 to-cyan-500/20 text-white border border-emerald-500/40 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
              }`}
            >
              <div className="flex items-center gap-2">
                <span>{item.icon}</span>
                <span className={item.color}>{item.label}</span>
              </div>
              <span
                className={`text-[11px] font-mono px-1.5 py-0.5 rounded-md ${
                  isActive ? 'bg-emerald-500 text-black font-bold' : 'bg-slate-800 text-slate-400'
                }`}
              >
                {item.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Sub Categories */}
      <div className="flex flex-col gap-1 border-t border-white/5 pt-3">
        <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 px-3 py-1">
          Phân Loại Định Dạng
        </span>
        {subItems.map((item) => {
          const isActive = selectedCategory === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => downloadStore.setSelectedCategory(item.id)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${
                isActive
                  ? 'bg-cyan-950/60 text-cyan-300 border border-cyan-500/40'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
              }`}
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>
    </aside>
  );
};
