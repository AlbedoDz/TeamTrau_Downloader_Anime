import React, { useState, useEffect } from 'react';
import { downloadStore } from '../state/useDownloadStore';
import { SettingsConfig } from '../types';

export const SettingsDrawer: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [settings, setSettings] = useState<SettingsConfig>(downloadStore.getState().settings);

  useEffect(() => {
    // RAII Subscription
    const unsubscribe = downloadStore.subscribe(() => {
      const state = downloadStore.getState();
      setIsOpen(state.isSettingsOpen);
      setSettings(state.settings);
    });

    return () => {
      unsubscribe();
    };
  }, []);

  if (!isOpen) return null;

  const handleChange = <K extends keyof SettingsConfig>(key: K, value: SettingsConfig[K]) => {
    const updated = { ...settings, [key]: value };
    setSettings(updated);
    downloadStore.updateSettings({ [key]: value });
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-[#05080E]/70 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="w-full max-w-md bg-[#161F30] border-l border-white/10 shadow-2xl h-full flex flex-col justify-between overflow-y-auto animate-in slide-in-from-right duration-300">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-white/10 bg-[#131C2D]">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-100">Cấu Hình Hệ Thống</h2>
              <p className="text-xs text-slate-400">Settings & Download Engine</p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => downloadStore.toggleSettings(false)}
            className="text-slate-400 hover:text-slate-200 p-1.5 rounded-lg hover:bg-white/5 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Settings Body */}
        <div className="p-6 flex flex-col gap-6 flex-1">
          {/* Output Directory */}
          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Thư mục lưu trữ / Output Directory
            </label>
            <input
              type="text"
              value={settings.outputDir}
              onChange={(e) => handleChange('outputDir', e.target.value)}
              className="bg-[#0B0F17] text-slate-200 text-sm px-3.5 py-2.5 rounded-xl border border-white/10 focus:border-cyan-400 focus:outline-none"
            />
          </div>

          {/* Concurrent Workers Slider */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                Số Luồng Tải Song Song (Workers)
              </label>
              <span className="text-xs font-mono text-cyan-400 font-bold">{settings.maxConcurrentWorkers} Threads</span>
            </div>
            <input
              type="range"
              min="1"
              max="16"
              value={settings.maxConcurrentWorkers}
              onChange={(e) => handleChange('maxConcurrentWorkers', parseInt(e.target.value, 10))}
              className="w-full accent-cyan-400 cursor-pointer"
            />
            <div className="flex justify-between text-[11px] text-slate-500 font-mono">
              <span>1 (Safe)</span>
              <span>8 (Standard)</span>
              <span>16 (Max Boost)</span>
            </div>
          </div>

          {/* Proxy URL */}
          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Proxy Switcher (HTTP / SOCKS5)
            </label>
            <input
              type="text"
              value={settings.proxyUrl}
              onChange={(e) => handleChange('proxyUrl', e.target.value)}
              placeholder="e.g. http://127.0.0.1:7890 (Tùy chọn)"
              className="bg-[#0B0F17] text-slate-200 text-sm px-3.5 py-2.5 rounded-xl border border-white/10 focus:border-cyan-400 focus:outline-none"
            />
          </div>

          {/* User Agent */}
          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              User-Agent Header
            </label>
            <textarea
              rows={2}
              value={settings.userAgent}
              onChange={(e) => handleChange('userAgent', e.target.value)}
              className="bg-[#0B0F17] text-slate-300 text-xs px-3 py-2 rounded-xl border border-white/10 focus:border-cyan-400 focus:outline-none font-mono resize-none"
            />
          </div>

          {/* Switches */}
          <div className="flex flex-col gap-3 pt-4 border-t border-white/10">
            <label className="flex items-center justify-between cursor-pointer">
              <span className="text-xs text-slate-200 font-medium">Tự động Muxing phụ đề vào file MP4</span>
              <input
                type="checkbox"
                checked={settings.autoMuxSubtitles}
                onChange={(e) => handleChange('autoMuxSubtitles', e.target.checked)}
                className="w-4 h-4 rounded border-slate-700 bg-slate-900 text-emerald-500 focus:ring-emerald-400"
              />
            </label>

            <label className="flex items-center justify-between cursor-pointer">
              <span className="text-xs text-slate-200 font-medium">Bỏ qua file đã tải xong (Skip existing)</span>
              <input
                type="checkbox"
                checked={settings.skipExisting}
                onChange={(e) => handleChange('skipExisting', e.target.checked)}
                className="w-4 h-4 rounded border-slate-700 bg-slate-900 text-emerald-500 focus:ring-emerald-400"
              />
            </label>

            <label className="flex items-center justify-between cursor-pointer">
              <span className="text-xs text-slate-200 font-medium">Thông báo hoàn tất (System Notifications)</span>
              <input
                type="checkbox"
                checked={settings.notificationsEnabled}
                onChange={(e) => handleChange('notificationsEnabled', e.target.checked)}
                className="w-4 h-4 rounded border-slate-700 bg-slate-900 text-cyan-500 focus:ring-cyan-400"
              />
            </label>
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-white/10 bg-[#131C2D]">
          <button
            type="button"
            onClick={() => downloadStore.toggleSettings(false)}
            className="w-full py-2.5 text-xs font-semibold text-white bg-gradient-to-r from-emerald-500 to-cyan-500 hover:from-emerald-400 hover:to-cyan-400 rounded-xl transition-all shadow-md shadow-cyan-500/20 active:scale-98"
          >
            Lưu & Đóng
          </button>
        </div>
      </div>
    </div>
  );
};
