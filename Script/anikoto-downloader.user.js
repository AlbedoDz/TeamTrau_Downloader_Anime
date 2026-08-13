// ==UserScript==
// @name         Anikoto Subtitle Downloader
// @namespace    http://tampermonkey.net/
// @version      1.1
// @description  Automatically detects and downloads subtitles (VTT/SRT) from anikototv.to player servers (Megacloud, Rapidcloud, etc.)
// @author       Antigravity
// @match        *://anikototv.to/*
// @match        *://*/*
// @grant        GM_download
// @grant        GM_xmlhttpRequest
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
        console.log('[Anikoto Subtitle] Main site script initialized.');
    } else {
        console.log('[Anikoto Subtitle] Player iframe script initialized on:', window.location.hostname);
    }



    // Helper: Recursively search JSON for video sources
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

    // Helper: Recursively search JSON for subtitles/tracks
    function findSubtitlesInObject(obj) {
        let tracks = [];
        if (!obj || typeof obj !== 'object') return tracks;

        if (Array.isArray(obj)) {
            for (let item of obj) {
                tracks = tracks.concat(findSubtitlesInObject(item));
            }
            return tracks;
        }

        // Check keys in the current object
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
                    // Check if it's an absolute URL
                    if (val.startsWith('http://') || val.startsWith('https://')) {
                        // Try to infer language from sibling properties or path
                        let label = 'Sub';
                        if (obj.label || obj.name || obj.language) {
                            label = obj.label || obj.name || obj.language;
                        } else {
                            // Extract label from URL path (e.g. /eng.vtt)
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

    // Helper: Extract label from URL
    function inferLabelFromUrl(url) {
        if (typeof url !== 'string') return 'Sub';
        const match = url.match(/\/([a-zA-Z0-9_-]+)\.(vtt|srt)/i);
        if (match && !/index|sub|track|play/i.test(match[1])) {
            return match[1].toUpperCase();
        }
        // Try to search query parameters
        try {
            const urlObj = new URL(url, window.location.href);
            const lang = urlObj.searchParams.get('lang') || urlObj.searchParams.get('language');
            if (lang) return lang.toUpperCase();
        } catch (e) {}
        return 'Sub';
    }

    // Helper: Convert VTT format to SRT format
    function convertVttToSrt(vttText) {
        if (!vttText) return '';
        
        // Normalize line breaks
        const cleanText = vttText.trim().replace(/\r\n/g, '\n').replace(/\r/g, '\n');
        const lines = cleanText.split('\n');
        
        let parsedCues = [];
        let currentCue = null;
        let insideHeader = true;

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            
            // 1. Skip WEBVTT header metadata, NOTE comments, or STYLE blocks fully
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
            
            // Check if it's a timestamp line e.g. "00:12.890 --> 00:17.020"
            const timestampMatch = line.match(/^(\d{2}:)?(\d{2}):(\d{2})[.,](\d{3})\s*-->\s*(\d{2}:)?(\d{2}):(\d{2})[.,](\d{3})/);
            
            if (timestampMatch) {
                // If there's a pending cue, save it
                if (currentCue) {
                    parsedCues.push(currentCue);
                }
                
                // Construct standard SRT timestamps: HH:MM:SS,mmm
                let startH = timestampMatch[1] ? timestampMatch[1].replace(':', '') : '00';
                let startM = timestampMatch[2];
                let startS = timestampMatch[3];
                let startMs = timestampMatch[4];
                
                let endH = timestampMatch[5] ? timestampMatch[5].replace(':', '') : '00';
                let endM = timestampMatch[6];
                let endS = timestampMatch[7];
                let endMs = timestampMatch[8];
                
                const formattedTime = `${startH}:${startM}:${startS},${startMs} --> ${endH}:${endM}:${endS},${endMs}`;
                
                currentCue = {
                    time: formattedTime,
                    text: []
                };
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

        // Build final SRT output string
        let srtOutput = [];
        let cueIndex = 1;
        for (const cue of parsedCues) {
            if (cue.text.length === 0) continue;
            let cueLines = cue.text;
            
            // Clean styling tags entirely to match Reference file (pure plain-text srt)
            for (let t = 0; t < cueLines.length; t++) {
                cueLines[t] = cueLines[t].replace(/<[^>]+>/g, '');
            }

            // Skip empty cues after cleaning
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

    // Helper: Trim Referer path to origin-only with a trailing slash to bypass CDN WAF blocks
    function getSafeReferer(url) {
        if (!url) return '';
        try {
            const parsed = new URL(url);
            return parsed.origin + '/';
        } catch (e) {
            return url;
        }
    }

    // Subtitle detection & network hook
    function hookNetwork() {
        const handleJSONResponse = (url, json) => {
            try {
                console.log('[Anikoto Subtitle] Scanning JSON response from:', url);
                const tracks = findSubtitlesInObject(json);
                const videoSources = findVideoSourcesInObject(json);

                if (tracks.length > 0 || videoSources.length > 0) {
                    // De-duplicate tracks by URL
                    const uniqueTracks = [];
                    const seen = new Set();
                    for (const t of tracks) {
                        if (!seen.has(t.url)) {
                            seen.add(t.url);
                            t.referer = window.location.href;
                            uniqueTracks.push(t);
                        }
                    }

                    // De-duplicate video sources by URL
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
                        console.log('[Anikoto Subtitle] Found subtitles/videos in iframe:', uniqueTracks, uniqueVideoSources);
                        window.top.postMessage({
                            type: 'ANIKOTO_SUBTITLES_DETECTED',
                            tracks: uniqueTracks,
                            videoSources: uniqueVideoSources
                        }, '*');
                    }
                }
            } catch (e) {
                console.error('[Subtitle Downloader] Error parsing JSON response', e);
            }
        };

        console.log('[Anikoto Subtitle] Network hook registered.');
        // Hook Fetch
        const originalFetch = window.fetch;
        window.fetch = async function(...args) {
            const url = args[0];
            if (!isMainSite && typeof url === 'string' && (url.includes('.vtt') || url.includes('.srt') || url.includes('lostproject.club'))) {
                const label = inferLabelFromUrl(url);
                console.log('[Anikoto Subtitle] Intercepted VTT request in Fetch:', url);
                window.top.postMessage({
                    type: 'ANIKOTO_SUBTITLES_DETECTED',
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
                console.log('[Anikoto Subtitle] Intercepted VTT request in XHR:', url);
                window.top.postMessage({
                    type: 'ANIKOTO_SUBTITLES_DETECTED',
                    tracks: [{ url: url, label: label, lang: label.toLowerCase(), referer: window.location.href }]
                }, '*');
            }
            return originalOpen.call(this, method, url, ...args);
        };

        const originalSend = XMLHttpRequest.prototype.send;
        XMLHttpRequest.prototype.send = function(...args) {
            this.addEventListener('load', function() {
                try {
                    // Try parsing JSON regardless of Content-Type header
                    const data = JSON.parse(this.responseText);
                    handleJSONResponse(this._url, data);
                } catch (e) {}
            });
            return originalSend.apply(this, args);
        };
    }

    // MAIN SITE LOGIC (Runs on anikototv.to)
    if (isMainSite) {
        let detectedTracks = [];
        let detectedVideoSources = [];
        let uiPanel = null;
        let uiButton = null;
        let bulkDownloading = false;
        let bulkCancel = false;
        let isScanning = false;
        let cancelScan = false;
        let currentScanSessionId = 0;
        let autoScanEnabled = localStorage.getItem('anikoto_auto_scan') === 'true';

        // Hook network requests on main page to catch player URLs
        hookNetwork();

        // Listen for URL changes (episode switching) and reset tracks
        let lastUrl = window.location.href;
        setInterval(() => {
            if (window.location.href !== lastUrl) {
                lastUrl = window.location.href;
                detectedTracks = [];
                detectedVideoSources = [];
                updateUI();
                if (autoScanEnabled) {
                    setTimeout(preCheckEpisodes, 1500);
                }
            }
        }, 1000);

        // Listen for messages from iframes (as backup)
        window.addEventListener('message', function(event) {
            if (event.data && event.data.type === 'ANIKOTO_SUBTITLES_DETECTED') {
                const tracks = event.data.tracks;
                const videoSources = event.data.videoSources || [];
                console.log('[Anikoto Subtitle] Received tracks from iframe:', tracks, videoSources);
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

        const epSubtitleCounts = {};

        // Use GM_xmlhttpRequest for internal API calls on anikototv.to (runs via extension context to bypass Cloudflare)
        async function fetchInternal(url, retries = 4, delay = 5000) {
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

        // Grease/Violentmonkey GM_xmlhttpRequest wrapper with retries and exponential backoff
        function GM_xmlhttpRequestWithRetry(options, retries = 4, initialDelay = 5000) {
            return new Promise((resolve, reject) => {
                let attempt = 0;
                let currentDelay = initialDelay;

                function makeRequest() {
                    GM_xmlhttpRequest({
                        ...options,
                        onload: function(res) {
                            if (res.status === 429 || res.status === 403) {
                                if (attempt < retries - 1) {
                                    attempt++;
                                    console.warn(`[Anikoto Subtitle] GM_xmlhttpRequest Rate limited (HTTP ${res.status}) on ${options.url}. Retrying in ${currentDelay}ms...`);
                                    setTimeout(makeRequest, currentDelay);
                                    currentDelay *= 2;
                                } else {
                                    if (options.onload) options.onload(res);
                                    resolve(res);
                                }
                            } else {
                                if (options.onload) options.onload(res);
                                resolve(res);
                            }
                        },
                        onerror: function(err) {
                            if (attempt < retries - 1) {
                                attempt++;
                                console.warn(`[Anikoto Subtitle] GM_xmlhttpRequest Error on ${options.url}. Retrying in ${currentDelay}ms...`);
                                setTimeout(makeRequest, currentDelay);
                                currentDelay *= 2;
                            } else {
                                if (options.onerror) options.onerror(err);
                                reject(err);
                            }
                        },
                        ontimeout: function(err) {
                            if (attempt < retries - 1) {
                                attempt++;
                                console.warn(`[Anikoto Subtitle] GM_xmlhttpRequest Timeout on ${options.url}. Retrying in ${currentDelay}ms...`);
                                setTimeout(makeRequest, currentDelay);
                                currentDelay *= 2;
                            } else {
                                if (options.ontimeout) options.ontimeout(err);
                                reject(err);
                            }
                        }
                    });
                }

                makeRequest();
            });
        }

        function verifyTrack(track, playerUrl) {
            return new Promise((resolve) => {
                const ref = getSafeReferer(playerUrl || track.referer || window.location.origin);
                let origin = '';
                try {
                    origin = new URL(ref).origin;
                } catch (e) {}
                const headers = {
                    'User-Agent': navigator.userAgent,
                    'Referer': ref,
                    'Range': 'bytes=0-100'
                };
                if (origin) {
                    headers['Origin'] = origin;
                }
                GM_xmlhttpRequestWithRetry({
                    method: 'GET',
                    url: track.url,
                    timeout: 10000,
                    headers: headers,
                    onload: function(res) {
                        const isSuccess = res.status === 200 || res.status === 206;
                        if (isSuccess && res.responseText && (res.responseText.includes('WEBVTT') || res.responseText.includes('-->') || res.responseText.includes('1\n00:'))) {
                            resolve(true);
                        } else {
                            resolve(false);
                        }
                    },
                    ontimeout: function() {
                        resolve(false);
                    },
                    onerror: function() {
                        resolve(false);
                    }
                });
            });
        }

        function isEnglishTrack(track) {
            const label = (track.label || '').toLowerCase();
            const lang = (track.lang || '').toLowerCase();
            
            // List of non-English language keywords to reject
            const nonEngKeywords = [
                'spanish', 'espanol', 'castellano', 'esp',
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
                'finnish', 'suomi', 'fin',
                'norwegian', 'norsk', 'nor',
                'danish', 'dansk', 'dan',
                'greek', 'ellinika', 'gre',
                'korean', 'hangug', 'kor',
                'japanese', 'nihongo', 'jpn',
                'bengali', 'ben'
            ];

            // If the label contains any of these non-English keywords, reject it immediately
            // unless it also contains "english" (e.g. "French / English")
            if (nonEngKeywords.some(kw => label.includes(kw)) && !label.includes('english')) {
                return false;
            }
            
            // If the language code starts with any of these, reject it
            const nonEngLangs = ['es', 'fr', 'de', 'it', 'pt', 'sv', 'vi', 'ar', 'tr', 'hi', 'ru', 'zh', 'id', 'th', 'pl', 'nl', 'fi', 'no', 'da', 'el', 'ko', 'ja', 'ben'];
            if (nonEngLangs.some(l => lang.startsWith(l))) {
                return false;
            }

            const engRegex = /\b(en|eng|english)\b/i;
            const langRegex = /^(en|eng|english)([-_].*)?$/i;
            
            return engRegex.test(label) || langRegex.test(lang);
        }

        function getEpisodeLabel(a, epNum) {
            let epNumClean = epNum;
            if (epNumClean) {
                const match = epNumClean.match(/(?:ep|episode)[-_]?(\d+)/i);
                if (match) {
                    epNumClean = match[1];
                }
            }
            
            const cleanText = getCleanEpText(a, epNumClean);
            let epLabel = `Ep ${epNumClean}`;
            
            const cleanTextLower = cleanText.toLowerCase();
            const epNumInt = parseInt(epNumClean, 10);
            const isRedundant = cleanTextLower === `episode ${epNumClean}`.toLowerCase() ||
                                cleanTextLower === `ep ${epNumClean}`.toLowerCase() ||
                                (!isNaN(epNumInt) && (
                                    cleanTextLower === `episode ${epNumInt}`.toLowerCase() ||
                                    cleanTextLower === `ep ${epNumInt}`.toLowerCase()
                                ));
                                
            if (cleanText && !isRedundant) {
                epLabel += ` - ${cleanText}`;
            }
            return epLabel;
        }

        function copyToClipboard(text) {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                return navigator.clipboard.writeText(text);
            } else {
                const temp = document.createElement('textarea');
                temp.value = text;
                document.body.appendChild(temp);
                temp.select();
                document.execCommand('copy');
                document.body.removeChild(temp);
                return Promise.resolve();
            }
        }

        function get720pPlaylistUrl(masterM3u8Url, playerUrl) {
            return new Promise((resolve) => {
                if (!masterM3u8Url.toLowerCase().includes('.m3u8')) {
                    resolve(masterM3u8Url);
                    return;
                }
                
                const ref = getSafeReferer(playerUrl || masterM3u8Url);
                let origin = '';
                try {
                    origin = new URL(ref).origin;
                } catch (e) {}
                const headers = {
                    'User-Agent': navigator.userAgent,
                    'Referer': ref
                };
                if (origin) {
                    headers['Origin'] = origin;
                }

                GM_xmlhttpRequestWithRetry({
                    method: 'GET',
                    url: masterM3u8Url,
                    headers: headers,
                    onload: function(res) {
                        if (res.status !== 200 || !res.responseText) {
                            resolve(masterM3u8Url);
                            return;
                        }
                        
                        try {
                            const lines = res.responseText.split('\n');
                            let url720p = '';
                            let highestUrl = '';
                            let highestRes = 0;
                            
                            for (let i = 0; i < lines.length; i++) {
                                const line = lines[i].trim();
                                if (line.startsWith('#EXT-X-STREAM-INF') || line.startsWith('#EXT-STREAM-INF')) {
                                    const resMatch = line.match(/RESOLUTION=(\d+)x(\d+)/i);
                                    const nextLine = (lines[i + 1] || '').trim();
                                    if (nextLine && !nextLine.startsWith('#')) {
                                        let absoluteUrl = nextLine;
                                        if (!nextLine.startsWith('http://') && !nextLine.startsWith('https://')) {
                                            absoluteUrl = new URL(nextLine, masterM3u8Url).href;
                                        }
                                        
                                        if (resMatch) {
                                            const width = parseInt(resMatch[1], 10);
                                            const height = parseInt(resMatch[2], 10);
                                            
                                            if (height === 720) {
                                                url720p = absoluteUrl;
                                            }
                                            
                                            if (height > highestRes) {
                                                highestRes = height;
                                                highestUrl = absoluteUrl;
                                            }
                                        }
                                    }
                                }
                            }
                            
                            resolve(url720p || highestUrl || masterM3u8Url);
                        } catch (e) {
                            resolve(masterM3u8Url);
                        }
                    },
                    onerror: function() {
                        resolve(masterM3u8Url);
                    }
                });
            });
        }

        function parseMp4DownloadLinks(htmlText) {
            const parser = new DOMParser();
            const doc = parser.parseFromString(htmlText, 'text/html');
            const links = Array.from(doc.querySelectorAll('a[href]'));
            
            const results = [];
            links.forEach(a => {
                const href = a.getAttribute('href');
                if (!href) return;
                
                const text = (a.innerText || '').toLowerCase();
                
                let parentText = '';
                let parent = a.parentElement;
                while (parent && parent !== doc.body) {
                    parentText += ' ' + (parent.innerText || '');
                    parent = parent.parentElement;
                }
                parentText = parentText.toLowerCase();
                
                let resolution = 'auto';
                if (href.includes('1080') || text.includes('1080') || parentText.includes('1080')) {
                    resolution = '1080p';
                } else if (href.includes('720') || text.includes('720') || parentText.includes('720')) {
                    resolution = '720p';
                } else if (href.includes('480') || text.includes('480') || parentText.includes('480')) {
                    resolution = '480p';
                } else if (href.includes('360') || text.includes('360') || parentText.includes('360')) {
                    resolution = '360p';
                }
                
                const hrefLower = href.toLowerCase();
                const isLikelyVideo = hrefLower.includes('.mp4') || 
                                      hrefLower.includes('.mkv') || 
                                      hrefLower.includes('.ts') || 
                                      hrefLower.includes('redirect') || 
                                      hrefLower.includes('download') || 
                                      hrefLower.includes('googlevideo') || 
                                      hrefLower.includes('storage') || 
                                      hrefLower.includes('delivery') ||
                                      hrefLower.includes('stream');
                
                if (href.startsWith('http') && isLikelyVideo) {
                    results.push({
                        url: href,
                        resolution: resolution,
                        label: a.innerText.trim() || resolution
                    });
                }
            });
            return results;
        }

        async function resolveDirectMp4ForActiveEpisode() {
            let epActive = document.querySelector('#w-episodes .ep-item.active, #w-episodes a.active, .episodes a.active');
            if (!epActive) {
                epActive = document.querySelector('#w-episodes a.active, .episodes a.active');
            }
            if (!epActive) return null;

            const serverIds = epActive.getAttribute('data-ids');
            if (!serverIds) return null;

            try {
                const serversUrl = `/ajax/server/list?servers=${serverIds}`;
                const serverJson = await fetchInternal(serversUrl);
                const html = serverJson.result || '';
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');
                const serverLis = Array.from(doc.querySelectorAll('li[data-link-id]'));
                
                const downloadLi = serverLis.find(li => li.innerText.toLowerCase().includes('download'));
                if (!downloadLi) return null;

                const linkId = downloadLi.getAttribute('data-link-id');
                const getUrl = `/ajax/server?get=${linkId}`;
                const getJson = await fetchInternal(getUrl);
                let downloadPageUrl = getJson.result;
                if (downloadPageUrl && typeof downloadPageUrl === 'object') {
                    downloadPageUrl = downloadPageUrl.url;
                }
                
                if (!downloadPageUrl) return null;
                
                console.log('[Anikoto Subtitle] Found download page URL:', downloadPageUrl);
                
                const pageRes = await GM_xmlhttpRequestWithRetry({
                    method: 'GET',
                    url: downloadPageUrl,
                    headers: {
                        'Referer': window.location.href,
                        'User-Agent': navigator.userAgent
                    }
                });
                
                if (pageRes.status !== 200) return null;
                
                const mp4Links = parseMp4DownloadLinks(pageRes.responseText);
                console.log('[Anikoto Subtitle] Parsed MP4 links:', mp4Links);
                
                return mp4Links;
            } catch (e) {
                console.error('[Anikoto Subtitle] Error resolving direct MP4:', e);
                return null;
            }
        }

        function updateBadge(epNum, text, bg, color) {
            const a = document.querySelector(`#w-episodes a[data-slug="${epNum}"], .episodes a[data-slug="${epNum}"]`);
            if (a) {
                let badge = a.querySelector('.ani-sub-badge');
                if (!badge) {
                    badge = document.createElement('span');
                    badge.className = 'ani-sub-badge';
                    badge.style.cssText = 'margin-left: 8px; font-size: 10px; padding: 2px 6px; border-radius: 4px; font-weight: bold; transition: all 0.3s;';
                    a.appendChild(badge);
                }
                badge.innerText = text;
                badge.style.background = bg;
                badge.style.color = color;
            }
        }

        function preCheckEpisodes() {
            const epLinks = Array.from(document.querySelectorAll('#w-episodes a, .episodes a'))
                .filter(a => a.getAttribute('data-ids'));
            
            if (epLinks.length === 0) {
                setTimeout(preCheckEpisodes, 1000);
                return;
            }

            console.log('[Anikoto Subtitle] Starting background pre-check for episodes...');
            isScanning = true;
            cancelScan = false;
            const sessionId = ++currentScanSessionId;
            let index = 0;

            async function checkNext() {
                if (cancelScan || sessionId !== currentScanSessionId) {
                    console.log('[Anikoto Subtitle] Pre-check scan cancelled or superseded. Session:', sessionId);
                    isScanning = false;
                    return;
                }
                if (index >= epLinks.length) {
                    console.log('[Anikoto Subtitle] Pre-check complete. Counts:', epSubtitleCounts);
                    isScanning = false;
                    return;
                }

                const a = epLinks[index];
                const serverIds = a.getAttribute('data-ids');
                const epNum = a.getAttribute('data-slug') || (index + 1);

                updateBadge(epNum, 'Scanning...', 'rgba(255, 152, 0, 0.2)', '#ff9800');

                try {
                    const serversUrl = `/ajax/server/list?servers=${serverIds}`;
                    const serverJson = await fetchInternal(serversUrl);
                    const html = serverJson.result || '';
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(html, 'text/html');
                    const serverLis = Array.from(doc.querySelectorAll('li[data-link-id]'));

                    if (serverLis.length === 0) {
                        updateBadge(epNum, 'No Sub', 'rgba(244, 67, 54, 0.2)', '#f44336');
                        epSubtitleCounts[epNum] = 0;
                        continueCheck();
                        return;
                    }

                    let selectedLi = serverLis.find(li => li.innerText.includes('HD-1'));
                    if (!selectedLi) selectedLi = serverLis.find(li => li.innerText.includes('Vidstream'));
                    if (!selectedLi) selectedLi = serverLis[0];

                    const linkId = selectedLi.getAttribute('data-link-id');
                    const getUrl = `/ajax/server?get=${linkId}`;
                    const getJson = await fetchInternal(getUrl);
                    let playerUrl = getJson.result;
                    if (playerUrl && typeof playerUrl === 'object') {
                        playerUrl = playerUrl.url;
                    }

                    if (!playerUrl) {
                        updateBadge(epNum, 'No Sub', 'rgba(244, 67, 54, 0.2)', '#f44336');
                        epSubtitleCounts[epNum] = 0;
                        continueCheck();
                        return;
                    }

                    let apiUrl = '';
                    const playerObj = new URL(playerUrl);
                    const streamMatch = playerObj.pathname.match(/\/stream\/s-\d+\/(\d+)/);
                    if (streamMatch) {
                        apiUrl = `${playerObj.origin}/stream/getSources?id=${streamMatch[1]}`;
                    } else if (playerObj.pathname.includes('getSources') || playerObj.pathname.includes('sources')) {
                        apiUrl = playerUrl;
                    }

                    if (!apiUrl) {
                        updateBadge(epNum, 'No Sub', 'rgba(244, 67, 54, 0.2)', '#f44336');
                        epSubtitleCounts[epNum] = 0;
                        continueCheck();
                        return;
                    }

                    GM_xmlhttpRequestWithRetry({
                        method: 'GET',
                        url: apiUrl,
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                            'Referer': playerUrl
                        },
                        onload: async function(srcRes) {
                            if (cancelScan || sessionId !== currentScanSessionId) {
                                isScanning = false;
                                return;
                            }
                            if (srcRes.status !== 200) {
                                updateBadge(epNum, 'Error', 'rgba(244, 67, 54, 0.2)', '#f44336');
                                epSubtitleCounts[epNum] = 0;
                                continueCheck();
                                return;
                            }

                            try {
                                const srcJson = JSON.parse(srcRes.responseText);
                                const tracks = findSubtitlesInObject(srcJson);

                                const enTracks = tracks.filter(isEnglishTrack);

                                if (enTracks.length === 0) {
                                    updateBadge(epNum, 'No Sub', 'rgba(244, 67, 54, 0.2)', '#f44336');
                                    epSubtitleCounts[epNum] = 0;
                                    continueCheck();
                                    return;
                                }

                                // Perform verification for each track sequentially with a delay to avoid rate limit / spam
                                const results = [];
                                for (let i = 0; i < enTracks.length; i++) {
                                    if (cancelScan || sessionId !== currentScanSessionId) {
                                        isScanning = false;
                                        return;
                                    }
                                    if (i > 0) {
                                        const verifyDelay = 1200 + Math.random() * 1300;
                                        await new Promise(r => setTimeout(r, verifyDelay));
                                    }
                                    const isValid = await verifyTrack(enTracks[i], playerUrl);
                                    results.push(isValid);
                                }

                                const validTracks = enTracks.filter((_, idx) => results[idx]);
                                const count = validTracks.length;
                                epSubtitleCounts[epNum] = count;

                                if (count > 0) {
                                    updateBadge(epNum, `EN (${count})`, 'rgba(76, 175, 80, 0.2)', '#4caf50');
                                } else {
                                    updateBadge(epNum, 'No Sub', 'rgba(244, 67, 54, 0.2)', '#f44336');
                                }
                            } catch (e) {
                                updateBadge(epNum, 'Error', 'rgba(244, 67, 54, 0.2)', '#f44336');
                                epSubtitleCounts[epNum] = 0;
                            }
                            continueCheck();
                        },
                        onerror: function() {
                            if (cancelScan || sessionId !== currentScanSessionId) {
                                isScanning = false;
                                return;
                            }
                            updateBadge(epNum, 'Error', 'rgba(244, 67, 54, 0.2)', '#f44336');
                            epSubtitleCounts[epNum] = 0;
                            continueCheck();
                        }
                    });

                } catch (err) {
                    if (cancelScan || sessionId !== currentScanSessionId) {
                        isScanning = false;
                        return;
                    }
                    console.error('[Anikoto Subtitle] Pre-check failed for Ep', epNum, err);
                    updateBadge(epNum, 'Error', 'rgba(244, 67, 54, 0.2)', '#f44336');
                    epSubtitleCounts[epNum] = 0;
                    continueCheck();
                }
            }

            function continueCheck() {
                if (cancelScan || sessionId !== currentScanSessionId) {
                    isScanning = false;
                    return;
                }
                index++;
                const checkDelay = 5000 + Math.random() * 3000; // 5s to 8s randomized delay
                setTimeout(checkNext, checkDelay);
            }

            checkNext();
        }

        // Resolve player URLs and fetch tracks directly from main site (bypassing iframe sandbox)
        function resolvePlayerSubtitles(playerUrl) {
            console.log('[Anikoto Subtitle] Resolving player URL:', playerUrl);
            let apiUrl = '';
            
            try {
                const urlObj = new URL(playerUrl);
                
                // Case 1: Megaplay / stream patterns (e.g. megaplay.buzz/stream/s-5/170263/sub)
                const streamMatch = urlObj.pathname.match(/\/stream\/s-\d+\/(\d+)/);
                if (streamMatch) {
                    apiUrl = `${urlObj.origin}/stream/getSources?id=${streamMatch[1]}`;
                } 
                // Case 2: Megacloud / Rapidcloud embed patterns (e.g. megacloud.tv/embed-2/e-1/getSources?id=XYZ)
                else if (urlObj.pathname.includes('getSources') || urlObj.pathname.includes('sources')) {
                    apiUrl = playerUrl;
                }
                
                if (apiUrl) {
                    console.log('[Anikoto Subtitle] Requesting player sources API:', apiUrl);
                    GM_xmlhttpRequestWithRetry({
                        method: "GET",
                        url: apiUrl,
                        headers: {
                            "X-Requested-With": "XMLHttpRequest",
                            "Referer": playerUrl
                        },
                        onload: function(response) {
                            if (response.status !== 200) {
                                console.error('[Anikoto Subtitle] Player API response status error:', response.status);
                                return;
                            }
                            try {
                                const json = JSON.parse(response.responseText);
                                console.log('[Anikoto Subtitle] Received sources API response:', json);
                                
                                const tracks = findSubtitlesInObject(json);
                                tracks.forEach(t => t.referer = playerUrl);

                                const videoSources = findVideoSourcesInObject(json);
                                if (videoSources.length > 0) {
                                    videoSources.forEach(src => {
                                        if (!detectedVideoSources.some(s => s.url === src.url)) {
                                            detectedVideoSources.push(src);
                                        }
                                    });
                                }

                                if (tracks.length > 0 || videoSources.length > 0) {
                                    console.log('[Anikoto Subtitle] Successfully resolved tracks/videos:', tracks, videoSources);
                                    tracks.forEach(track => {
                                        if (!detectedTracks.some(t => t.url === track.url)) {
                                            detectedTracks.push(track);
                                        }
                                    });
                                    updateUI();
                                }
                            } catch (e) {
                                console.error('[Anikoto Subtitle] Error parsing API response:', e);
                            }
                        }
                    });
                }
            } catch (err) {
                console.error('[Anikoto Subtitle] Error resolving player:', err);
            }
        }

        // Helper: Get clean anime folder name
        function getCleanAnimeFolderName() {
            const animeTitle = document.querySelector('h1.title')?.innerText.trim() || 'Anime';
            return animeTitle.replace(/[^a-zA-Z0-9\s\-_]/g, '').replace(/\s+/g, ' ').trim();
        }

        // Helper: Extract clean episode label text without the count badges and leading numbers
        function getCleanEpText(a, epNum) {
            const temp = a.cloneNode(true);
            const badge = temp.querySelector('.ani-sub-badge');
            if (badge) badge.remove();
            
            const epNumEl = temp.querySelector('.ep-num');
            if (epNumEl) epNumEl.remove();
            
            let text = temp.innerText.replace(/\s+/g, ' ').trim();
            text = text.replace(/(EN \(\d+\)|No Sub|Error|Scanning\.\.\.)$/i, '').trim();
            
            if (epNum) {
                const epNumInt = parseInt(epNum, 10);
                const cleanNumPattern = isNaN(epNumInt) ? epNum : `(?:${epNum}|0*${epNumInt})`;
                
                const labelStartRegex = new RegExp(`^(?:ep(?:isode)?\\.?[-\\s:]*${cleanNumPattern}\\b|${cleanNumPattern}\\b)`, 'i');
                text = text.replace(labelStartRegex, '').trim();
                
                const labelEndRegex = new RegExp(`\\b(?:ep(?:isode)?\\.?[-\\s:]*${cleanNumPattern}|${cleanNumPattern})$`, 'i');
                text = text.replace(labelEndRegex, '').trim();
            }
            
            text = text.replace(/^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$/g, '').trim();
            return text.replace(/[^a-zA-Z0-9\s\-_]/g, '').trim();
        }

        // Get safe episode/anime title
        function getEpisodeTitle() {
            const animeTitle = getCleanAnimeFolderName();
            
            let epActive = document.querySelector('#w-episodes .ep-item.active, #w-episodes a.active, .episodes a.active');
            if (!epActive) {
                epActive = document.querySelector('#w-episodes a.active, .episodes a.active');
            }
            
            let epSlug = '';
            if (epActive) {
                epSlug = epActive.getAttribute('data-slug') || '';
            }
            if (!epSlug) {
                epSlug = document.querySelector('#w-report-ep-num')?.value || '';
            }

            let epNumClean = '01';
            if (epSlug) {
                const match = epSlug.match(/(?:ep|episode|ep-)?[-_]?(\d+)/i);
                if (match) {
                    epNumClean = match[1];
                } else if (/^\d+$/.test(epSlug)) {
                    epNumClean = epSlug;
                }
            }

            // Pad episode number to at least 2 digits (e.g., 26 -> 26, 9 -> 09)
            let paddedEp = epNumClean;
            if (paddedEp.length < 2) {
                paddedEp = '0' + paddedEp;
            }

            return `${animeTitle}-s01e${paddedEp}`;
        }

        function startBulkDownload() {
            cancelScan = true; // Signal background scanner to cancel immediately

            const epLinks = Array.from(document.querySelectorAll('#w-episodes a, .episodes a'))
                .filter(a => a.getAttribute('data-ids'));
            
            if (epLinks.length === 0) {
                alert('No episodes detected in sidebar. Please wait for page to load or start playing the video.');
                return;
            }

            const statusEl = uiPanel.querySelector('.ani-sub-bulk-status');
            const actionBtn = uiPanel.querySelector('.ani-sub-bulk-btn');

            if (bulkDownloading) {
                bulkCancel = true;
                return;
            }

            bulkDownloading = true;
            bulkCancel = false;

            actionBtn.innerText = 'Cancel';
            actionBtn.style.background = '#3a3b3c';

            let index = 0;
            const successfulDls = [];
            const failedDls = [];

            function updateStatus(text) {
                statusEl.innerText = text;
            }

            function finish() {
                bulkDownloading = false;
                actionBtn.innerText = 'Download All';
                actionBtn.style.background = 'linear-gradient(135deg, #ff5e62, #ff9966)';
                statusEl.innerText = 'Bulk Download (EN)';
                
                const totalEpisodesCount = epLinks.length;
                const successfulCount = successfulDls.length;
                const missingCount = totalEpisodesCount - successfulCount;
                
                if (bulkCancel) {
                    alert(`Tải hàng loạt đã bị hủy.\nTải thành công: ${successfulCount}/${totalEpisodesCount} tập.`);
                } else if (missingCount > 0) {
                    alert(`[CẢNH BÁO] Phát hiện tải thiếu phụ đề so với số lượng tập trên web!\n` +
                          `- Tổng số tập trên web: ${totalEpisodesCount} tập\n` +
                          `- Tải thành công: ${successfulCount} tập\n` +
                          `- Bị thiếu/Lỗi: ${missingCount} tập\n` +
                          `- Các tập bị thiếu/lỗi: ${failedDls.join(', ')}`);
                } else {
                    alert(`Tải hoàn tất thành công 100% tất cả phụ đề (${successfulCount}/${totalEpisodesCount} tập)!`);
                }
            }

            async function downloadTracksSequentially(tracksToDownload, playerUrl, playerObj, filenamePrefix, epNum) {
                const results = [];
                for (let i = 0; i < tracksToDownload.length; i++) {
                    if (bulkCancel) return results;
                    if (i > 0) {
                        const trackDelay = 1500 + Math.random() * 1500; // 1.5s to 3s delay between tracks
                        await new Promise(r => setTimeout(r, trackDelay));
                    }
                    const enTrack = tracksToDownload[i];
                    updateStatus(`Dl Ep ${epNum} (${i + 1}/${tracksToDownload.length})...`);
                    const success = await new Promise((resolveDl) => {
                        enTrack.referer = playerUrl;
                        const ref = getSafeReferer(playerUrl);
                        let origin = playerObj.origin;
                        try {
                            if (ref) {
                                origin = new URL(ref).origin;
                            }
                        } catch (e) {}
                        const dlHeaders = {
                            'User-Agent': navigator.userAgent,
                            'Referer': ref
                        };
                        if (origin) {
                            dlHeaders['Origin'] = origin;
                        }

                        GM_xmlhttpRequestWithRetry({
                            method: 'GET',
                            url: enTrack.url,
                            headers: dlHeaders,
                            onload: function(dlRes) {
                                if (dlRes.status !== 200) {
                                    resolveDl(false);
                                    return;
                                }
                                try {
                                    let text = dlRes.responseText;
                                    let extension = 'vtt';
                                    let mimeType = 'text/vtt';

                                    const isSrtUrl = enTrack.url.toLowerCase().includes('.srt');
                                    // If URL is VTT but we want to make sure SRT conversion works for bulk or single downloader
                                    if (isSrtUrl) {
                                        extension = 'srt';
                                        mimeType = 'application/x-subrip';
                                    }

                                    let labelSuffix = '';
                                    if (tracksToDownload.length > 1) {
                                        labelSuffix = ` - ${enTrack.label.replace(/[\\/:*?"<>|]/g, '_').trim()}`;
                                    }
                                    const cleanFilename = `${filenamePrefix}${labelSuffix}.${extension}`.replace(/[\\/:*?"<>|]/g, '_');
                                    const animeFolder = getCleanAnimeFolderName();
                                    const targetName = `${animeFolder}/${cleanFilename}`;
                                    const base64Data = btoa(unescape(encodeURIComponent(text)));
                                    const dataUrl = `data:${mimeType};base64,${base64Data}`;

                                    GM_download({
                                        url: dataUrl,
                                        name: targetName,
                                        onload: function() {
                                            resolveDl(true);
                                        },
                                        onerror: function() {
                                            const blob = new Blob([text], { type: mimeType });
                                            const blobUrl = URL.createObjectURL(blob);
                                            const dlLink = document.createElement('a');
                                            dlLink.href = blobUrl;
                                            dlLink.download = cleanFilename;
                                            document.body.appendChild(dlLink);
                                            dlLink.click();
                                            document.body.removeChild(dlLink);
                                            URL.revokeObjectURL(blobUrl);
                                            resolveDl(true);
                                        }
                                    });
                                } catch (e) {
                                    resolveDl(false);
                                }
                            },
                            onerror: function() {
                                resolveDl(false);
                            }
                        });
                    });
                    results.push(success);
                }
                return results;
            }

            async function processNext() {
                if (bulkCancel) {
                    finish();
                    return;
                }

                if (index >= epLinks.length) {
                    finish();
                    return;
                }

                const a = epLinks[index];
                const serverIds = a.getAttribute('data-ids');
                const epNum = a.getAttribute('data-slug') || (index + 1);
                
                const animeTitle = getCleanAnimeFolderName();
                const epLabel = getEpisodeLabel(a, epNum);
                const filenamePrefix = `${animeTitle} - ${epLabel}`;
                
                updateStatus(`Fetch Ep ${epNum} (${index + 1}/${epLinks.length})...`);
                updateBadge(epNum, 'Downloading...', 'rgba(255, 152, 0, 0.2)', '#ff9800');

                // Optimization: If this is the active episode and we already have detected subtitles, use them directly
                const activeEpActive = document.querySelector('#w-episodes .ep-item.active, #w-episodes a.active, .episodes a.active');
                let isActiveEp = false;
                if (activeEpActive) {
                    const activeEpNum = activeEpActive.getAttribute('data-slug') || '';
                    if (activeEpNum && String(activeEpNum) === String(epNum)) {
                        isActiveEp = true;
                    }
                }

                if (isActiveEp && detectedTracks.length > 0) {
                    const enTracks = detectedTracks.filter(isEnglishTrack);
                    if (enTracks.length > 0) {
                        console.log(`[Bulk Download] Using pre-detected tracks for active Ep ${epNum}`);
                        const playerIframe = document.querySelector('iframe[src*="megaplay.buzz"]') || 
                                             document.querySelector('iframe[src*="megacloud.tv"]') ||
                                             document.querySelector('iframe[src*="rapidcloud.cc"]') ||
                                             document.querySelector('iframe');
                        const playerUrl = playerIframe?.src || window.location.href;
                        let playerObj = window.location;
                        try { playerObj = new URL(playerUrl); } catch(e){}

                        downloadTracksSequentially(enTracks, playerUrl, playerObj, filenamePrefix, epNum).then(results => {
                            const successCount = results.filter(r => r === true).length;
                            if (successCount > 0) {
                                successfulDls.push(epNum);
                                updateBadge(epNum, `EN (${successCount})`, 'rgba(76, 175, 80, 0.2)', '#4caf50');
                            } else {
                                failedDls.push(epNum);
                                updateBadge(epNum, 'Error', 'rgba(244, 67, 54, 0.2)', '#f44336');
                            }
                            nextEpisode();
                        });
                        return;
                    }
                }

                try {
                    const serversUrl = `/ajax/server/list?servers=${serverIds}`;
                    const serverJson = await fetchInternal(serversUrl);
                    const html = serverJson.result || '';
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(html, 'text/html');
                    const serverLis = Array.from(doc.querySelectorAll('li[data-link-id]'));

                    if (serverLis.length === 0) {
                        console.warn(`[Bulk Download] No servers found for Ep ${epNum}`);
                        failedDls.push(epNum);
                        updateBadge(epNum, 'No Sub', 'rgba(244, 67, 54, 0.2)', '#f44336');
                        nextEpisode();
                        return;
                    }

                    let selectedLi = serverLis.find(li => li.innerText.includes('HD-1'));
                    if (!selectedLi) selectedLi = serverLis.find(li => li.innerText.includes('Vidstream'));
                    if (!selectedLi) selectedLi = serverLis[0];

                    const linkId = selectedLi.getAttribute('data-link-id');
                    const getUrl = `/ajax/server?get=${linkId}`;
                    const getJson = await fetchInternal(getUrl);
                    let playerUrl = getJson.result;
                    if (playerUrl && typeof playerUrl === 'object') {
                        playerUrl = playerUrl.url;
                    }

                    if (!playerUrl) {
                        console.warn(`[Bulk Download] Empty player URL for Ep ${epNum}`);
                        failedDls.push(epNum);
                        updateBadge(epNum, 'No Sub', 'rgba(244, 67, 54, 0.2)', '#f44336');
                        nextEpisode();
                        return;
                    }

                    let apiUrl = '';
                    const playerObj = new URL(playerUrl);
                    const streamMatch = playerObj.pathname.match(/\/stream\/s-\d+\/(\d+)/);
                    if (streamMatch) {
                        apiUrl = `${playerObj.origin}/stream/getSources?id=${streamMatch[1]}`;
                    } else if (playerObj.pathname.includes('getSources') || playerObj.pathname.includes('sources')) {
                        apiUrl = playerUrl;
                    }

                    if (!apiUrl) {
                        console.warn(`[Bulk Download] Could not resolve sources API for Ep ${epNum}`);
                        failedDls.push(epNum);
                        updateBadge(epNum, 'No Sub', 'rgba(244, 67, 54, 0.2)', '#f44336');
                        nextEpisode();
                        return;
                    }

                    GM_xmlhttpRequestWithRetry({
                        method: 'GET',
                        url: apiUrl,
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                            'Referer': playerUrl
                        },
                        onload: function(srcRes) {
                            if (srcRes.status !== 200) {
                                console.error(`[Bulk Download] API failed for Ep ${epNum}`);
                                failedDls.push(epNum);
                                updateBadge(epNum, 'Error', 'rgba(244, 67, 54, 0.2)', '#f44336');
                                nextEpisode();
                                return;
                            }

                            try {
                                const srcJson = JSON.parse(srcRes.responseText);
                                const tracks = findSubtitlesInObject(srcJson);

                                const enTracks = tracks.filter(isEnglishTrack);

                                if (enTracks.length === 0) {
                                    console.warn(`[Bulk Download] No English subtitle for Ep ${epNum}`);
                                    failedDls.push(epNum);
                                    updateBadge(epNum, 'No Sub', 'rgba(244, 67, 54, 0.2)', '#f44336');
                                    nextEpisode();
                                    return;
                                }

                                downloadTracksSequentially(enTracks, playerUrl, playerObj, filenamePrefix, epNum).then(results => {
                                    const successCount = results.filter(r => r === true).length;
                                    if (successCount > 0) {
                                        successfulDls.push(epNum);
                                        updateBadge(epNum, `EN (${successCount})`, 'rgba(76, 175, 80, 0.2)', '#4caf50');
                                    } else {
                                        failedDls.push(epNum);
                                        updateBadge(epNum, 'Error', 'rgba(244, 67, 54, 0.2)', '#f44336');
                                    }
                                    nextEpisode();
                                });
                            } catch (e) {
                                console.error(`[Bulk Download] Error parsing sources JSON for Ep ${epNum}`, e);
                                failedDls.push(epNum);
                                updateBadge(epNum, 'Error', 'rgba(244, 67, 54, 0.2)', '#f44336');
                                nextEpisode();
                            }
                        },
                        onerror: function() {
                            console.error(`[Bulk Download] Error calling sources API for Ep ${epNum}`);
                            failedDls.push(epNum);
                            updateBadge(epNum, 'Error', 'rgba(244, 67, 54, 0.2)', '#f44336');
                            nextEpisode();
                        }
                    });

                } catch (e) {
                    console.error(`[Bulk Download] Process failed for Ep ${epNum}`, e);
                    failedDls.push(epNum);
                    updateBadge(epNum, 'Error', 'rgba(244, 67, 54, 0.2)', '#f44336');
                    nextEpisode();
                }
            }

            function nextEpisode() {
                index++;
                const bulkDelay = 4000 + Math.random() * 3000; // 4s to 7s delay between episodes
                setTimeout(processNext, bulkDelay);
            }

            processNext();
        }

        function downloadSubtitle(track, forceFormat) {
            const headers = {
                "User-Agent": navigator.userAgent
            };
            let rawReferer = '';
            if (track.referer) {
                rawReferer = track.referer;
            } else {
                const playerIframe = document.querySelector('iframe[src*="megaplay.buzz"]') || 
                                     document.querySelector('iframe[src*="megacloud.tv"]') ||
                                     document.querySelector('iframe[src*="rapidcloud.cc"]') ||
                                     document.querySelector('iframe');
                if (playerIframe && playerIframe.src) {
                    rawReferer = playerIframe.src;
                }
            }
            if (rawReferer) {
                const ref = getSafeReferer(rawReferer);
                headers["Referer"] = ref;
                try {
                    headers["Origin"] = new URL(ref).origin;
                } catch (e) {}
            }

            GM_xmlhttpRequestWithRetry({
                method: "GET",
                url: track.url,
                headers: headers,
                onload: function(response) {
                    if (response.status !== 200) {
                        alert('Failed to download subtitle. Server returned status: ' + response.status);
                        return;
                    }
                    try {
                        let text = response.responseText;
                        let extension = 'vtt';
                        let mimeType = 'text/vtt';

                        const isSrtUrl = track.url.toLowerCase().includes('.srt');
                        const wantSrt = forceFormat === 'srt' || isSrtUrl;

                        if (wantSrt) {
                            extension = 'srt';
                            mimeType = 'application/x-subrip';
                            // Normalize text to check for WEBVTT (handle BOM, leading whitespace etc.)
                            const checkText = text.replace(/^\uFEFF/, '').trim();
                            if (!isSrtUrl && (checkText.startsWith('WEBVTT') || checkText.includes('-->'))) {
                                text = convertVttToSrt(text);
                            }
                        }

                        const englishTracks = detectedTracks.filter(isEnglishTrack);
                        let labelSuffix = '';
                        if (englishTracks.length > 1) {
                            labelSuffix = ` - ${track.label.replace(/[\\/:*?"<>|]/g, '_').trim()}`;
                        }
                        let cleanFilename = `${getEpisodeTitle()}${labelSuffix}.${extension}`.replace(/[\\/:*?"<>|]/g, '_');
                        const animeFolder = getCleanAnimeFolderName();
                        let targetName = `${animeFolder}/${cleanFilename}`;
                        const base64Data = btoa(unescape(encodeURIComponent(text)));
                        const dataUrl = `data:${mimeType};base64,${base64Data}`;

                        GM_download({
                            url: dataUrl,
                            name: targetName,
                            onload: function() {
                                console.log('[Anikoto Subtitle] Downloaded successfully to:', targetName);
                            },
                            onerror: function(err) {
                                console.error('[Anikoto Subtitle] GM_download failed, fallback to blob...', err);
                                const blob = new Blob([text], { type: mimeType });
                                const blobUrl = URL.createObjectURL(blob);
                                
                                const a = document.createElement('a');
                                a.href = blobUrl;
                                a.download = cleanFilename;
                                document.body.appendChild(a);
                                a.click();
                                document.body.removeChild(a);
                                URL.revokeObjectURL(blobUrl);
                            }
                        });
                    } catch (e) {
                        alert('Error downloading subtitles: ' + e.message);
                    }
                },
                onerror: function(err) {
                    alert('Failed to fetch subtitle file.');
                }
            });
        }

        function createUI() {
            if (uiButton) return;

            // Create styles
            const style = document.createElement('style');
            style.innerHTML = `
                .ani-sub-btn {
                    position: fixed;
                    bottom: 25px;
                    right: 25px;
                    width: 54px;
                    height: 54px;
                    border-radius: 50%;
                    background: linear-gradient(135deg, #ff5e62, #ff9966);
                    color: white;
                    border: none;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.3);
                    cursor: pointer;
                    z-index: 999999;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-weight: bold;
                    font-family: 'Nunito', sans-serif;
                    transition: transform 0.2s, box-shadow 0.2s;
                }
                .ani-sub-btn:hover {
                    transform: scale(1.1);
                    box-shadow: 0 6px 20px rgba(0,0,0,0.4);
                }
                .ani-sub-btn svg {
                    width: 24px;
                    height: 24px;
                    fill: white;
                }
                .ani-sub-panel {
                    position: fixed;
                    bottom: 90px;
                    right: 25px;
                    width: 320px;
                    max-height: 400px;
                    background: rgba(20, 20, 20, 0.95);
                    backdrop-filter: blur(10px);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 12px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.5);
                    z-index: 999999;
                    display: none;
                    flex-direction: column;
                    overflow: hidden;
                    font-family: 'Nunito', sans-serif;
                    color: #fff;
                }
                .ani-sub-header {
                    padding: 12px 16px;
                    background: rgba(255, 255, 255, 0.05);
                    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    font-weight: bold;
                    font-size: 14px;
                }
                .ani-sub-close {
                    cursor: pointer;
                    opacity: 0.7;
                    transition: opacity 0.2s;
                }
                .ani-sub-close:hover {
                    opacity: 1;
                }
                .ani-sub-list {
                    overflow-y: auto;
                    padding: 8px 0;
                    flex: 1;
                }
                .ani-sub-item {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 8px 16px;
                    transition: background 0.2s;
                }
                .ani-sub-item:hover {
                    background: rgba(255, 255, 255, 0.05);
                }
                .ani-sub-label {
                    font-size: 13px;
                    font-weight: 500;
                    max-width: 160px;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }
                .ani-sub-actions {
                    display: flex;
                    gap: 6px;
                }
                .ani-sub-dl-btn {
                    padding: 4px 8px;
                    border-radius: 4px;
                    border: none;
                    background: #3a3b3c;
                    color: #fff;
                    font-size: 11px;
                    font-weight: bold;
                    cursor: pointer;
                    transition: background 0.2s;
                }
                .ani-sub-dl-btn:hover {
                    background: #555;
                }
                .ani-sub-dl-btn.srt {
                    background: #ff5e62;
                }
                .ani-sub-dl-btn.srt:hover {
                    background: #ff474b;
                }
                .ani-sub-empty {
                    padding: 24px;
                    text-align: center;
                    color: #aaa;
                    font-size: 13px;
                }
            `;
            document.head.appendChild(style);

            // Floating button
            uiButton = document.createElement('button');
            uiButton.className = 'ani-sub-btn';
            uiButton.innerHTML = `
                <svg viewBox="0 0 24 24">
                    <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/>
                </svg>
            `;
            document.body.appendChild(uiButton);

            // Panel
            uiPanel = document.createElement('div');
            uiPanel.className = 'ani-sub-panel';
            uiPanel.innerHTML = `
                <div class="ani-sub-header">
                    <span>Subtitles Detected</span>
                    <span class="ani-sub-close">✖</span>
                </div>
                <div class="ani-sub-settings-section" style="padding: 8px 16px; border-bottom: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.01); display: flex; align-items: center; gap: 8px; font-size: 11px;">
                    <input type="checkbox" id="ani-sub-auto-scan" style="cursor: pointer;" ${autoScanEnabled ? 'checked' : ''}>
                    <label for="ani-sub-auto-scan" style="cursor: pointer; user-select: none; color: #aaa;">Tự động quét tập (Dễ bị chặn IP)</label>
                </div>
                <div class="ani-sub-bulk-section" style="padding: 10px 16px; border-bottom: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.02); display: flex; align-items: center; justify-content: space-between;">
                    <span class="ani-sub-bulk-status" style="font-size: 12px; font-weight: 600; color: #ff9966;">Bulk Download (EN)</span>
                    <button class="ani-sub-bulk-btn" style="padding: 4px 10px; border-radius: 4px; border: none; background: linear-gradient(135deg, #ff5e62, #ff9966); color: #fff; font-size: 11px; font-weight: bold; cursor: pointer; transition: background 0.2s;">Download All</button>
                </div>
                <div class="ani-sub-list">
                    <div class="ani-sub-empty">No subtitles detected yet.<br>Start playing video to trigger.</div>
                </div>
                <div class="ani-sub-video-section" style="padding: 10px 16px; border-top: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.02); display: none; flex-direction: column; gap: 8px;">
                    <div style="font-size: 12px; font-weight: 600; color: #4caf50; display: flex; align-items: center; justify-content: space-between;">
                        <span>Video Stream (720p/Auto)</span>
                        <span class="ani-sub-video-status" style="font-size: 10px; opacity: 0.8; color: #4caf50;">Detected</span>
                    </div>
                    <div style="display: flex; gap: 8px;">
                        <button class="ani-sub-video-dl-btn" style="flex: 1; padding: 6px; border-radius: 4px; border: none; background: linear-gradient(135deg, #4caf50, #81c784); color: #fff; font-size: 11px; font-weight: bold; cursor: pointer; transition: background 0.2s;">Download Video</button>
                        <button class="ani-sub-video-copy-btn" style="padding: 6px 12px; border-radius: 4px; border: none; background: #3a3b3c; color: #fff; font-size: 11px; font-weight: bold; cursor: pointer; transition: background 0.2s;">Copy Link</button>
                    </div>
                </div>
            `;
            document.body.appendChild(uiPanel);

            // Toggle Panel
            uiButton.addEventListener('click', () => {
                uiPanel.style.display = uiPanel.style.display === 'flex' ? 'none' : 'flex';
            });

            // Close button
            uiPanel.querySelector('.ani-sub-close').addEventListener('click', () => {
                uiPanel.style.display = 'none';
            });

            // Auto Scan Checkbox action
            const autoScanCheckbox = uiPanel.querySelector('#ani-sub-auto-scan');
            autoScanCheckbox.addEventListener('change', (e) => {
                autoScanEnabled = e.target.checked;
                localStorage.setItem('anikoto_auto_scan', autoScanEnabled ? 'true' : 'false');
                if (autoScanEnabled) {
                    preCheckEpisodes();
                } else {
                    currentScanSessionId++; // Cancel current scan session
                    // Remove all badges that are currently Scanning...
                    const badges = document.querySelectorAll('.ani-sub-badge');
                    badges.forEach(badge => {
                        if (badge.innerText === 'Scanning...') {
                            badge.remove();
                        }
                    });
                }
            });

            // Bulk Download action
            uiPanel.querySelector('.ani-sub-bulk-btn').addEventListener('click', startBulkDownload);

            // Video download actions
            const videoDlBtn = uiPanel.querySelector('.ani-sub-video-dl-btn');
            const videoCopyBtn = uiPanel.querySelector('.ani-sub-video-copy-btn');
            const videoStatus = uiPanel.querySelector('.ani-sub-video-status');

            const handleVideoAction = async (actionType) => {
                if (detectedVideoSources.length === 0) return;
                const source = detectedVideoSources[0];
                
                videoStatus.innerText = 'Resolving 720p...';
                videoStatus.style.color = '#ff9800';

                try {
                    // Try to resolve direct MP4 download links from the server list's Download page first
                    const mp4Links = await resolveDirectMp4ForActiveEpisode();
                    
                    if (mp4Links && mp4Links.length > 0) {
                        // Find best quality link, preferably 720p
                        let selectedLink = mp4Links.find(l => l.resolution === '720p');
                        if (!selectedLink) selectedLink = mp4Links.find(l => l.resolution === '1080p');
                        if (!selectedLink) selectedLink = mp4Links.find(l => l.resolution === '480p');
                        if (!selectedLink) selectedLink = mp4Links.find(l => l.resolution === '360p');
                        if (!selectedLink) selectedLink = mp4Links[0];
                        
                        if (actionType === 'download') {
                            videoStatus.innerText = 'Downloading...';
                            videoStatus.style.color = '#4caf50';
                            
                            const animeFolder = getCleanAnimeFolderName();
                            const epTitle = getEpisodeTitle();
                            const cleanFilename = `${epTitle}.mp4`.replace(/[\\/:*?"<>|]/g, '_');
                            const targetName = `${animeFolder}/${cleanFilename}`;
                            
                            console.log('[Anikoto Subtitle] Starting direct MP4 download:', selectedLink.url, 'to:', targetName);
                            
                            GM_download({
                                url: selectedLink.url,
                                name: targetName,
                                onload: function() {
                                    alert(`Tải video thành công: ${cleanFilename}`);
                                },
                                onerror: function(err) {
                                    console.error('[Anikoto Subtitle] GM_download failed, fallback to new tab:', err);
                                    window.open(selectedLink.url, '_blank');
                                }
                            });
                        } else if (actionType === 'copy') {
                            await copyToClipboard(selectedLink.url);
                            videoStatus.innerText = 'Copied MP4!';
                            videoStatus.style.color = '#4caf50';
                            alert(`Đường dẫn tải trực tiếp Video MP4 (${selectedLink.resolution}) đã được sao chép vào Clipboard!`);
                        }
                        
                        setTimeout(() => {
                            videoStatus.innerText = 'Detected';
                            videoStatus.style.color = '#4caf50';
                        }, 2500);
                        return;
                    }
                    
                    // Fallback to HLS playlist (.m3u8) if direct MP4 links could not be resolved
                    const resolvedUrl = await get720pPlaylistUrl(source.url, source.referer);
                    
                    if (actionType === 'download') {
                        videoStatus.innerText = 'Redirecting...';
                        videoStatus.style.color = '#4caf50';
                        
                        await copyToClipboard(resolvedUrl);
                        
                        const downloadUrl = `https://blog.luckly-mjw.cn/tool-show/m3u8-downloader/index.html?source=${resolvedUrl}`;
                        window.open(downloadUrl, '_blank');
                        
                        alert(
                            "HƯỚNG DẪN TẢI VIDEO (CORS LIMIT):\n\n" +
                            "Do chính sách bảo mật CORS của máy chủ video, trình duyệt mặc định sẽ chặn trang web m3u8-downloader tải các mảnh video.\n\n" +
                            "Để tải thành công, bạn có 3 lựa chọn đơn giản sau:\n" +
                            "1. Cài tiện ích mở rộng 'Allow CORS: Access-Control-Allow-Origin' trên Chrome/Edge và bật nó lên khi tải ở trang m3u8-downloader.\n" +
                            "2. (Khuyên dùng) Đường dẫn luồng video 720p đã được tự động COPY vào Clipboard của bạn. Hãy mở cmd/terminal và chạy lệnh sau để tải siêu tốc bằng yt-dlp:\n" +
                            "   yt-dlp \"" + resolvedUrl + "\"\n" +
                            "3. Dán liên kết m3u8 đã copy vào các tiện ích tải video như FetchV hoặc CoCoCut."
                        );
                    } else if (actionType === 'copy') {
                        await copyToClipboard(resolvedUrl);
                        videoStatus.innerText = 'Copied!';
                        videoStatus.style.color = '#4caf50';
                        alert("Đường dẫn luồng video 720p .m3u8 đã được sao chép vào Clipboard!");
                    }
                } catch (e) {
                    console.error('[Anikoto Subtitle] Video action failed:', e);
                    videoStatus.innerText = 'Error';
                    videoStatus.style.color = '#f44336';
                }

                setTimeout(() => {
                    videoStatus.innerText = 'Detected';
                    videoStatus.style.color = '#4caf50';
                }, 2500);
            };

            videoDlBtn.addEventListener('click', () => handleVideoAction('download'));
            videoCopyBtn.addEventListener('click', () => handleVideoAction('copy'));
        }

        function updateUI() {
            createUI();

            const videoSection = uiPanel.querySelector('.ani-sub-video-section');
            if (detectedVideoSources.length > 0) {
                videoSection.style.display = 'flex';
            } else {
                videoSection.style.display = 'none';
            }

            const listEl = uiPanel.querySelector('.ani-sub-list');
            if (detectedTracks.length === 0) {
                listEl.innerHTML = '<div class="ani-sub-empty">No subtitles detected yet.<br>Start playing video to trigger.</div>';
                return;
            }

            listEl.innerHTML = '';
            detectedTracks.forEach(track => {
                const item = document.createElement('div');
                item.className = 'ani-sub-item';
                
                const label = document.createElement('div');
                label.className = 'ani-sub-label';
                label.innerText = track.label;
                label.title = track.label;

                const actions = document.createElement('div');
                actions.className = 'ani-sub-actions';

                const isSrt = track.url.toLowerCase().includes('.srt');

                if (isSrt) {
                    const srtBtn = document.createElement('button');
                    srtBtn.className = 'ani-sub-dl-btn srt';
                    srtBtn.innerText = 'SRT';
                    srtBtn.onclick = () => downloadSubtitle(track, 'srt');
                    actions.appendChild(srtBtn);
                } else {
                    const vttBtn = document.createElement('button');
                    vttBtn.className = 'ani-sub-dl-btn vtt';
                    vttBtn.innerText = 'VTT';
                    vttBtn.onclick = () => downloadSubtitle(track, 'vtt');
                    actions.appendChild(vttBtn);

                    const srtBtn = document.createElement('button');
                    srtBtn.className = 'ani-sub-dl-btn srt';
                    srtBtn.innerText = 'SRT';
                    srtBtn.onclick = () => downloadSubtitle(track, 'srt');
                    actions.appendChild(srtBtn);
                }

                item.appendChild(label);
                item.appendChild(actions);
                listEl.appendChild(item);
            });
        }

        // Initialize UI check loop
        const initInterval = setInterval(() => {
            if (document.body) {
                createUI();
                clearInterval(initInterval);
                if (autoScanEnabled) {
                    preCheckEpisodes();
                }
            }
        }, 500);
    } else {
        // IFRAME LOGIC (Runs on Megacloud, Rapidcloud, etc.)
        hookNetwork();
    }
})();
