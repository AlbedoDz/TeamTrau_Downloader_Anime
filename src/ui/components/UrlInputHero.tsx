import React, { useState, useEffect } from 'react';
import { downloadStore } from '../state/useDownloadStore';
import { ExtractorSite, ExtractorState } from '../types';

export interface UrlInputHeroProps {
  readonly onParseSuccess?: () => void;
}

export const UrlInputHero: React.FC<UrlInputHeroProps> = ({ onParseSuccess }) => {
  const [url, setUrlInput] = useState('');
  const [site, setSite] = useState<ExtractorSite>('unknown');
  const [extractorState, setExtractorState] = useState<ExtractorState>('idle');
  const [isParsing, setIsParsing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    // RAII Subscription to Store
    const unsubscribe = downloadStore.subscribe(() => {
      const state = downloadStore.getState();
      setUrlInput(state.currentUrl);
      setSite(state.extractorSite);
      setExtractorState(state.extractorState);
      setIsParsing(state.isParsing);
      setErrorMessage(state.parseError);
    });

    return () => {
      unsubscribe();
    };
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setUrlInput(val);
    downloadStore.setUrl(val);
  };

  const handlePasteClipboard = async () => {
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard) {
        const text = await navigator.clipboard.readText();
        if (text) {
          setUrlInput(text);
          downloadStore.setUrl(text);
          downloadStore.addLog('info', 'general', `Dán URL từ clipboard: ${text}`);
        }
      }
    } catch {
      downloadStore.addLog('warn', 'general', 'Không thể truy cập clipboard tự động. Vui lòng dán thủ công.');
    }
  };

  const handleParseSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim() || isParsing) return;
    await downloadStore.parseUrl();
    if (onParseSuccess && !downloadStore.getState().parseError) {
      onParseSuccess();
    }
  };

  const getBadgeStyle = (currentSite: ExtractorSite, state: ExtractorState) => {
    if (state === 'idle') return { bg: 'bg-slate-800', text: 'text-slate-400', label: 'Ready' };
    if (state === 'unsupported') return { bg: 'bg-rose-950/80', text: 'text-rose-400', label: 'Unsupported Site' };
    switch (currentSite) {
      case 'anikoto':
        return { bg: 'bg-emerald-950/80 border-emerald-500/40', text: 'text-emerald-400', label: 'AnikotoTV Engine' };
      case 'animesuge':
        return { bg: 'bg-cyan-950/80 border-cyan-500/40', text: 'text-cyan-400', label: 'AnimeSuge Extractor' };
      case 'allwish':
        return { bg: 'bg-purple-950/80 border-purple-500/40', text: 'text-purple-400', label: 'AllWish Native' };
      case 'animecube':
        return { bg: 'bg-amber-950/80 border-amber-500/40', text: 'text-amber-400', label: 'AnimeCube Next.js' };
      default:
        return { bg: 'bg-slate-800', text: 'text-slate-400', label: 'Auto Detect' };
    }
  };

  const badge = getBadgeStyle(site, extractorState);

  return (
    <div className="w-full max-w-4xl mx-auto my-6 px-4">
      <div className="relative p-6 sm:p-8 rounded-2xl bg-[#161F30]/75 backdrop-blur-xl border border-white/10 shadow-2xl overflow-hidden">
        {/* Glow backdrop accents */}
        <div className="absolute -top-12 -left-12 w-48 h-48 bg-emerald-500/15 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-12 -right-12 w-48 h-48 bg-cyan-500/15 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-xs uppercase tracking-wider font-semibold text-slate-400">Stream Source URL</span>
              <span
                className={`text-xs px-2.5 py-0.5 rounded-full font-mono border transition-all duration-200 ${badge.bg} ${badge.text}`}
              >
                {badge.label}
              </span>
            </div>
            <button
              type="button"
              onClick={handlePasteClipboard}
              className="text-xs flex items-center gap-1.5 text-cyan-400 hover:text-cyan-300 transition-colors py-1 px-2.5 rounded-md hover:bg-cyan-500/10 active:scale-95"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              Paste URL
            </button>
          </div>

          <form onSubmit={handleParseSubmit} className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <input
                type="text"
                value={url}
                onChange={handleInputChange}
                placeholder="Dán link Anime (e.g. https://anikototv.to/watch/solo-leveling...)"
                className="w-full bg-[#0B0F17]/80 text-slate-100 placeholder-slate-500 text-sm sm:text-base px-4 py-3.5 rounded-xl border border-white/10 focus:border-cyan-400 focus:ring-2 focus:ring-cyan-500/20 transition-all duration-200 outline-none"
              />
              {url && (
                <button
                  type="button"
                  onClick={() => {
                    setUrlInput('');
                    downloadStore.setUrl('');
                  }}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 p-1"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>

            <button
              type="submit"
              disabled={!url.trim() || isParsing || extractorState === 'unsupported'}
              className="flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl font-medium text-white bg-gradient-to-r from-emerald-500 to-cyan-500 hover:from-emerald-400 hover:to-cyan-400 active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none transition-all duration-200 shadow-lg shadow-emerald-500/20"
            >
              {isParsing ? (
                <>
                  <svg className="animate-spin w-5 h-5 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  <span>Phân tích Stream...</span>
                </>
              ) : (
                <>
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  <span>1-Click Parse</span>
                </>
              )}
            </button>
          </form>

          {errorMessage && (
            <div className="flex items-center gap-2 text-xs text-rose-400 bg-rose-950/40 border border-rose-800/30 px-3.5 py-2.5 rounded-lg">
              <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>{errorMessage}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
