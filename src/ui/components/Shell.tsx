import React, { useState, useEffect } from 'react';
import { downloadStore } from '../state/useDownloadStore';
import { DownloadStats } from '../types';

export interface ShellProps {
  readonly children: React.ReactNode;
}

export const Shell: React.FC<ShellProps> = ({ children }) => {
  const [activeTab, setActiveTab] = useState<'download' | 'queue' | 'logs' | 'settings'>('download');
  const [stats, setStats] = useState<DownloadStats>(downloadStore.getStats());

  useEffect(() => {
    // RAII Subscription
    const unsubscribe = downloadStore.subscribe(() => {
      const state = downloadStore.getState();
      setActiveTab(state.activeTab);
      setStats(downloadStore.getStats());
    });

    return () => {
      unsubscribe();
    };
  }, []);

  const formatSpeed = (bytesPerSec: number): string => {
    if (bytesPerSec === 0) return '0.0 MB/s';
    const mb = bytesPerSec / (1024 * 1024);
    return `${mb.toFixed(1)} MB/s`;
  };

  return (
    <div className="min-h-screen bg-[#0B0F17] text-slate-100 flex flex-col antialiased selection:bg-cyan-500/30 selection:text-cyan-200">
      {/* Top Glass Navigation Bar */}
      <header className="sticky top-0 z-30 bg-[#161F30]/80 backdrop-blur-xl border-b border-white/10 px-4 sm:px-8 py-3 flex items-center justify-between shadow-lg">
        {/* Brand Identity */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-emerald-500 to-cyan-500 p-0.5 shadow-lg shadow-emerald-500/25 flex items-center justify-center">
            <div className="w-full h-full bg-[#0B0F17] rounded-[10px] flex items-center justify-center">
              <svg className="w-5 h-5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold tracking-tight bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
                TeamTrau Downloader
              </h1>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-mono font-semibold">
                v2.0+
              </span>
            </div>
            <p className="text-[11px] text-slate-400">High-Performance Anime Batch Pipeline</p>
          </div>
        </div>

        {/* Global Live Stats Widget */}
        <div className="hidden md:flex items-center gap-6 px-4 py-1.5 rounded-xl bg-[#0B0F17]/60 border border-white/5 font-mono text-xs">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-slate-400">Tốc độ:</span>
            <span className="font-semibold text-emerald-400">{formatSpeed(stats.totalDownloadSpeedBytesPerSec)}</span>
          </div>
          <div className="w-px h-4 bg-white/10" />
          <div className="flex items-center gap-2">
            <span className="text-slate-400">Đang tải:</span>
            <span className="font-semibold text-cyan-400">{stats.activeTasks}</span>
          </div>
          <div className="w-px h-4 bg-white/10" />
          <div className="flex items-center gap-2">
            <span className="text-slate-400">Hoàn thành:</span>
            <span className="font-semibold text-slate-300">{stats.completedTasks}/{stats.totalTasks}</span>
          </div>
        </div>

        {/* Quick Nav Actions */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => downloadStore.setTab('download')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeTab === 'download'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
            }`}
          >
            Parser
          </button>
          <button
            type="button"
            onClick={() => downloadStore.setTab('queue')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all relative ${
              activeTab === 'queue'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
            }`}
          >
            Queue
            {stats.activeTasks > 0 && (
              <span className="absolute -top-1 -right-1 w-2 h-2 bg-cyan-400 rounded-full animate-ping" />
            )}
          </button>
          <button
            type="button"
            onClick={() => downloadStore.toggleSettings(true)}
            className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors"
            title="Cài đặt"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </button>
        </div>
      </header>

      {/* Main Content View Container */}
      <main className="flex-1 pb-16">{children}</main>
    </div>
  );
};
