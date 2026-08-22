import React from 'react';
import { downloadStore } from '../state/useDownloadStore';

interface ManagerToolbarProps {
  onOpenAddModal: () => void;
  onOpenSettings: () => void;
}

export const ManagerToolbar: React.FC<ManagerToolbarProps> = ({ onOpenAddModal, onOpenSettings }) => {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-3 bg-[#131C2D]/90 border-b border-white/10 backdrop-blur-md">
      {/* Action Buttons */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onOpenAddModal}
          className="flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold text-white bg-gradient-to-r from-emerald-500 to-cyan-500 hover:from-emerald-400 hover:to-cyan-400 rounded-lg shadow-md shadow-emerald-500/20 active:scale-95 transition-all"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          <span>Thêm URL</span>
        </button>

        <button
          type="button"
          onClick={() => downloadStore.resumeAll()}
          className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-slate-200 bg-[#161F30] hover:bg-white/10 border border-white/10 rounded-lg transition-all"
          title="Tiếp tục tất cả"
        >
          <svg className="w-3.5 h-3.5 text-emerald-400" fill="currentColor" viewBox="0 0 24 24">
            <path d="M8 5v14l11-7z" />
          </svg>
          <span className="hidden sm:inline">Tiếp Tục Tất Cả</span>
        </button>

        <button
          type="button"
          onClick={() => downloadStore.pauseAll()}
          className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-slate-200 bg-[#161F30] hover:bg-white/10 border border-white/10 rounded-lg transition-all"
          title="Tạm dừng tất cả"
        >
          <svg className="w-3.5 h-3.5 text-amber-400" fill="currentColor" viewBox="0 0 24 24">
            <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
          </svg>
          <span className="hidden sm:inline">Tạm Dừng</span>
        </button>

        <button
          type="button"
          onClick={() => downloadStore.clearCompleted()}
          className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-slate-300 bg-[#161F30] hover:bg-white/10 border border-white/10 rounded-lg transition-all"
          title="Dọn dẹp tác vụ hoàn thành"
        >
          <svg className="w-3.5 h-3.5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          <span className="hidden md:inline">Dọn Đã Xong</span>
        </button>
      </div>

      {/* Right controls: Search & Settings */}
      <div className="flex items-center gap-3">
        <div className="relative">
          <input
            type="text"
            placeholder="Tìm kiếm tác vụ..."
            onChange={(e) => downloadStore.setSearchQuery(e.target.value)}
            className="w-44 sm:w-60 bg-[#0B0F17] text-slate-200 text-xs pl-8 pr-3 py-1.5 rounded-lg border border-white/10 focus:border-cyan-400 focus:outline-none"
          />
          <svg className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>

        <button
          type="button"
          onClick={onOpenSettings}
          className="p-1.5 text-slate-300 hover:text-white bg-[#161F30] hover:bg-white/10 border border-white/10 rounded-lg transition-all"
          title="Cài đặt hệ thống"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </button>
      </div>
    </div>
  );
};
