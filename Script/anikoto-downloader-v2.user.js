// ==UserScript==
// @name         Anikoto Subtitle & Video Downloader v2
// @namespace    http://tampermonkey.net/
// @version      2.2.0
// @description  High-performance batch subtitle downloader for anikototv.to with smart language classification (es-LA, es-ES, EN, All), Megaplay real-id resolver, multi-server fail-over, and full multi-page episode range support
// @author       TeamTrau & Antigravity
// @match        *://anikototv.to/*
// @match        *://*/*
// @grant        GM_download
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @connect      *
// @run-at       document-start
// ==/UserScript==

(function() {
    'use strict';

    const isMainSite = window.location.hostname.includes('anikototv.to');
    const isIframe = window.self !== window.top;

    if (!isMainSite && !isIframe) {
        return;
    }

    if (isMainSite) {
        console.log('[Anikoto Subtitle v2] Main site script initialized.');
    } else {
        console.log('[Anikoto Subtitle v2] Player iframe script initialized on:', window.location.hostname);
    }

    // ──────────────────────────────────────────────────────────────────────────
    // 1. Language Classification & Variant Resolution Engine (Kaizen Poka-Yoke)
    // ──────────────────────────────────────────────────────────────────────────

    /**
     * Classify Spanish variant according to the latest project standards:
     * - 'es-LA': Spanish Latin America (e.g. Spanish[LAT], Español (LA), Latam, es-419)
     * - 'es-ES': Spanish Spain / European (e.g. Spanish[ESP], Español (ES), Castellano)
     * - 'es': Generic Spanish
     * - null: Non-Spanish
     */
    function classifySpanishVariant(label, code = '') {
        const lbl = (label || '').trim().toLowerCase();
        const c = (code || '').trim().toLowerCase();

        // Anti-pattern guard: Exclude Portuguese ("portuguese" contains "es")
        if (lbl.includes('portuguese') || lbl.includes('portugues') || ['pt', 'por', 'pt-br', 'pt-pt'].includes(c)) {
            return null;
        }

        let isSpanish = false;
        const spanishKeywords = ['spanish', 'espanol', 'español', 'castellano', 'castilian'];
        if (spanishKeywords.some(kw => lbl.includes(kw))) {
            isSpanish = true;
        } else if (['es', 'spa', 'spanish', 'es-la', 'es-419', 'es-es', 'es_la', 'es_419', 'es_es'].includes(c)) {
            isSpanish = true;
        }

        if (!isSpanish) {
            return null;
        }

        // Check for Latin American Spanish indicators (High Priority)
        const latinIndicators = [
            'latin america', 'latin_america', 'latinamerica',
            'america latina', 'américa latina', 'americalatina',
            'latinoamérica', 'latinoamerica', 'latam',
            '[lat]', '(lat)', '[la]', '(la)', '[latam]', '(latam)',
            '[es-la]', '(es-la)', '[es-419]', '(es-419)',
            'spanish[lat]', 'spanish[la]', 'español (la)', 'espanol (la)',
            'spanish (la)', 'español (lat)', 'espanol (lat)', 'spanish (lat)',
            'español (latam)', 'espanol (latam)', 'spanish (latam)',
            'spanish (- español (la))', 'spanish (- spanish[lat])'
        ];

        if (latinIndicators.some(ind => lbl.includes(ind)) || ['es-la', 'es-419', 'es_la', 'es_419'].includes(c)) {
            return 'es-LA';
        }

        // Check for European Spain Spanish indicators
        const spainIndicators = [
            'spain', 'españa', 'espana', 'castellano', 'castilian',
            'european', '[esp]', '(esp)', '[es]', '(es)',
            '[es-es]', '(es-es)', 'spanish[esp]', 'español (es)', 'espanol (es)',
            'spanish (es)', 'spanish (- español (es))', 'spanish (- spanish[esp])'
        ];

        const hasSpainKeyword = spainIndicators.some(ind => lbl.includes(ind)) || ['es-es', 'es_es'].includes(c);
        if (hasSpainKeyword && !latinIndicators.some(ind => lbl.includes(ind))) {
            return 'es-ES';
        }

        return 'es';
    }

    /**
     * Strict English track identifier
     */
    function isEnglishTrack(track) {
        const label = (track.label || '').trim().toLowerCase();
        const lang = (track.lang || '').trim().toLowerCase();

        const nonEngKeywords = [
            'spanish', 'espanol', 'español', 'castellano', 'esp',
            'french', 'francais', 'fre',
            'german', 'deutsch', 'ger',
            'italian', 'italiano', 'ita',
            'portuguese', 'portugues', 'por',
            'swedish', 'svenska', 'swe',
            'vietnamese', 'tieng viet', 'vie',
            'arabic', 'ara',
            'turkish', 'turkce', 'tur',
            'hindi', 'hin',
            'russian', 'russkiy', 'rus',
            'chinese', 'zhongwen', 'chi', 'zho',
            'indonesian', 'bahasa', 'ind',
            'thai', 'tha',
            'polish', 'polski', 'pol',
            'dutch', 'nederlands', 'dut',
            'korean', 'hangug', 'kor',
            'japanese', 'nihongo', 'jpn'
        ];

        if (nonEngKeywords.some(kw => label.includes(kw)) && !label.includes('english')) {
            return false;
        }

        const nonEngLangs = ['es', 'fr', 'de', 'it', 'pt', 'sv', 'vi', 'ar', 'tr', 'hi', 'ru', 'zh', 'id', 'th', 'pl', 'nl', 'ko', 'ja'];
        if (nonEngLangs.some(l => lang.startsWith(l))) {
            return false;
        }

        const engRegex = /\b(en|eng|english|cr|forced|force)\b/i;
        const langRegex = /^(en|eng|english)([-_].*)?$/i;

        return engRegex.test(label) || langRegex.test(lang) || ['sub', 'srt', 'vtt'].includes(label);
    }

    /**
     * Determine normalized language tag and human readable display badge
     */
    function getTrackTagAndDisplay(track) {
        const label = (track.label || '').trim();
        const lang = (track.lang || '').trim();

        // 1. Spanish check
        const spVar = classifySpanishVariant(label, lang);
        if (spVar === 'es-LA') {
            return { tag: 'es-LA', badge: 'es-LA', color: '#ff9800' };
        }
        if (spVar === 'es-ES') {
            return { tag: 'es-ES', badge: 'es-ES', color: '#e91e63' };
        }
        if (spVar === 'es') {
            return { tag: 'es', badge: 'ES', color: '#ff9800' };
        }

        // 2. English check
        if (isEnglishTrack(track)) {
            const isForced = label.toLowerCase().includes('forced') || label.toLowerCase().includes('force');
            return { tag: isForced ? 'en.forced' : 'en', badge: isForced ? 'EN (Forced)' : 'EN', color: '#4caf50' };
        }

        // 3. Vietnamese check
        if (label.toLowerCase().includes('viet') || lang.toLowerCase().startsWith('vi')) {
            return { tag: 'vi', badge: 'VI', color: '#00bcd4' };
        }

        // 4. Portuguese check
        if (label.toLowerCase().includes('portugu') || ['pt', 'pt-br'].includes(lang.toLowerCase())) {
            return { tag: 'pt-BR', badge: 'PT-BR', color: '#9c27b0' };
        }

        // 5. French check
        if (label.toLowerCase().includes('franc') || lang.toLowerCase().startsWith('fr')) {
            return { tag: 'fr', badge: 'FR', color: '#3f51b5' };
        }

        // 6. German check
        if (label.toLowerCase().includes('deutsch') || label.toLowerCase().includes('german') || lang.toLowerCase().startsWith('de')) {
            return { tag: 'de', badge: 'DE', color: '#795548' };
        }

        // Generic Fallback
        const cleanTag = (lang || label || 'sub').replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 10) || 'sub';
        return { tag: cleanTag, badge: label.slice(0, 15), color: '#607d8b' };
    }

    /**
     * Filter & prioritize subtitle tracks according to user selected bulk download mode
     */
    function filterTracksByMode(tracks, mode = 'en') {
        if (!tracks || tracks.length === 0) return [];

        switch (mode) {
            case 'en': {
                const enTracks = tracks.filter(isEnglishTrack);
                enTracks.sort((a, b) => {
                    const score = (t) => {
                        const lbl = (t.label || '').toLowerCase();
                        if (lbl.includes('cr')) return 0;
                        if (lbl.includes('forced') || lbl.includes('force')) return 2;
                        return 1;
                    };
                    return score(a) - score(b);
                });
                return enTracks;
            }

            case 'es-la': {
                const latinTracks = tracks.filter(t => classifySpanishVariant(t.label, t.lang) === 'es-LA');
                if (latinTracks.length > 0) return latinTracks;
                return tracks.filter(t => classifySpanishVariant(t.label, t.lang) === 'es');
            }

            case 'es-es': {
                return tracks.filter(t => classifySpanishVariant(t.label, t.lang) === 'es-ES');
            }

            case 'es-all': {
                const spTracks = tracks.filter(t => classifySpanishVariant(t.label, t.lang) !== null);
                spTracks.sort((a, b) => {
                    const getRank = (t) => {
                        const v = classifySpanishVariant(t.label, t.lang);
                        if (v === 'es-LA') return 0;
                        if (v === 'es') return 1;
                        return 2;
                    };
                    return getRank(a) - getRank(b);
                });
                return spTracks;
            }

            case 'multi_en_es': {
                const res = [];
                const enList = tracks.filter(isEnglishTrack);
                if (enList.length > 0) res.push(...enList);

                const esList = tracks.filter(t => classifySpanishVariant(t.label, t.lang) !== null);
                if (esList.length > 0) res.push(...esList);
                return res;
            }

            case 'all':
            default:
                return tracks;
        }
    }

    // ──────────────────────────────────────────────────────────────────────────
    // 2. Parser Helpers, VRF Encryption & Stream Extraction
    // ──────────────────────────────────────────────────────────────────────────

    function rc4(key, str) {
        let s = [], j = 0, x, res = '';
        for (let i = 0; i < 256; i++) {
            s[i] = i;
        }
        for (let i = 0; i < 256; i++) {
            j = (j + s[i] + key.charCodeAt(i % key.length)) % 256;
            x = s[i];
            s[i] = s[j];
            s[j] = x;
        }
        let i = 0;
        j = 0;
        for (let y = 0; y < str.length; y++) {
            i = (i + 1) % 256;
            j = (j + s[i]) % 256;
            x = s[i];
            s[i] = s[j];
            s[j] = x;
            res += String.fromCharCode(str.charCodeAt(y) ^ s[(s[i] + s[j]) % 256]);
        }
        return res;
    }

    function vrfEncrypt(text) {
        try {
            return btoa(rc4("simple-hash", String(text)));
        } catch (e) {
            return '';
        }
    }

    function findVideoSourcesInObject(obj) {
        let sources = [];
        if (!obj || typeof obj !== 'object') return sources;

        if (Array.isArray(obj)) {
            for (let item of obj) {
                sources = sources.concat(findVideoSourcesInObject(item));
            }
            return sources;
        }

        for (let key in obj) {
            if (Object.prototype.hasOwnProperty.call(obj, key)) {
                const val = obj[key];
                const lowerKey = key.toLowerCase();

                if (lowerKey === 'sources' && Array.isArray(val)) {
                    val.forEach(s => {
                        if (s && typeof s === 'object') {
                            const url = s.file || s.url || s.src;
                            if (url && typeof url === 'string') {
                                sources.push({
                                    url: url,
                                    type: s.type || (url.includes('.m3u8') ? 'hls' : 'mp4')
                                });
                            }
                        }
                    });
                } else if (typeof val === 'string' && (val.includes('.m3u8') || val.includes('.mp4'))) {
                    if (val.startsWith('http://') || val.startsWith('https://')) {
                        sources.push({
                            url: val,
                            type: val.includes('.m3u8') ? 'hls' : 'mp4'
                        });
                    }
                } else if (typeof val === 'object') {
                    sources = sources.concat(findVideoSourcesInObject(val));
                }
            }
        }
        return sources;
    }

    function findSubtitlesInObject(obj) {
        let tracks = [];
        if (!obj || typeof obj !== 'object') return tracks;

        if (Array.isArray(obj)) {
            for (let item of obj) {
                tracks = tracks.concat(findSubtitlesInObject(item));
            }
            return tracks;
        }

        for (let key in obj) {
            if (Object.prototype.hasOwnProperty.call(obj, key)) {
                const val = obj[key];
                const lowerKey = key.toLowerCase();

                if (['tracks', 'subtitles', 'subs', 'captions'].includes(lowerKey) && Array.isArray(val)) {
                    val.forEach(t => {
                        if (t && typeof t === 'object') {
                            const url = t.file || t.url || t.src;
                            if (url && typeof url === 'string') {
                                tracks.push({
                                    url: url,
                                    label: t.label || t.name || t.language || 'Detected Subtitle',
                                    lang: t.lang || t.language || 'en'
                                });
                            }
                        }
                    });
                } else if (typeof val === 'string' && (val.includes('.vtt') || val.includes('.srt') || val.includes('lostproject.club'))) {
                    if (val.startsWith('http://') || val.startsWith('https://')) {
                        let label = 'Sub';
                        if (obj.label || obj.name || obj.language) {
                            label = obj.label || obj.name || obj.language;
                        } else {
                            const match = val.match(/\/([a-zA-Z0-9_-]+)\.(vtt|srt)/);
                            if (match) label = match[1].toUpperCase();
                        }
                        tracks.push({
                            url: val,
                            label: label,
                            lang: label.toLowerCase()
                        });
                    }
                } else if (typeof val === 'object') {
                    tracks = tracks.concat(findSubtitlesInObject(val));
                }
            }
        }
        return tracks;
    }

    function inferLabelFromUrl(url) {
        if (typeof url !== 'string') return 'Sub';
        const match = url.match(/\/([a-zA-Z0-9_-]+)\.(vtt|srt)/i);
        if (match && !/index|sub|track|play/i.test(match[1])) {
            return match[1].toUpperCase();
        }
        try {
            const urlObj = new URL(url, window.location.href);
            const lang = urlObj.searchParams.get('lang') || urlObj.searchParams.get('language');
            if (lang) return lang.toUpperCase();
        } catch (e) {}
        return 'Sub';
    }

    function convertVttToSrt(vttText) {
        if (!vttText) return '';
        const cleanText = vttText.trim().replace(/\r\n/g, '\n').replace(/\r/g, '\n');
        const lines = cleanText.split('\n');

        let parsedCues = [];
        let currentCue = null;
        let insideHeader = true;

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();

            if (insideHeader) {
                if (line.startsWith('WEBVTT') || line.startsWith('NOTE') || line.startsWith('STYLE') || line.startsWith('REGION')) {
                    continue;
                }
                if (line.includes('-->')) {
                    insideHeader = false;
                } else if (line === '') {
                    continue;
                } else {
                    if (line.includes(':') && !/^\d+$/.test(line)) {
                        continue;
                    }
                }
            }

            const timestampMatch = line.match(/^(\d{2}:)?(\d{2}):(\d{2})[.,](\d{3})\s*-->\s*(\d{2}:)?(\d{2}):(\d{2})[.,](\d{3})/);
            if (timestampMatch) {
                if (currentCue) {
                    parsedCues.push(currentCue);
                }

                let startH = timestampMatch[1] ? timestampMatch[1].replace(':', '') : '00';
                let startM = timestampMatch[2];
                let startS = timestampMatch[3];
                let startMs = timestampMatch[4];

                let endH = timestampMatch[5] ? timestampMatch[5].replace(':', '') : '00';
                let endM = timestampMatch[6];
                let endS = timestampMatch[7];
                let endMs = timestampMatch[8];

                const formattedTime = `${startH}:${startM}:${startS},${startMs} --> ${endH}:${endM}:${endS},${endMs}`;
                currentCue = { time: formattedTime, text: [] };
            } else if (line === '') {
                if (currentCue && currentCue.text.length > 0) {
                    parsedCues.push(currentCue);
                    currentCue = null;
                }
            } else {
                if (currentCue) {
                    const cleanedLine = line.replace(/<[^>]+>/g, (tag) => {
                        return /<\/?(i|b|u)>/i.test(tag) ? tag : '';
                    });
                    if (/^\d+$/.test(cleanedLine) && currentCue.text.length === 0) {
                        continue;
                    }
                    currentCue.text.push(cleanedLine);
                }
            }
        }

        if (currentCue) {
            parsedCues.push(currentCue);
        }

        let srtOutput = [];
        let cueIndex = 1;
        for (const cue of parsedCues) {
            if (cue.text.length === 0) continue;
            let cueLines = cue.text;

            for (let t = 0; t < cueLines.length; t++) {
                cueLines[t] = cueLines[t].replace(/<[^>]+>/g, '');
            }

            const finalCueText = cueLines.filter(line => line.trim() !== '').join('\r\n');
            if (!finalCueText) continue;

            srtOutput.push(cueIndex.toString());
            srtOutput.push(cue.time);
            srtOutput.push(finalCueText);
            srtOutput.push('');
            cueIndex++;
        }

        return srtOutput.join('\r\n');
    }

    function getSafeReferer(url) {
        if (!url) return '';
        try {
            const parsed = new URL(url);
            return parsed.origin + '/';
        } catch (e) {
            return url;
        }
    }

    // ──────────────────────────────────────────────────────────────────────────
    // 3. Network Hooking (Main Site & Embed Player Iframes)
    // ──────────────────────────────────────────────────────────────────────────

    function hookNetwork() {
        const handleJSONResponse = (url, json) => {
            try {
                const tracks = findSubtitlesInObject(json);
                const videoSources = findVideoSourcesInObject(json);

                if (tracks.length > 0 || videoSources.length > 0) {
                    const uniqueTracks = [];
                    const seen = new Set();
                    for (const t of tracks) {
                        if (!seen.has(t.url)) {
                            seen.add(t.url);
                            t.referer = window.location.href;
                            uniqueTracks.push(t);
                        }
                    }

                    const uniqueVideoSources = [];
                    const seenVideo = new Set();
                    for (const s of videoSources) {
                        if (!seenVideo.has(s.url)) {
                            seenVideo.add(s.url);
                            s.referer = window.location.href;
                            uniqueVideoSources.push(s);
                        }
                    }

                    if (uniqueTracks.length > 0 || uniqueVideoSources.length > 0) {
                        console.log('[Anikoto Subtitle v2] Detected in network:', uniqueTracks, uniqueVideoSources);
                        window.top.postMessage({
                            type: 'ANIKOTO_SUBTITLES_DETECTED_V2',
                            tracks: uniqueTracks,
                            videoSources: uniqueVideoSources
                        }, '*');
                    }
                }
            } catch (e) {
                console.error('[Anikoto Subtitle v2] JSON parse error', e);
            }
        };

        // Hook Fetch
        const originalFetch = window.fetch;
        window.fetch = async function(...args) {
            const url = args[0];
            if (!isMainSite && typeof url === 'string' && (url.includes('.vtt') || url.includes('.srt') || url.includes('lostproject.club'))) {
                const label = inferLabelFromUrl(url);
                window.top.postMessage({
                    type: 'ANIKOTO_SUBTITLES_DETECTED_V2',
                    tracks: [{ url: url, label: label, lang: label.toLowerCase(), referer: window.location.href }]
                }, '*');
            }
            const response = await originalFetch.apply(this, args);
            const clone = response.clone();
            clone.json().then(data => {
                handleJSONResponse(args[0], data);
            }).catch(() => {});
            return response;
        };

        // Hook XHR
        const originalOpen = XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open = function(method, url, ...args) {
            this._url = url;
            if (!isMainSite && typeof url === 'string' && (url.includes('.vtt') || url.includes('.srt') || url.includes('lostproject.club'))) {
                const label = inferLabelFromUrl(url);
                window.top.postMessage({
                    type: 'ANIKOTO_SUBTITLES_DETECTED_V2',
                    tracks: [{ url: url, label: label, lang: label.toLowerCase(), referer: window.location.href }]
                }, '*');
            }
            return originalOpen.call(this, method, url, ...args);
        };

        const originalSend = XMLHttpRequest.prototype.send;
        XMLHttpRequest.prototype.send = function(...args) {
            this.addEventListener('load', function() {
                try {
                    const data = JSON.parse(this.responseText);
                    handleJSONResponse(this._url, data);
                } catch (e) {}
            });
            return originalSend.apply(this, args);
        };
    }

    // ──────────────────────────────────────────────────────────────────────────
    // 4. Main Site Dashboard & Full Multi-Page Bulk Downloader Engine
    // ──────────────────────────────────────────────────────────────────────────

    if (isMainSite) {
        let detectedTracks = [];
        let detectedVideoSources = [];
        let uiPanel = null;
        let uiButton = null;
        let bulkDownloading = false;
        let bulkCancel = false;

        // Settings (Persisted in localStorage)
        let selectedLangMode = localStorage.getItem('anikoto_v2_lang_mode') || 'es-la';
        let selectedFormat = localStorage.getItem('anikoto_v2_format') || 'srt';
        let selectedScope = localStorage.getItem('anikoto_v2_scope') || 'all';
        let customRangeText = localStorage.getItem('anikoto_v2_custom_range') || '';

        hookNetwork();

        // Episode change watcher
        let lastUrl = window.location.href;
        setInterval(() => {
            if (window.location.href !== lastUrl) {
                lastUrl = window.location.href;
                detectedTracks = [];
                detectedVideoSources = [];
                updateUI();
            }
        }, 1000);

        // Receive message from iframes
        window.addEventListener('message', function(event) {
            if (event.data && (event.data.type === 'ANIKOTO_SUBTITLES_DETECTED_V2' || event.data.type === 'ANIKOTO_SUBTITLES_DETECTED')) {
                const tracks = event.data.tracks || [];
                const videoSources = event.data.videoSources || [];

                tracks.forEach(track => {
                    if (!detectedTracks.some(t => t.url === track.url)) {
                        detectedTracks.push(track);
                    }
                });
                videoSources.forEach(src => {
                    if (!detectedVideoSources.some(s => s.url === src.url)) {
                        detectedVideoSources.push(src);
                    }
                });
                updateUI();
            }
        });

        // GreaseMonkey Request with retry & strict timeout
        function GM_xmlhttpRequestWithRetry(options, retries = 3, initialDelay = 3000) {
            return new Promise((resolve, reject) => {
                let attempt = 0;
                let currentDelay = initialDelay;

                function makeRequest() {
                    const reqOptions = {
                        timeout: 12000,
                        ...options,
                        onload: function(res) {
                            if (res.status === 429 || res.status === 403) {
                                if (attempt < retries - 1) {
                                    attempt++;
                                    console.warn(`[Anikoto Subtitle v2] Rate limit HTTP ${res.status} on ${options.url}. Retrying in ${currentDelay}ms...`);
                                    setTimeout(makeRequest, currentDelay);
                                    currentDelay *= 2;
                                    return;
                                }
                            }
                            resolve(res);
                        },
                        onerror: function(err) {
                            if (attempt < retries - 1) {
                                attempt++;
                                setTimeout(makeRequest, currentDelay);
                                currentDelay *= 2;
                                return;
                            }
                            if (options.onerror) options.onerror(err);
                            resolve({ status: 500, error: err });
                        },
                        ontimeout: function() {
                            if (attempt < retries - 1) {
                                attempt++;
                                setTimeout(makeRequest, currentDelay);
                                currentDelay *= 2;
                                return;
                            }
                            if (options.ontimeout) options.ontimeout();
                            resolve({ status: 408, error: 'Timeout' });
                        }
                    };
                    GM_xmlhttpRequest(reqOptions);
                }
                makeRequest();
            });
        }

        async function fetchInternal(url, retries = 3, delay = 3000) {
            const absoluteUrl = url.startsWith('http') ? url : window.location.origin + url;
            const res = await GM_xmlhttpRequestWithRetry({
                method: 'GET',
                url: absoluteUrl,
                anonymous: false,
                withCredentials: true,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json, text/javascript, */*; q=0.01',
                    'Referer': window.location.href,
                    'User-Agent': navigator.userAgent
                }
            }, retries, delay);

            if (res.status !== 200) {
                throw new Error('HTTP status ' + res.status);
            }
            return JSON.parse(res.responseText);
        }

        function parseSeriesAndSeason(rawTitle, url = window.location.href) {
            let cleanTitle = (rawTitle || '').replace(/\s*-\s*Watch\s*.*$/i, '')
                                             .replace(/\s*Watch\s*.*$/i, '')
                                             .replace(/\s*-\s*Anikoto.*$/i, '')
                                             .replace(/\s*Anime\s*Online.*$/i, '')
                                             .trim();

            let season = 1;
            const mUrlOrd = url.match(/(\d+)(?:st|nd|rd|th)?[-_]?season/i);
            const mTitleOrd = cleanTitle.match(/(\d+)(?:st|nd|rd|th)?\s*(?:season|series|ss)/i);

            if (mUrlOrd) {
                season = parseInt(mUrlOrd[1], 10);
            } else if (mTitleOrd) {
                season = parseInt(mTitleOrd[1], 10);
            } else {
                const mUrl = url.match(/season[-_]?(\d+)/i);
                if (mUrl) {
                    season = parseInt(mUrl[1], 10);
                } else {
                    const mTitle = cleanTitle.match(/(?:season|series|ss)\s*[-_]?\s*(\d+)/i);
                    if (mTitle) {
                        season = parseInt(mTitle[1], 10);
                    }
                }
            }

            if (isNaN(season) || season < 1) season = 1;

            // Remove season text from series folder title
            cleanTitle = cleanTitle.replace(/\s*\d+(?:st|nd|rd|th)?\s*(?:season|series|ss)/gi, '')
                                   .replace(/\s*(?:season|series|ss)\s*[-_]?\s*\d+/gi, '')
                                   .trim();

            const sanitizedTitle = cleanTitle.replace(/[\\/*?:"<>|]/g, '').trim().replace(/\s+/g, ' ') || 'Anime_Download';
            const seasonFolder = `Season ${String(season).padStart(2, '0')}`;
            const seasonCode = `s${String(season).padStart(2, '0')}`;

            return {
                seriesTitle: sanitizedTitle,
                season: season,
                seasonFolder: seasonFolder,
                seasonCode: seasonCode
            };
        }

        function getCleanAnimeFolderName() {
            const h1 = document.querySelector('h1.film-name, .film-info h1, .anisc-detail .film-name, h1.title');
            const raw = h1 ? h1.innerText : document.title;
            const seriesInfo = parseSeriesAndSeason(raw, window.location.href);
            return seriesInfo.seriesTitle;
        }

        function getEpisodeLabel(epNum, rawText = '') {
            let epNumClean = String(epNum);
            const match = epNumClean.match(/(?:ep|episode)[-_]?(\d+)/i);
            if (match) epNumClean = match[1];

            let epNumPadded = epNumClean;
            if (epNumPadded.length < 2) epNumPadded = '0' + epNumPadded;

            const h1 = document.querySelector('h1.film-name, .film-info h1, .anisc-detail .film-name, h1.title');
            const rawTitle = h1 ? h1.innerText : document.title;
            const seriesInfo = parseSeriesAndSeason(rawTitle, window.location.href);

            let cleanTitle = (rawText || '').trim().replace(/\s+/g, ' ');
            cleanTitle = cleanTitle.replace(/^(?:ep|episode)?\s*\d+\s*[:.-]?\s*/i, '').trim();

            let epLabel = `${seriesInfo.seasonCode}e${epNumPadded}`;
            if (cleanTitle && cleanTitle.toLowerCase() !== `ep ${epNumClean}` && cleanTitle.toLowerCase() !== `episode ${epNumClean}`) {
                const safeTitle = cleanTitle.replace(/[\\/*?:"<>|]/g, '').trim();
                if (safeTitle) epLabel += ` - ${safeTitle}`;
            }
            return epLabel;
        }

        function getEpisodeTitle() {
            const h1 = document.querySelector('h1.film-name, .film-info h1, .anisc-detail .film-name, h1.title');
            const rawTitle = h1 ? h1.innerText : document.title;
            const seriesInfo = parseSeriesAndSeason(rawTitle, window.location.href);

            let epActive = document.querySelector('#w-episodes .ep-item.active, #w-episodes a.active, .episodes a.active');
            let epSlug = epActive ? epActive.getAttribute('data-slug') : '';
            if (!epSlug) epSlug = document.querySelector('#w-report-ep-num')?.value || '01';

            let epNumClean = '01';
            const match = String(epSlug).match(/(?:ep|episode|ep-)?[-_]?(\d+)/i);
            if (match) {
                epNumClean = match[1];
            } else if (/^\d+$/.test(epSlug)) {
                epNumClean = epSlug;
            }
            if (epNumClean.length < 2) epNumClean = '0' + epNumClean;

            return `${seriesInfo.seriesTitle} - ${seriesInfo.seasonCode}e${epNumClean}`;
        }

        function updateBadge(epNum, text, bg, color) {
            const epLink = document.querySelector(`#w-episodes a[data-slug="${epNum}"], .episodes a[data-slug="${epNum}"], a[data-slug="${epNum}"]`);
            if (!epLink) return;

            let badge = epLink.querySelector('.ani-sub-badge');
            if (!badge) {
                badge = document.createElement('span');
                badge.className = 'ani-sub-badge';
                badge.style.marginLeft = '6px';
                badge.style.padding = '2px 5px';
                badge.style.fontSize = '10px';
                badge.style.fontWeight = 'bold';
                badge.style.borderRadius = '4px';
                badge.style.lineHeight = '1';
                badge.style.display = 'inline-block';
                badge.style.verticalAlign = 'middle';
                epLink.appendChild(badge);
            }
            badge.innerText = text;
            badge.style.background = bg;
            badge.style.color = color;
        }

        /**
         * Fetch complete episode list for the entire anime (across all pagination ranges)
         */
        async function fetchAllEpisodesList() {
            let animeId = null;

            // 1. Try finding mangaId from script variables
            const scripts = Array.from(document.querySelectorAll('script'));
            for (const script of scripts) {
                const text = script.innerText || '';
                const m = text.match(/mangaId\s*=\s*['"]?(\d+)['"]?/);
                if (m) {
                    animeId = m[1];
                    break;
                }
            }

            // 2. Try finding from DOM attributes
            if (!animeId) {
                const el = document.querySelector('[data-manga-id], [data-anime-id], [data-id]');
                if (el) {
                    animeId = el.getAttribute('data-manga-id') || el.getAttribute('data-anime-id');
                }
            }

            // 3. If animeId found, fetch complete dynamic episode list via VRF API
            if (animeId) {
                try {
                    const vrf = vrfEncrypt(animeId);
                    const epUrl = `/ajax/episode/list/${animeId}?vrf=${encodeURIComponent(vrf)}`;
                    const json = await fetchInternal(epUrl);
                    const html = json.result || '';
                    if (html) {
                        const parser = new DOMParser();
                        const doc = parser.parseFromString(html, 'text/html');
                        const rawLinks = Array.from(doc.querySelectorAll('a[data-ids]'));

                        if (rawLinks.length > 0) {
                            console.log(`[Anikoto Subtitle v2] Successfully fetched all ${rawLinks.length} episodes via VRF API.`);
                            return rawLinks.map((a, idx) => ({
                                ids: a.getAttribute('data-ids'),
                                slug: a.getAttribute('data-slug') || String(idx + 1),
                                title: a.innerText || `Episode ${idx + 1}`
                            }));
                        }
                    }
                } catch (e) {
                    console.warn('[Anikoto Subtitle v2] VRF API fetch failed, fallback to DOM scanning...', e);
                }
            }

            // 4. Fallback to DOM elements
            const domLinks = Array.from(document.querySelectorAll('#w-episodes a[data-ids], .episodes a[data-ids], a[data-ids]'));
            const uniqueMap = new Map();
            domLinks.forEach((a, idx) => {
                const ids = a.getAttribute('data-ids');
                const slug = a.getAttribute('data-slug') || String(idx + 1);
                if (ids && !uniqueMap.has(slug)) {
                    uniqueMap.set(slug, {
                        ids: ids,
                        slug: slug,
                        title: a.innerText || `Episode ${slug}`
                    });
                }
            });

            return Array.from(uniqueMap.values());
        }

        /**
         * Parse custom range string like "1-50, 55, 60-70"
         */
        function parseCustomRanges(inputStr, allEpisodes) {
            if (!inputStr || !inputStr.trim()) return allEpisodes;
            const set = new Set();
            const parts = inputStr.split(',');

            parts.forEach(part => {
                const p = part.trim();
                if (p.includes('-')) {
                    const [start, end] = p.split('-').map(n => parseInt(n.trim(), 10));
                    if (!isNaN(start) && !isNaN(end)) {
                        for (let i = Math.min(start, end); i <= Math.max(start, end); i++) {
                            set.add(String(i));
                        }
                    }
                } else {
                    const num = parseInt(p, 10);
                    if (!isNaN(num)) {
                        set.add(String(num));
                    }
                }
            });

            return allEpisodes.filter(ep => {
                const numOnly = ep.slug.replace(/[^0-9]/g, '');
                return set.has(ep.slug) || set.has(numOnly);
            });
        }

        /**
         * Resolve real stream sources API endpoint (Handling Megaplay data-id extraction & Fallbacks)
         */
        async function resolveSourcesApiUrl(playerUrl) {
            if (!playerUrl) return '';
            const playerObj = new URL(playerUrl);
            let apiUrl = '';

            // Check if Megaplay / Vidwish / Megacloud embed requires real data-id
            if (playerUrl.includes('megaplay.buzz') || playerUrl.includes('vidwish.live') || playerUrl.includes('/stream/s-')) {
                try {
                    const embedRes = await GM_xmlhttpRequestWithRetry({
                        method: 'GET',
                        url: playerUrl,
                        headers: {
                            'User-Agent': navigator.userAgent,
                            'Referer': window.location.href
                        }
                    }, 2, 2000);

                    if (embedRes && embedRes.status === 200 && embedRes.responseText) {
                        const html = embedRes.responseText;
                        const parser = new DOMParser();
                        const doc = parser.parseFromString(html, 'text/html');
                        const playerDiv = doc.querySelector('#megaplay-player[data-id], .fix-area[data-id], [data-id]');
                        let realId = playerDiv ? playerDiv.getAttribute('data-id') : null;
                        if (!realId) {
                            const m = html.match(/data-id=["'](\d+)["']/);
                            if (m) realId = m[1];
                        }
                        if (realId) {
                            apiUrl = `${playerObj.origin}/stream/getSources?id=${realId}`;
                            return apiUrl;
                        }
                    }
                } catch (e) {
                    console.warn('[Anikoto Subtitle v2] Embed page fetch failed', e);
                }
            }

            // Fallback: standard regex matches
            const streamMatch = playerObj.pathname.match(/\/stream\/s-\d+\/(\d+)/);
            if (streamMatch) {
                apiUrl = `${playerObj.origin}/stream/getSources?id=${streamMatch[1]}`;
            } else if (playerObj.pathname.includes('getSources') || playerObj.pathname.includes('sources')) {
                apiUrl = playerUrl;
            } else {
                const embedMatch = playerObj.pathname.match(/(\/embed-[^\/]+\/e-[^\/]+\/)([^\/?#]+)/) ||
                                   playerObj.pathname.match(/(\/e-[^\/]+\/)([^\/?#]+)/);
                if (embedMatch) {
                    apiUrl = `${playerObj.origin}${embedMatch[1]}getSources?id=${embedMatch[2]}`;
                }
            }
            return apiUrl;
        }

        /**
         * Poka-Yoke file saver (Blob URL + <a> download click with 2s safety timeout)
         */
        function saveSubtitleFile(filename, text, extension) {
            return new Promise((resolve) => {
                try {
                    const mimeType = extension === 'srt' ? 'application/x-subrip;charset=utf-8' : 'text/vtt;charset=utf-8';
                    const blob = new Blob([text], { type: mimeType });
                    const blobUrl = URL.createObjectURL(blob);

                    const h1 = document.querySelector('h1.film-name, .film-info h1, .anisc-detail .film-name, h1.title');
                    const rawTitle = h1 ? h1.innerText : document.title;
                    const seriesInfo = parseSeriesAndSeason(rawTitle, window.location.href);

                    // Sonarr compliant directory: Series Name/Season 01/Filename
                    const targetName = `${seriesInfo.seriesTitle}/${seriesInfo.seasonFolder}/${filename}`;
                    let completed = false;

                    const done = (status) => {
                        if (completed) return;
                        completed = true;
                        try { URL.revokeObjectURL(blobUrl); } catch(e){}
                        resolve(status);
                    };

                    setTimeout(() => done(true), 2000);

                    try {
                        if (typeof GM_download === 'function') {
                            GM_download({
                                url: blobUrl,
                                name: targetName,
                                onload: () => done(true),
                                onerror: () => {
                                    const a = document.createElement('a');
                                    a.href = blobUrl;
                                    a.download = filename;
                                    document.body.appendChild(a);
                                    a.click();
                                    document.body.removeChild(a);
                                    done(true);
                                }
                            });
                        } else {
                            const a = document.createElement('a');
                            a.href = blobUrl;
                            a.download = filename;
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                            done(true);
                        }
                    } catch (err) {
                        const a = document.createElement('a');
                        a.href = blobUrl;
                        a.download = filename;
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                        done(true);
                    }
                } catch (e) {
                    resolve(false);
                }
            });
        }

        // ──────────────────────────────────────────────────────────────────────
        // 5. Bulk Download Logic (Multi-Language, Multi-Page & Multi-Server Fail-Over)
        // ──────────────────────────────────────────────────────────────────────

        async function startBulkDownload() {
            const statusEl = uiPanel.querySelector('.ani-sub-bulk-status');
            const actionBtn = uiPanel.querySelector('.ani-sub-bulk-btn');

            if (bulkDownloading) {
                bulkCancel = true;
                return;
            }

            statusEl.innerText = 'Đang tải danh sách tập...';
            const allEpisodes = await fetchAllEpisodesList();

            if (allEpisodes.length === 0) {
                alert('Không tìm thấy danh sách tập phim. Vui lòng chờ trang load hoặc bấm phát video.');
                statusEl.innerText = `Bulk Download (${selectedLangMode.toUpperCase()})`;
                return;
            }

            let targetEpisodes = allEpisodes;
            if (selectedScope === 'current') {
                const currentDomSlugs = new Set(
                    Array.from(document.querySelectorAll('#w-episodes a[data-slug], .episodes a[data-slug]'))
                         .map(a => a.getAttribute('data-slug'))
                );
                targetEpisodes = allEpisodes.filter(ep => currentDomSlugs.has(ep.slug));
            } else if (selectedScope === 'custom') {
                targetEpisodes = parseCustomRanges(customRangeText, allEpisodes);
            }

            if (targetEpisodes.length === 0) {
                alert('Không có tập nào khớp với phạm vi đã chọn.');
                statusEl.innerText = `Bulk Download (${selectedLangMode.toUpperCase()})`;
                return;
            }

            bulkDownloading = true;
            bulkCancel = false;

            actionBtn.innerText = 'Dừng';
            actionBtn.style.background = '#e53935';

            let index = 0;
            const successfulDls = [];
            const failedDls = [];
            const currentMode = selectedLangMode;
            const currentFormat = selectedFormat;

            function updateStatus(text) {
                statusEl.innerText = text;
            }

            function finish() {
                bulkDownloading = false;
                actionBtn.innerText = 'Download All';
                actionBtn.style.background = 'linear-gradient(135deg, #ff5e62, #ff9966)';
                statusEl.innerText = `Bulk Download (${currentMode.toUpperCase()})`;

                const totalEpisodesCount = targetEpisodes.length;
                const successfulCount = successfulDls.length;
                const missingCount = totalEpisodesCount - successfulCount;

                if (bulkCancel) {
                    alert(`Tải hàng loạt đã bị dừng.\nTải thành công: ${successfulCount}/${totalEpisodesCount} tập.`);
                } else if (missingCount > 0) {
                    alert(`[CẢNH BÁO] Phát hiện tải thiếu phụ đề so với số lượng tập yêu cầu!\n` +
                          `- Tổng số tập mục tiêu: ${totalEpisodesCount} tập\n` +
                          `- Tải thành công: ${successfulCount} tập\n` +
                          `- Bị thiếu/Lỗi: ${missingCount} tập\n` +
                          `- Danh sách tập bị thiếu/lỗi: ${failedDls.join(', ')}`);
                } else {
                    alert(`Tải hoàn tất thành công 100% tất cả phụ đề (${successfulCount}/${totalEpisodesCount} tập)!`);
                }
            }

            async function downloadTracksSequentially(tracksToDownload, playerUrl, filenamePrefix, epNum) {
                const results = [];
                for (let i = 0; i < tracksToDownload.length; i++) {
                    if (bulkCancel) return results;
                    if (i > 0) {
                        const trackDelay = 800 + Math.random() * 800;
                        await new Promise(r => setTimeout(r, trackDelay));
                    }
                    const track = tracksToDownload[i];
                    updateStatus(`Ep ${epNum} (${i + 1}/${tracksToDownload.length})... [${index + 1}/${targetEpisodes.length}]`);

                    const ref = getSafeReferer(playerUrl);
                    let origin = '';
                    try { if (ref) origin = new URL(ref).origin; } catch (e) {}

                    const dlHeaders = { 'User-Agent': navigator.userAgent, 'Referer': ref };
                    if (origin) dlHeaders['Origin'] = origin;

                    const dlRes = await GM_xmlhttpRequestWithRetry({
                        method: 'GET',
                        url: track.url,
                        headers: dlHeaders
                    }, 2, 2000);

                    if (dlRes && dlRes.status === 200 && dlRes.responseText) {
                        let text = dlRes.responseText;
                        let extension = currentFormat === 'srt' ? 'srt' : 'vtt';

                        if (currentFormat === 'srt') {
                            const checkText = text.replace(/^\uFEFF/, '').trim();
                            if (checkText.startsWith('WEBVTT') || checkText.includes('-->')) {
                                text = convertVttToSrt(text);
                            }
                        }

                        const tagInfo = getTrackTagAndDisplay(track);
                        const langTag = tagInfo.tag;

                        // Clean Sonarr format: Anime - s01e01.es-LA.srt
                        let cleanFilename = `${filenamePrefix}.${langTag}.${extension}`.replace(/[\\/:*?"<>|]/g, '_');
                        const saved = await saveSubtitleFile(cleanFilename, text, extension);
                        results.push(saved);
                    } else {
                        results.push(false);
                    }
                }
                return results;
            }

            async function processNext() {
                if (bulkCancel) {
                    finish();
                    return;
                }
                if (index >= targetEpisodes.length) {
                    finish();
                    return;
                }

                const ep = targetEpisodes[index];
                const serverIds = ep.ids;
                const epNum = ep.slug;

                const animeTitle = getCleanAnimeFolderName();
                const epLabel = getEpisodeLabel(epNum, ep.title);
                const filenamePrefix = `${animeTitle} - ${epLabel}`;

                updateStatus(`[${index + 1}/${targetEpisodes.length}] Ep ${epNum}...`);
                updateBadge(epNum, 'Đang tải...', 'rgba(255, 152, 0, 0.2)', '#ff9800');

                // Active episode optimization
                const activeEpActive = document.querySelector('#w-episodes .ep-item.active, #w-episodes a.active, .episodes a.active');
                let isActiveEp = false;
                if (activeEpActive) {
                    const activeEpNum = activeEpActive.getAttribute('data-slug') || '';
                    if (activeEpNum && String(activeEpNum) === String(epNum)) {
                        isActiveEp = true;
                    }
                }

                if (isActiveEp && detectedTracks.length > 0) {
                    const matchedTracks = filterTracksByMode(detectedTracks, currentMode);
                    if (matchedTracks.length > 0) {
                        const playerIframe = document.querySelector('iframe[src*="megaplay.buzz"]') ||
                                             document.querySelector('iframe[src*="megacloud.tv"]') ||
                                             document.querySelector('iframe[src*="rapidcloud.cc"]') ||
                                             document.querySelector('iframe');
                        const playerUrl = playerIframe?.src || window.location.href;

                        const results = await downloadTracksSequentially(matchedTracks, playerUrl, filenamePrefix, epNum);
                        const successCount = results.filter(r => r === true).length;
                        if (successCount > 0) {
                            successfulDls.push(epNum);
                            updateBadge(epNum, `${currentMode.toUpperCase()} (${successCount})`, 'rgba(76, 175, 80, 0.2)', '#4caf50');
                        } else {
                            failedDls.push(epNum);
                            updateBadge(epNum, 'Lỗi', 'rgba(244, 67, 54, 0.2)', '#f44336');
                        }
                        nextEpisode();
                        return;
                    }
                }

                try {
                    const serversUrl = `/ajax/server/list?servers=${serverIds}`;
                    const serverJson = await fetchInternal(serversUrl);
                    const html = serverJson.result || '';
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(html, 'text/html');

                    // Candidate server elements (prioritizing SUB)
                    let serverLis = Array.from(doc.querySelectorAll('.servers .type[data-type="sub"] li[data-link-id]'));
                    if (serverLis.length === 0) {
                        serverLis = Array.from(doc.querySelectorAll('li[data-link-id]'));
                    }

                    if (serverLis.length === 0) {
                        failedDls.push(epNum);
                        updateBadge(epNum, 'No Sub', 'rgba(244, 67, 54, 0.2)', '#f44336');
                        nextEpisode();
                        return;
                    }

                    // Sort candidates by priority
                    serverLis.sort((a, b) => {
                        const score = (li) => {
                            const txt = li.innerText;
                            if (txt.includes('Vidstream-2')) return 0;
                            if (txt.includes('Vidstream')) return 1;
                            if (txt.includes('HD-1')) return 2;
                            if (txt.includes('VidPlay-1')) return 3;
                            if (txt.includes('Megacloud')) return 4;
                            return 5;
                        };
                        return score(a) - score(b);
                    });

                    let resolvedSubtitles = false;

                    // Try candidate servers sequentially until subtitles are resolved
                    for (const candidateLi of serverLis) {
                        if (bulkCancel) break;

                        const linkId = candidateLi.getAttribute('data-link-id');
                        const getUrl = `/ajax/server?get=${linkId}`;
                        const getJson = await fetchInternal(getUrl);
                        let playerUrl = getJson.result;
                        if (playerUrl && typeof playerUrl === 'object') {
                            playerUrl = playerUrl.url;
                        }

                        if (!playerUrl) continue;

                        const apiUrl = await resolveSourcesApiUrl(playerUrl);
                        if (!apiUrl) continue;

                        const srcRes = await GM_xmlhttpRequestWithRetry({
                            method: 'GET',
                            url: apiUrl,
                            headers: {
                                'X-Requested-With': 'XMLHttpRequest',
                                'Referer': playerUrl
                            }
                        }, 2, 2000);

                        if (srcRes && srcRes.status === 200 && srcRes.responseText) {
                            try {
                                const srcJson = JSON.parse(srcRes.responseText);
                                const tracks = findSubtitlesInObject(srcJson);
                                const matchedTracks = filterTracksByMode(tracks, currentMode);

                                if (matchedTracks.length > 0) {
                                    const results = await downloadTracksSequentially(matchedTracks, playerUrl, filenamePrefix, epNum);
                                    const successCount = results.filter(r => r === true).length;
                                    if (successCount > 0) {
                                        successfulDls.push(epNum);
                                        updateBadge(epNum, `${currentMode.toUpperCase()} (${successCount})`, 'rgba(76, 175, 80, 0.2)', '#4caf50');
                                        resolvedSubtitles = true;
                                        break;
                                    }
                                }
                            } catch (e) {
                                console.warn('[Anikoto Subtitle v2] JSON parse failed for server', candidateLi.innerText);
                            }
                        }
                    }

                    if (!resolvedSubtitles) {
                        failedDls.push(epNum);
                        updateBadge(epNum, `No ${currentMode.toUpperCase()}`, 'rgba(244, 67, 54, 0.2)', '#f44336');
                    }

                    nextEpisode();

                } catch (e) {
                    failedDls.push(epNum);
                    updateBadge(epNum, 'Lỗi', 'rgba(244, 67, 54, 0.2)', '#f44336');
                    nextEpisode();
                }
            }

            function nextEpisode() {
                index++;
                const bulkDelay = 2000 + Math.random() * 1500;
                setTimeout(processNext, bulkDelay);
            }

            processNext();
        }

        async function downloadSingleSubtitle(track, forceFormat) {
            const headers = { 'User-Agent': navigator.userAgent };
            let rawReferer = track.referer;
            if (!rawReferer) {
                const playerIframe = document.querySelector('iframe[src*="megaplay.buzz"]') ||
                                     document.querySelector('iframe[src*="megacloud.tv"]') ||
                                     document.querySelector('iframe[src*="rapidcloud.cc"]') ||
                                     document.querySelector('iframe');
                if (playerIframe && playerIframe.src) rawReferer = playerIframe.src;
            }

            if (rawReferer) {
                const ref = getSafeReferer(rawReferer);
                headers["Referer"] = ref;
                try { headers["Origin"] = new URL(ref).origin; } catch (e) {}
            }

            const response = await GM_xmlhttpRequestWithRetry({
                method: "GET",
                url: track.url,
                headers: headers
            }, 2, 2000);

            if (response && response.status === 200 && response.responseText) {
                try {
                    let text = response.responseText;
                    let extension = forceFormat === 'srt' ? 'srt' : 'vtt';

                    if (forceFormat === 'srt') {
                        const checkText = text.replace(/^\uFEFF/, '').trim();
                        if (checkText.startsWith('WEBVTT') || checkText.includes('-->')) {
                            text = convertVttToSrt(text);
                        }
                    }

                    const tagInfo = getTrackTagAndDisplay(track);
                    const epTitle = getEpisodeTitle();
                    const cleanFilename = `${epTitle}.${tagInfo.tag}.${extension}`.replace(/[\\/:*?"<>|]/g, '_');

                    await saveSubtitleFile(cleanFilename, text, extension);
                    console.log('[Anikoto Subtitle v2] Single download complete:', cleanFilename);
                } catch (e) {
                    alert('Lỗi xử lý file subtitle: ' + e.message);
                }
            } else {
                alert('Lỗi mạng khi tải file phụ đề.');
            }
        }

        // ──────────────────────────────────────────────────────────────────────
        // 7. Modern UI Dashboard Construction
        // ──────────────────────────────────────────────────────────────────────

        function createUI() {
            if (uiButton) return;

            const style = document.createElement('style');
            style.innerHTML = `
                .ani-sub-btn-v2 {
                    position: fixed;
                    bottom: 25px;
                    right: 25px;
                    width: 54px;
                    height: 54px;
                    border-radius: 50%;
                    background: linear-gradient(135deg, #ff5e62, #ff9966);
                    color: white;
                    border: none;
                    box-shadow: 0 4px 18px rgba(255, 94, 98, 0.4);
                    cursor: pointer;
                    z-index: 999999;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-weight: bold;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    transition: transform 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275), box-shadow 0.2s;
                }
                .ani-sub-btn-v2:hover {
                    transform: scale(1.08);
                    box-shadow: 0 6px 24px rgba(255, 94, 98, 0.6);
                }
                .ani-sub-btn-v2 svg {
                    width: 26px;
                    height: 26px;
                    fill: white;
                }
                .ani-sub-panel-v2 {
                    position: fixed;
                    bottom: 90px;
                    right: 25px;
                    width: 360px;
                    max-height: 560px;
                    background: rgba(18, 20, 24, 0.96);
                    backdrop-filter: blur(14px);
                    border: 1px solid rgba(255, 255, 255, 0.12);
                    border-radius: 14px;
                    box-shadow: 0 16px 40px rgba(0,0,0,0.6);
                    z-index: 999999;
                    display: none;
                    flex-direction: column;
                    overflow: hidden;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    color: #e2e8f0;
                }
                .ani-sub-header-v2 {
                    padding: 12px 16px;
                    background: rgba(255, 255, 255, 0.04);
                    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    font-weight: 700;
                    font-size: 13.5px;
                    letter-spacing: 0.3px;
                }
                .ani-sub-close-v2 {
                    cursor: pointer;
                    opacity: 0.7;
                    font-size: 15px;
                    transition: opacity 0.2s;
                }
                .ani-sub-close-v2:hover {
                    opacity: 1;
                    color: #ff5e62;
                }
                .ani-sub-ctrl-grid {
                    padding: 10px 14px;
                    background: rgba(255, 255, 255, 0.02);
                    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 8px;
                }
                .ani-sub-scope-row {
                    padding: 8px 14px;
                    background: rgba(255, 255, 255, 0.01);
                    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
                    display: flex;
                    flex-direction: column;
                    gap: 6px;
                }
                .ani-sub-select {
                    width: 100%;
                    padding: 5px 8px;
                    background: #252830;
                    border: 1px solid #3c404d;
                    border-radius: 6px;
                    color: #fff;
                    font-size: 11.5px;
                    font-weight: 600;
                    outline: none;
                    cursor: pointer;
                }
                .ani-sub-select:focus {
                    border-color: #ff9966;
                }
                .ani-sub-input {
                    width: 100%;
                    padding: 5px 8px;
                    background: #252830;
                    border: 1px solid #3c404d;
                    border-radius: 6px;
                    color: #fff;
                    font-size: 11.5px;
                    outline: none;
                    box-sizing: border-box;
                }
                .ani-sub-input:focus {
                    border-color: #ff9966;
                }
                .ani-sub-bulk-bar {
                    padding: 10px 14px;
                    background: rgba(255, 94, 98, 0.06);
                    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                }
                .ani-sub-bulk-btn {
                    padding: 6px 14px;
                    border-radius: 6px;
                    border: none;
                    background: linear-gradient(135deg, #ff5e62, #ff9966);
                    color: #fff;
                    font-size: 12px;
                    font-weight: 700;
                    cursor: pointer;
                    transition: transform 0.15s, opacity 0.2s;
                }
                .ani-sub-bulk-btn:hover {
                    opacity: 0.92;
                    transform: translateY(-1px);
                }
                .ani-sub-list-v2 {
                    overflow-y: auto;
                    padding: 6px 0;
                    flex: 1;
                    max-height: 240px;
                }
                .ani-sub-item-v2 {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 8px 14px;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.03);
                    transition: background 0.15s;
                }
                .ani-sub-item-v2:hover {
                    background: rgba(255, 255, 255, 0.05);
                }
                .ani-sub-tag {
                    font-size: 10px;
                    font-weight: 800;
                    padding: 2px 6px;
                    border-radius: 4px;
                    margin-right: 6px;
                    display: inline-block;
                }
                .ani-sub-name {
                    font-size: 12px;
                    font-weight: 500;
                    max-width: 160px;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }
                .ani-sub-actions-v2 {
                    display: flex;
                    gap: 5px;
                }
                .ani-sub-pill-btn {
                    padding: 4px 8px;
                    border-radius: 4px;
                    border: none;
                    background: #2d3139;
                    color: #cbd5e1;
                    font-size: 11px;
                    font-weight: 700;
                    cursor: pointer;
                    transition: all 0.15s;
                }
                .ani-sub-pill-btn:hover {
                    background: #3f4450;
                    color: #fff;
                }
                .ani-sub-pill-btn.srt {
                    background: rgba(255, 94, 98, 0.2);
                    color: #ff8a80;
                    border: 1px solid rgba(255, 94, 98, 0.3);
                }
                .ani-sub-pill-btn.srt:hover {
                    background: #ff5e62;
                    color: #fff;
                }
                .ani-sub-empty-v2 {
                    padding: 24px 16px;
                    text-align: center;
                    color: #94a3b8;
                    font-size: 12px;
                    line-height: 1.5;
                }
            `;
            document.head.appendChild(style);

            // Button
            uiButton = document.createElement('button');
            uiButton.className = 'ani-sub-btn-v2';
            uiButton.title = 'Anikoto Subtitle & Video Downloader v2';
            uiButton.innerHTML = `
                <svg viewBox="0 0 24 24">
                    <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/>
                </svg>
            `;
            document.body.appendChild(uiButton);

            // Panel
            uiPanel = document.createElement('div');
            uiPanel.className = 'ani-sub-panel-v2';
            uiPanel.innerHTML = `
                <div class="ani-sub-header-v2">
                    <div style="display:flex; align-items:center; gap:6px;">
                        <span style="color:#ff9966;">★</span>
                        <span>Anikoto Downloader v2</span>
                    </div>
                    <span class="ani-sub-close-v2">✕</span>
                </div>

                <div class="ani-sub-ctrl-grid">
                    <div>
                        <div style="font-size: 10px; color: #94a3b8; margin-bottom: 3px; font-weight: 600;">NGÔN NGỮ BULK:</div>
                        <select class="ani-sub-select ani-sub-lang-select">
                            <option value="es-la" ${selectedLangMode === 'es-la' ? 'selected' : ''}>Spanish (es-LA) [Latin]</option>
                            <option value="en" ${selectedLangMode === 'en' ? 'selected' : ''}>English (EN)</option>
                            <option value="es-es" ${selectedLangMode === 'es-es' ? 'selected' : ''}>Spanish (es-ES) [Spain]</option>
                            <option value="es-all" ${selectedLangMode === 'es-all' ? 'selected' : ''}>Tất cả Spanish (LA + ES)</option>
                            <option value="multi_en_es" ${selectedLangMode === 'multi_en_es' ? 'selected' : ''}>Song ngữ (EN + es-LA)</option>
                            <option value="all" ${selectedLangMode === 'all' ? 'selected' : ''}>Tất cả Subtitles (All)</option>
                        </select>
                    </div>
                    <div>
                        <div style="font-size: 10px; color: #94a3b8; margin-bottom: 3px; font-weight: 600;">ĐỊNH DẠNG:</div>
                        <select class="ani-sub-select ani-sub-format-select">
                            <option value="srt" ${selectedFormat === 'srt' ? 'selected' : ''}>SRT (Khuyên dùng)</option>
                            <option value="vtt" ${selectedFormat === 'vtt' ? 'selected' : ''}>VTT (Gốc Web)</option>
                        </select>
                    </div>
                </div>

                <div class="ani-sub-scope-row">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-size: 10px; color: #94a3b8; font-weight: 600;">PHẠM VI TẬP TẢI VỀ:</span>
                        <select class="ani-sub-select ani-sub-scope-select" style="width: auto; padding: 2px 6px;">
                            <option value="all" ${selectedScope === 'all' ? 'selected' : ''}>Toàn bộ bộ phim (Tất cả trang)</option>
                            <option value="current" ${selectedScope === 'current' ? 'selected' : ''}>Trang đang xem (001-100...)</option>
                            <option value="custom" ${selectedScope === 'custom' ? 'selected' : ''}>Tùy chỉnh (vd: 1-50, 6, 100)</option>
                        </select>
                    </div>
                    <input type="text" class="ani-sub-input ani-sub-custom-input" placeholder="Nhập dải tập: 1-50, 55, 60-120" value="${customRangeText}" style="display: ${selectedScope === 'custom' ? 'block' : 'none'};">
                </div>

                <div class="ani-sub-bulk-bar">
                    <span class="ani-sub-bulk-status" style="font-size: 11.5px; font-weight: 700; color: #ff9966; max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">Bulk Download (${selectedLangMode.toUpperCase()})</span>
                    <button class="ani-sub-bulk-btn">Download All</button>
                </div>

                <div class="ani-sub-list-v2">
                    <div class="ani-sub-empty-v2">Chưa phát hiện phụ đề tập này.<br>Bấm phát video để nạp phụ đề.</div>
                </div>
            `;
            document.body.appendChild(uiPanel);

            // Toggle Panel
            uiButton.addEventListener('click', () => {
                uiPanel.style.display = uiPanel.style.display === 'flex' ? 'none' : 'flex';
            });

            uiPanel.querySelector('.ani-sub-close-v2').addEventListener('click', () => {
                uiPanel.style.display = 'none';
            });

            // Select change events
            const langSelect = uiPanel.querySelector('.ani-sub-lang-select');
            langSelect.addEventListener('change', (e) => {
                selectedLangMode = e.target.value;
                localStorage.setItem('anikoto_v2_lang_mode', selectedLangMode);
                const statusEl = uiPanel.querySelector('.ani-sub-bulk-status');
                if (!bulkDownloading) {
                    statusEl.innerText = `Bulk Download (${selectedLangMode.toUpperCase()})`;
                }
            });

            const formatSelect = uiPanel.querySelector('.ani-sub-format-select');
            formatSelect.addEventListener('change', (e) => {
                selectedFormat = e.target.value;
                localStorage.setItem('anikoto_v2_format', selectedFormat);
            });

            const scopeSelect = uiPanel.querySelector('.ani-sub-scope-select');
            const customInput = uiPanel.querySelector('.ani-sub-custom-input');
            scopeSelect.addEventListener('change', (e) => {
                selectedScope = e.target.value;
                localStorage.setItem('anikoto_v2_scope', selectedScope);
                customInput.style.display = selectedScope === 'custom' ? 'block' : 'none';
            });

            customInput.addEventListener('input', (e) => {
                customRangeText = e.target.value;
                localStorage.setItem('anikoto_v2_custom_range', customRangeText);
            });

            uiPanel.querySelector('.ani-sub-bulk-btn').addEventListener('click', startBulkDownload);
        }

        function updateUI() {
            createUI();

            const listEl = uiPanel.querySelector('.ani-sub-list-v2');
            if (detectedTracks.length === 0) {
                listEl.innerHTML = '<div class="ani-sub-empty-v2">Chưa phát hiện phụ đề tập này.<br>Bấm phát video để nạp phụ đề.</div>';
                return;
            }

            listEl.innerHTML = '';
            detectedTracks.forEach(track => {
                const tagInfo = getTrackTagAndDisplay(track);
                const item = document.createElement('div');
                item.className = 'ani-sub-item-v2';

                const left = document.createElement('div');
                left.style.display = 'flex';
                left.style.alignItems = 'center';

                const badge = document.createElement('span');
                badge.className = 'ani-sub-tag';
                badge.innerText = tagInfo.badge;
                badge.style.background = `${tagInfo.color}22`;
                badge.style.color = tagInfo.color;
                badge.style.border = `1px solid ${tagInfo.color}55`;

                const name = document.createElement('span');
                name.className = 'ani-sub-name';
                name.innerText = track.label;
                name.title = track.label;

                left.appendChild(badge);
                left.appendChild(name);

                const actions = document.createElement('div');
                actions.className = 'ani-sub-actions-v2';

                const srtBtn = document.createElement('button');
                srtBtn.className = 'ani-sub-pill-btn srt';
                srtBtn.innerText = 'SRT';
                srtBtn.onclick = () => downloadSingleSubtitle(track, 'srt');

                const vttBtn = document.createElement('button');
                vttBtn.className = 'ani-sub-pill-btn';
                vttBtn.innerText = 'VTT';
                vttBtn.onclick = () => downloadSingleSubtitle(track, 'vtt');

                actions.appendChild(srtBtn);
                actions.appendChild(vttBtn);

                item.appendChild(left);
                item.appendChild(actions);
                listEl.appendChild(item);
            });
        }

        const initInterval = setInterval(() => {
            if (document.body) {
                createUI();
                clearInterval(initInterval);
            }
        }, 500);
    } else {
        // IFRAME LOGIC (Runs on Megacloud, Rapidcloud, Megaplay, etc.)
        hookNetwork();
    }
})();
