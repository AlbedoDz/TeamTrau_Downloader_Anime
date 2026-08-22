import React, { useState, useEffect } from 'react';
import { downloadStore } from '../state/useDownloadStore';
import {
  DownloadMode,
  NamingFormat,
  ParsedAnimeDetails,
  StreamQuality,
  SubtitleLanguageCode,
} from '../types';

export const BatchOptionsModal: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [parsed, setParsed] = useState<ParsedAnimeDetails | null>(null);
  const [rangeInput, setRangeInput] = useState('all');
  const [selectedQuality, setSelectedQuality] = useState<StreamQuality>('1080p');
  const [downloadMode, setDownloadMode] = useState<DownloadMode>('full');
  const [selectedLangs, setSelectedLangs] = useState<SubtitleLanguageCode[]>(['es-LA', 'en']);
  const [namingFormat, setNamingFormat] = useState<NamingFormat>('simple');
  const [tvdbId, setTvdbId] = useState('');
  const [serverPriority, setServerPriority] = useState('');
  const [excludeServers, setExcludeServers] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    // RAII Subscription
    const unsubscribe = downloadStore.subscribe(() => {
      const state = downloadStore.getState();
      setIsOpen(state.isBatchModalOpen);
      setParsed(state.parsedDetails);
    });

    return () => {
      unsubscribe();
    };
  }, []);

  if (!isOpen || !parsed) return null;

  const handleToggleLang = (lang: SubtitleLanguageCode) => {
    if (selectedLangs.includes(lang)) {
      setSelectedLangs(selectedLangs.filter((l) => l !== lang));
    } else {
      setSelectedLangs([...selectedLangs, lang]);
    }
  };

  const handleStartDownload = () => {
    if (!parsed) return;

    let selectedEpNums: string[] = [];
    if (rangeInput.trim().toLowerCase() === 'all') {
      selectedEpNums = parsed.episodes.map((e) => e.num);
    } else {
      const parts = rangeInput.split(',').map((p) => p.trim());
      for (const part of parts) {
        if (part.includes('-')) {
          const [startStr, endStr] = part.split('-').map((s) => parseInt(s.trim(), 10));
          if (!isNaN(startStr) && !isNaN(endStr)) {
            for (let i = startStr; i <= endStr; i++) {
              selectedEpNums.push(String(i));
            }
          }
        } else if (part) {
          selectedEpNums.push(part);
        }
      }
    }

    if (selectedEpNums.length === 0) {
      selectedEpNums = parsed.episodes.map((e) => e.num);
    }

    const tasksToEnqueue = selectedEpNums.map((epNum) => ({
      animeTitle: parsed.title,
      episodeNum: epNum,
      site: parsed.site,
      quality: selectedQuality,
      downloadMode,
      targetSubLangs: selectedLangs,
      destinationFilePath: `./downloads/${parsed.title}/Season 01/${parsed.title} - S01E${epNum.padStart(2, '0')}.mp4`,
    }));

    downloadStore.enqueueTasks(tasksToEnqueue);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#05080E]/80 backdrop-blur-md">
      <div className="relative w-full max-w-2xl bg-[#161F30] border border-white/10 rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-[#131C2D]/80">
          <div>
            <span className="text-xs uppercase tracking-wider font-semibold text-emerald-400 font-mono">
              Stream Extracted ({parsed.site.toUpperCase()})
            </span>
            <h2 className="text-lg font-bold text-slate-100">{parsed.title}</h2>
          </div>
          <button
            type="button"
            onClick={() => downloadStore.toggleBatchModal(false)}
            className="text-slate-400 hover:text-slate-200 p-1.5 rounded-lg hover:bg-white/5 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-6 flex flex-col gap-5 max-h-[72vh] overflow-y-auto">
          {/* Download Mode Switcher */}
          <div className="grid grid-cols-3 gap-2 bg-[#0B0F17] p-1.5 rounded-xl border border-white/5">
            <button
              type="button"
              onClick={() => setDownloadMode('full')}
              className={`py-2 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-all ${
                downloadMode === 'full'
                  ? 'bg-gradient-to-r from-emerald-500 to-cyan-500 text-white shadow-md'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Full (Video + Sub)
            </button>
            <button
              type="button"
              onClick={() => setDownloadMode('sub_only')}
              className={`py-2 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-all ${
                downloadMode === 'sub_only'
                  ? 'bg-gradient-to-r from-cyan-500 to-blue-500 text-white shadow-md'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Chỉ Tải Sub (Sub-Only)
            </button>
            <button
              type="button"
              onClick={() => setDownloadMode('video_only')}
              className={`py-2 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-all ${
                downloadMode === 'video_only'
                  ? 'bg-gradient-to-r from-purple-500 to-indigo-500 text-white shadow-md'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Chỉ Tải Video (No Sub)
            </button>
          </div>

          {/* Episode Range Selector */}
          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Chọn Tập / Episode Range ({parsed.totalEpisodes} tập có sẵn)
            </label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={rangeInput}
                onChange={(e) => setRangeInput(e.target.value)}
                placeholder="all hoặc 1-12 hoặc 1,3,5"
                className="flex-1 bg-[#0B0F17] text-slate-200 text-sm px-3.5 py-2.5 rounded-xl border border-white/10 focus:border-cyan-400 focus:outline-none"
              />
              <button
                type="button"
                onClick={() => setRangeInput('all')}
                className="px-3 py-2.5 text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl transition-colors"
              >
                All
              </button>
              <button
                type="button"
                onClick={() => setRangeInput(`1-${Math.min(parsed.totalEpisodes, 6)}`)}
                className="px-3 py-2.5 text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl transition-colors"
              >
                Half
              </button>
            </div>
          </div>

          {/* Quality & Server Row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="flex flex-col gap-2">
              <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">Độ Phân Giải</label>
              <select
                value={selectedQuality}
                onChange={(e) => setSelectedQuality(e.target.value as StreamQuality)}
                className="bg-[#0B0F17] text-slate-200 text-sm px-3.5 py-2.5 rounded-xl border border-white/10 focus:border-cyan-400 focus:outline-none"
              >
                <option value="1080p">1080p Full HD (Khuyến nghị)</option>
                <option value="720p">720p HD</option>
                <option value="480p">480p SD</option>
                <option value="source">Source Stream (Direct)</option>
              </select>
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">Định dạng tên File</label>
              <select
                value={namingFormat}
                onChange={(e) => setNamingFormat(e.target.value as NamingFormat)}
                className="bg-[#0B0F17] text-slate-200 text-sm px-3.5 py-2.5 rounded-xl border border-white/10 focus:border-cyan-400 focus:outline-none"
              >
                <option value="simple">Simple (Anime - S01E01.mp4)</option>
                <option value="tvdb">TVDB Standard</option>
                <option value="anikoto">AniKoto Original</option>
              </select>
            </div>
          </div>

          {/* Subtitle Selection Checklist */}
          {downloadMode !== 'video_only' && (
            <div className="flex flex-col gap-2.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                  Phụ Đề / Subtitles (IETF Standards)
                </label>
                <span className="text-[11px] text-emerald-400 font-mono">es-LA / es-ES Standardized</span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {[
                  { code: 'es-LA', label: 'Spanish (LAT)' },
                  { code: 'es-ES', label: 'Spanish (ESP)' },
                  { code: 'en', label: 'English' },
                  { code: 'vi', label: 'Tiếng Việt' },
                ].map((lang) => {
                  const checked = selectedLangs.includes(lang.code);
                  return (
                    <button
                      key={lang.code}
                      type="button"
                      onClick={() => handleToggleLang(lang.code)}
                      className={`flex items-center justify-between px-3 py-2.5 rounded-xl border text-xs font-medium transition-all ${
                        checked
                          ? 'bg-cyan-950/60 border-cyan-500/50 text-cyan-300 shadow-sm shadow-cyan-500/20'
                          : 'bg-[#0B0F17]/60 border-white/5 text-slate-400 hover:border-white/10 hover:text-slate-200'
                      }`}
                    >
                      <span>{lang.label}</span>
                      <span
                        className={`w-3.5 h-3.5 rounded flex items-center justify-center border ${
                          checked ? 'bg-cyan-500 border-cyan-400 text-black' : 'border-slate-600'
                        }`}
                      >
                        {checked && '✓'}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Advanced CLI Options Drawer */}
          <div className="border-t border-white/10 pt-3">
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1 font-semibold"
            >
              <span>{showAdvanced ? '▼ Ẩn Tùy Chọn Nâng Cao' : '▶ Tùy Chọn Nâng Cao (TVDB, Server Priority, Exclude)'}</span>
            </button>

            {showAdvanced && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3 p-3 bg-[#0B0F17]/80 rounded-xl border border-white/5 text-xs">
                <div>
                  <label className="text-slate-400">TheTVDB Series ID/Slug</label>
                  <input
                    type="text"
                    value={tvdbId}
                    onChange={(e) => setTvdbId(e.target.value)}
                    placeholder="e.g. 397123"
                    className="w-full mt-1 bg-[#161F30] text-slate-200 px-2.5 py-1.5 rounded-lg border border-white/10"
                  />
                </div>
                <div>
                  <label className="text-slate-400">Server Ưu Tiên (--server-priority)</label>
                  <input
                    type="text"
                    value={serverPriority}
                    onChange={(e) => setServerPriority(e.target.value)}
                    placeholder="vidplay,megaplay"
                    className="w-full mt-1 bg-[#161F30] text-slate-200 px-2.5 py-1.5 rounded-lg border border-white/10"
                  />
                </div>
                <div>
                  <label className="text-slate-400">Server Loại Trừ (--exclude-servers)</label>
                  <input
                    type="text"
                    value={excludeServers}
                    onChange={(e) => setExcludeServers(e.target.value)}
                    placeholder="HD-1,VidCloud-1"
                    className="w-full mt-1 bg-[#161F30] text-slate-200 px-2.5 py-1.5 rounded-lg border border-white/10"
                  />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer actions */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-white/10 bg-[#131C2D]/80">
          <button
            type="button"
            onClick={() => downloadStore.toggleBatchModal(false)}
            className="px-4 py-2.5 text-xs font-semibold text-slate-300 hover:text-white rounded-xl hover:bg-white/5 transition-colors"
          >
            Hủy Bỏ
          </button>
          <button
            type="button"
            onClick={handleStartDownload}
            className="px-5 py-2.5 text-xs font-semibold text-white bg-gradient-to-r from-emerald-500 to-cyan-500 hover:from-emerald-400 hover:to-cyan-400 rounded-xl shadow-lg shadow-emerald-500/20 active:scale-95 transition-all"
          >
            Bắt Đầu Tải ({downloadMode.toUpperCase()})
          </button>
        </div>
      </div>
    </div>
  );
};
