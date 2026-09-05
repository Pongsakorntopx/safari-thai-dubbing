/**
 * Safari AI Thai Video Dubber - 60-Second Paragraph-Level Batch Dubbing Engine (Unlock-TTS & JaiTTS Standards)
 * Includes Strict Gender Persona Alignment (ครับ/ค่ะ), Dynamic Register Adaptation, 1-Minute Initial Buffer,
 * and Pitch-Preserved Crystal-Clear Natural Speech Cadence (Zero Slow-Motion / Zero Stretching Distortion).
 */

(function () {
  'use strict';

  // --- Runtime State ---
  const state = {
    enabled: true,
    engine: 'qwen_tts',
    voice: 'qwen-thai-female',
    gender: 'female',
    style: 'auto',
    rate: '+0%',
    dubVolume: 1.0,
    duckVolume: 0.2,
    showSubtitles: false, // Default is OFF (ปิดเป็นค่าเริ่มต้น)
    backendUrl: 'http://127.0.0.1:8000',
    translationModel: 'qwen-max',
    customQwenKey: 'sk-ws-H.DDLIDRI.FjEo.MEYCIQClFrpLY4yP_rpWWLjU-jTAsiMqqOeXOoMLE3s-6K08lAIhAJB8ZZVuWXYGmzhIxp9RXsZY-2AP_7ywEQCOWuEAmz_s',

    // Playback & Queue State
    isDubbingActive: false,
    timedCues: [],
    currentVideoId: null,
    targetBufferSeconds: 180, // 180-Second (3-minute) Golden Buffer
    lastScheduledCue: null,
    nextSpeechTime: 0,
    syncInterval: null,
    liveObserver: null,
    subtitleHookAttached: false,
    audioCtx: null,
    audioGainNode: null,

    // UI HUD Controls
    isHUDMinimized: false,
    showSettingsModal: false,

    // Audio Ducking & Volume Restore
    originalVideoVolume: 1.0,
    isDucking: false,
  };

  const VOICES = [
    { id: 'qwen-thai-female', name: '👑 Alibaba Qwen-Max: หญิง (เปรมวดี • นุ่มนวล ไพเราะ สมจริง 100%)', engine: 'qwen_tts', gender: 'female' },
    { id: 'qwen-thai-male', name: '👑 Alibaba Qwen-Max: ชาย (นิวัฒน์ • ทุ้มนุ่ม มืออาชีพ สมจริง 100%)', engine: 'qwen_tts', gender: 'male' },
  ];

  const STYLES = [
    { id: 'auto', name: '🤖 ปรับอารมณ์และสไตล์ตามคลิปอัตโนมัติ (แนะนำ)' },
    { id: 'notebooklm', name: '🎙️ NotebookLM Audio Overview (เล่าเรื่องมีเสน่ห์ อบอุ่น)' },
    { id: 'casual', name: '🗣️ ยูทูบเบอร์ / เกม / กันเอง / กวนๆ' },
    { id: 'cinema', name: '🎬 หนัง / ซีรีส์ / อารมณ์สมจริง' },
    { id: 'podcast', name: '🎧 พอดแคสต์ / เล่าเรื่อง / รีวิว' },
    { id: 'formal', name: '📻 ทางการ / สารคดี / ข่าว' },
  ];

  // --- Dedicated Native HTML5 Audio Player Engine (100% Audible & Compatible on Safari macOS/iOS) ---
  let globalAudioPlayer = null;

  function getGlobalAudioPlayer() {
    if (!globalAudioPlayer) {
      globalAudioPlayer = document.getElementById('thai-dub-audio-player');
      if (!globalAudioPlayer) {
        globalAudioPlayer = document.createElement('audio');
        globalAudioPlayer.id = 'thai-dub-audio-player';
        globalAudioPlayer.style.display = 'none';
        globalAudioPlayer.preload = 'auto';
        (document.body || document.documentElement).appendChild(globalAudioPlayer);
      }
    }
    return globalAudioPlayer;
  }

  function base64ToBlobUrl(base64) {
    if (!base64) return '';
    try {
      const cleanBase64 = base64.replace(/^data:audio\/\w+;base64,/, '');
      const binaryStr = atob(cleanBase64);
      const len = binaryStr.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) {
        bytes[i] = binaryStr.charCodeAt(i);
      }
      const blob = new Blob([bytes], { type: 'audio/wav' });
      return URL.createObjectURL(blob);
    } catch (e) {
      console.warn('[ThaiDubbing] Blob conversion error, fallback to data URI:', e);
      return base64.startsWith('data:') ? base64 : `data:audio/wav;base64,${base64}`;
    }
  }

  let audioUnlocked = false;
  function unlockAudio() {
    if (audioUnlocked || state.isPlaying) return;
    try {
      const audio = getGlobalAudioPlayer();
      if (audio && audio.paused) {
        audioUnlocked = true;
      }
    } catch (e) {}
  }

  // --- Settings Loader & Realtime Sync ---
  async function loadSettings() {
    try {
      const data = await chrome.storage.local.get([
        'enabled',
        'engine',
        'voice',
        'gender',
        'style',
        'rate',
        'dubVolume',
        'duckVolume',
        'showSubtitles',
        'backendUrl',
        'customQwenKey',
        'translationModel',
        'isCollapsed',
      ]);
      if (data.enabled !== undefined) state.enabled = data.enabled;
      if (data.showSubtitles !== undefined) state.showSubtitles = data.showSubtitles;
      if (data.voice) {
        state.voice = data.voice;
        const vObj = VOICES.find((v) => v.id === data.voice);
        if (vObj) {
          state.engine = vObj.engine;
          state.gender = vObj.gender;
        }
      }
      if (data.gender) state.gender = data.gender;
      if (data.style) state.style = data.style;
      if (data.rate) state.rate = data.rate;
      if (data.dubVolume !== undefined) {
        state.dubVolume = data.dubVolume;
        if (state.audioGainNode) state.audioGainNode.gain.value = state.dubVolume;
      }
      if (data.duckVolume !== undefined) state.duckVolume = data.duckVolume;

      // Always default to Local Mac Daemon (http://127.0.0.1:8000)
      if (!data.backendUrl || data.backendUrl.includes('render.com')) {
        state.backendUrl = 'http://127.0.0.1:8000';
        chrome.storage.local.set({ backendUrl: 'http://127.0.0.1:8000' });
      } else {
        state.backendUrl = data.backendUrl;
      }
      state.backendUrl = state.backendUrl.replace(/\/+$/, '');

      const defaultQwenKey = 'sk-ws-H.DDLIDRI.FjEo.MEYCIQClFrpLY4yP_rpWWLjU-jTAsiMqqOeXOoMLE3s-6K08lAIhAJB8ZZVuWXYGmzhIxp9RXsZY-2AP_7ywEQCOWuEAmz_s';
      if (data.customQwenKey) {
        state.customQwenKey = data.customQwenKey;
      } else {
        state.customQwenKey = defaultQwenKey;
        saveSetting('customQwenKey', defaultQwenKey);
      }
      state.translationModel = data.translationModel || 'qwen-max';
      if (data.isCollapsed !== undefined) state.isCollapsed = data.isCollapsed;

      renderHUD();
    } catch (err) {
      console.error('[ThaiDubbing] Settings load error:', err);
    }
  }

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'local') {
      for (const [key, change] of Object.entries(changes)) {
        state[key] = change.newValue;
        if (key === 'voice') {
          const vObj = VOICES.find((v) => v.id === change.newValue);
          if (vObj) {
            state.engine = vObj.engine;
            state.gender = vObj.gender;
          }
        }
        if (key === 'showSubtitles') {
          state.showSubtitles = change.newValue;
          if (!state.showSubtitles) {
            clearCinemaSubtitle();
          }
        }
        if (key === 'dubVolume' && state.audioGainNode) {
          state.audioGainNode.gain.value = change.newValue;
        }
        if (key === 'enabled' && !change.newValue) {
          stopDubbing();
        }
      }
      renderHUD();
    }
  });

  function saveSetting(key, value) {
    state[key] = value;
    chrome.storage.local.set({ [key]: value });
  }

  // --- Helpers ---
  function base64ToArrayBuffer(base64) {
    const binary = atob(base64);
    const len = binary.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
  }

  function decodeAudioBuffer(ctx, arrayBuf) {
    return new Promise((resolve) => {
      if (!ctx || !arrayBuf || arrayBuf.byteLength === 0) {
        resolve(null);
        return;
      }
      try {
        const copy = arrayBuf.slice(0);
        ctx.decodeAudioData(
          copy,
          (buf) => resolve(buf),
          () => {
            try {
              ctx.decodeAudioData(arrayBuf.slice(0)).then(resolve).catch(() => resolve(null));
            } catch (e) {
              resolve(null);
            }
          }
        );
      } catch (err) {
        try {
          ctx.decodeAudioData(arrayBuf.slice(0)).then(resolve).catch(() => resolve(null));
        } catch (e) {
          resolve(null);
        }
      }
    });
  }

  function getVideoId() {
    const urlParams = new URLSearchParams(window.location.search);
    const v = urlParams.get('v');
    if (v) return v;
    const match = location.pathname.match(/\/(shorts|embed|v)\/([a-zA-Z0-9_-]{11})/);
    if (match) return match[2];
    return '';
  }

  function getVideoTitle() {
    const titleEl = document.querySelector('h1.ytd-watch-metadata') || document.querySelector('h1.title') || document.querySelector('title');
    return titleEl ? titleEl.textContent.trim() : document.title;
  }

  // --- Universal Same-Origin YouTube Subtitle Extractor (100% Reliable, Zero Block, No Bridge needed) ---
  const INNERTUBE_API_KEY = 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8';

  function parseXmlCues(rawXml) {
    if (!rawXml || !rawXml.trim()) return [];
    const cues = [];
    let cueId = 1;
    let currentCue = null;

    // Pattern 1: <p t="5759" d="4681" ...> ... </p>
    const pPattern = /<p\s+[^>]*?t="(\d+)"(?:\s+[^>]*?d="(\d+)")?[^>]*?>([\s\S]*?)<\/p>/gi;
    let match;
    let foundP = false;

    while ((match = pPattern.exec(rawXml)) !== null) {
      foundP = true;
      const tMs = parseInt(match[1], 10);
      const dMs = match[2] ? parseInt(match[2], 10) : 3000;
      const innerHtml = match[3];

      const text = innerHtml
        .replace(/<[^>]+>/g, '')
        .replace(/&amp;/g, '&')
        .replace(/&#39;/g, "'")
        .replace(/&quot;/g, '"')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/[\r\n]+/g, ' ')
        .trim();

      if (!text || text.startsWith('[')) continue;

      const start = parseFloat((tMs / 1000.0).toFixed(2));
      const dur = parseFloat((dMs / 1000.0).toFixed(2));
      const end = parseFloat((start + dur).toFixed(2));

      if (!currentCue) {
        currentCue = { id: cueId++, start, end, text };
      } else {
        const gap = start - currentCue.end;
        if (!currentCue.text.endsWith(text)) {
          currentCue.text += ' ' + text;
        }
        currentCue.end = Math.max(currentCue.end, end);

        // Merge into complete, natural semantic thoughts
        const isPunctuation = /[.!?。！？]["']?$/.test(currentCue.text);
        const isSpeechPause = gap > 0.9;
        const isMaxDuration = (currentCue.end - currentCue.start >= 8.0);

        if (isPunctuation || isSpeechPause || isMaxDuration) {
          cues.push(currentCue);
          currentCue = null;
        }
      }
    }
    if (currentCue) cues.push(currentCue);

    // Pattern 2: <text start="1.2" dur="3.4"> ... </text>
    if (!foundP || !cues.length) {
      const textPattern = /<text\s+[^>]*?start="([\d\.]+)"(?:\s+[^>]*?dur="([\d\.]+)")?[^>]*?>([\s\S]*?)<\/text>/gi;
      while ((match = textPattern.exec(rawXml)) !== null) {
        const start = parseFloat(parseFloat(match[1]).toFixed(2));
        const dur = match[2] ? parseFloat(parseFloat(match[2]).toFixed(2)) : 3.0;
        const end = parseFloat((start + dur).toFixed(2));
        const text = match[3]
          .replace(/<[^>]+>/g, '')
          .replace(/&amp;/g, '&')
          .replace(/&#39;/g, "'")
          .replace(/&quot;/g, '"')
          .replace(/&lt;/g, '<')
          .replace(/&gt;/g, '>')
          .replace(/[\r\n]+/g, ' ')
          .trim();

        if (!text || text.startsWith('[')) continue;

        if (!currentCue) {
          currentCue = { id: cueId++, start, end, text };
        } else {
          const gap = start - currentCue.end;
          if (!currentCue.text.endsWith(text)) {
            currentCue.text += ' ' + text;
          }
          currentCue.end = Math.max(currentCue.end, end);

          const isPunctuation = /[.!?。！？]["']?$/.test(currentCue.text);
          const isSpeechPause = gap > 0.9;
          const isMaxDuration = (currentCue.end - currentCue.start >= 8.0);

          if (isPunctuation || isSpeechPause || isMaxDuration) {
            cues.push(currentCue);
            currentCue = null;
          }
        }
      }
      if (currentCue) cues.push(currentCue);
    }

    return cues;
  }

  async function fetchYouTubeInnertubeDirect(videoId) {
    try {
      const cleanVid = videoId.split('&')[0].split('?')[0];
      console.log('[ThaiDubbing] Fetching YouTube subtitle metadata for video:', cleanVid);

      let captionTracks = [];

      // Stage 1: Inspect Native YouTube Player DOM API
      try {
        const player = document.getElementById('movie_player') || document.querySelector('.html5-video-player');
        if (player) {
          if (typeof player.getPlayerResponse === 'function') {
            const pData = player.getPlayerResponse();
            const trks = pData?.captions?.playerCaptionsTracklistRenderer?.captionTracks;
            if (Array.isArray(trks) && trks.length > 0) {
              captionTracks = trks;
              console.log('[ThaiDubbing] Found caption tracks via player.getPlayerResponse():', captionTracks.length);
            }
          }
          if (!captionTracks.length && typeof player.getOption === 'function') {
            const trkList = player.getOption('captions', 'tracklist');
            if (Array.isArray(trkList) && trkList.length > 0) {
              captionTracks = trkList.map(t => ({
                baseUrl: t.baseUrl || t.url || (t.vssId ? `https://www.youtube.com/api/timedtext?v=${cleanVid}&lang=${t.languageCode}&vss_id=${t.vssId}` : ''),
                languageCode: t.languageCode || t.lang || 'en',
                name: { runs: [{ text: t.name || t.displayName || 'Subtitles' }] }
              })).filter(t => t.baseUrl);
            }
          }
        }
      } catch (domErr) {
        console.warn('[ThaiDubbing] Player DOM inspection error:', domErr);
      }

      // Stage 2: Direct Same-Origin Innertube POST
      if (!captionTracks.length) {
        try {
          const pResp = await fetch(`https://www.youtube.com/youtubei/v1/player?key=${INNERTUBE_API_KEY}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              context: {
                client: {
                  clientName: 'ANDROID',
                  clientVersion: '20.10.38',
                  androidSdkVersion: 30,
                },
              },
              videoId: cleanVid,
            }),
          });
          if (pResp.ok) {
            const pData = await pResp.json();
            captionTracks = pData?.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];
          }
        } catch (innertubeErr) {
          console.warn('[ThaiDubbing] Innertube POST error, falling back to DOM scripts:', innertubeErr);
        }
      }

      // Stage 3: Search DOM script tags for captionTracks
      if (!captionTracks.length) {
        const scripts = document.querySelectorAll('script');
        for (const s of scripts) {
          if (s.textContent && s.textContent.includes('captionTracks')) {
            const match = s.textContent.match(/"captionTracks":\s*(\[.+?\])/);
            if (match) {
              try {
                const parsed = JSON.parse(match[1]);
                if (Array.isArray(parsed) && parsed.length) {
                  captionTracks = parsed;
                  break;
                }
              } catch (pe) {}
            }
          }
        }
      }

      if (!captionTracks || !captionTracks.length) {
        console.warn('[ThaiDubbing] No caption tracks found directly on page for:', cleanVid);
        return null;
      }

      console.log(`[ThaiDubbing] Available caption tracks (${captionTracks.length}):`, captionTracks.map((t) => t.languageCode));

      // Prioritize English, then Thai, then any available track
      const chosen = captionTracks.find((t) => t.languageCode === 'en' || t.languageCode === 'en-US') ||
                     captionTracks.find((t) => t.languageCode === 'th') ||
                     captionTracks[0];

      if (!chosen || !chosen.baseUrl) return null;

      console.log('[ThaiDubbing] Selected track:', chosen.languageCode, '-> Fetching timedtext...');

      const subResp = await fetch(chosen.baseUrl);
      if (!subResp.ok) return null;
      const rawXml = await subResp.text();
      if (!rawXml || !rawXml.trim()) return null;

      const cues = parseXmlCues(rawXml);
      if (cues && cues.length > 0) {
        console.log(`[ThaiDubbing] 🎉 Successfully parsed ${cues.length} structured sentence cues!`);
        return { success: true, videoId: cleanVid, cues };
      }
      return null;
    } catch (err) {
      console.error('[ThaiDubbing] Subtitle extraction error:', err);
      return null;
    }
  }

  // --- Subtitle Dispatcher (Direct Browser First -> Local Daemon via Background SW) ---
  async function fetchTranscriptDirect(videoId) {
    // 1. Direct Same-Origin Browser Extraction (100% Reliable, 0 Latency)
    const directRes = await fetchYouTubeInnertubeDirect(videoId);
    if (directRes && directRes.cues && directRes.cues.length > 0) {
      return directRes;
    }

    // 2. Fetch via Background Service Worker (Safe from Mixed Content)
    return new Promise((resolve) => {
      chrome.runtime.sendMessage(
        {
          type: 'FETCH_TRANSCRIPT',
          payload: {
            backendUrl: state.backendUrl || 'http://127.0.0.1:8000',
            videoId: videoId,
          },
        },
        (res) => {
          if (chrome.runtime.lastError || !res || !res.success || !res.cues || res.cues.length === 0) {
            console.warn('[ThaiDubbing] Background transcript fetch empty:', chrome.runtime.lastError || res);
            resolve({ success: false, cues: [] });
          } else {
            resolve(res);
          }
        }
      );
    });
  }

  async function fetchDubBatchDirect(cues) {
    const payload = {
      cues: cues.map((c) => ({ id: c.id, start: c.start, end: c.end, text: c.text })),
      context: getVideoTitle(),
      engine: state.engine || 'qwen_tts',
      voice: state.voice || 'qwen-thai-female',
      gender: state.gender || 'auto',
      style: state.style || 'auto',
      rate: state.rate,
      translationModel: 'qwen-max',
      customQwenKey: state.customQwenKey,
      fishApiKey: state.fishApiKey,
    };

    return new Promise((resolve) => {
      chrome.runtime.sendMessage(
        {
          type: 'FETCH_DUB_BATCH',
          payload: {
            backendUrl: state.backendUrl || 'http://127.0.0.1:8000',
            ...payload,
          },
        },
        (res) => {
          if (chrome.runtime.lastError || !res || !res.success || !res.results) {
            console.warn('[ThaiDubbing] Batch dub fetch error:', chrome.runtime.lastError || res);
            resolve({ success: false, results: [] });
          } else {
            resolve(res);
          }
        }
      );
    });
  }

  async function fetchDubDirect(payload) {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage(
        {
          type: 'FETCH_DUB',
          payload: {
            backendUrl: state.backendUrl || 'http://127.0.0.1:8000',
            text: payload.text,
            context: payload.context || getVideoTitle(),
            engine: payload.engine || state.engine,
            voice: payload.voice || state.voice,
            gender: payload.gender || state.gender || 'male',
            style: payload.style || state.style,
            rate: payload.rate || state.rate,
            translationModel: payload.translationModel || state.translationModel || 'qwen-max',
            customQwenKey: payload.customQwenKey || state.customQwenKey,
            fishApiKey: payload.fishApiKey || state.fishApiKey,
          },
        },
        (res) => {
          if (chrome.runtime.lastError || !res) {
            console.warn('[ThaiDubbing] Single dub fetch error:', chrome.runtime.lastError);
            resolve({ success: false });
          } else {
            resolve(res);
          }
        }
      );
    });
  }

  // --- Reliable YouTube Pause / Play Controls ---
  function pauseYouTubeVideo() {
    console.log('[ThaiDubbing] Pausing YouTube video cleanly...');
    const video = findVideoElement();
    if (video) {
      try {
        video.pause();
      } catch (e) {}
    }

    try {
      const player = document.getElementById('movie_player') || document.querySelector('.html5-video-player');
      if (player && typeof player.pauseVideo === 'function') {
        player.pauseVideo();
      }
    } catch (e) {}
  }

  function resumeYouTubeVideo() {
    console.log('[ThaiDubbing] Resuming YouTube video playback...');
    const video = findVideoElement();
    if (video) {
      try {
        video.play().catch(() => {});
      } catch (e) {}
    }

    try {
      const player = document.getElementById('movie_player') || document.querySelector('.html5-video-player');
      if (player && typeof player.playVideo === 'function') {
        player.playVideo();
      }
    } catch (e) {}
  }

  function findVideoElement() {
    const video = document.querySelector('video.html5-main-video') || document.querySelector('video');
    if (video && video !== state.videoElement) {
      state.videoElement = video;
      state.originalVideoVolume = video.volume;
      attachVideoEvents(video);
    }
    return state.videoElement;
  }

  function attachVideoEvents(video) {
    video.addEventListener('pause', () => {
      // Do not suspend audioCtx on pause, just allow monophonic queue management
    });

    video.addEventListener('play', () => {
      unlockAudio();
      if (state.isSyncBuffering) {
        console.log('[ThaiDubbing] Video play attempted during pre-buffering, keeping paused...');
        pauseYouTubeVideo();
        return;
      }
    });

    video.addEventListener('seeking', () => {
      if (state.isDubbingActive) {
        stopActivePlayback();
        restoreVideoVolume();
        const cur = video.currentTime;
        state.timedCues.forEach((c) => {
          if (c.end < cur) {
            c.status = 'played';
          } else if (c.start >= cur) {
            c.status = (c.audioUrl || c.audioBase64) ? 'ready' : 'pending';
          }
        });
        updateBufferGauge();
      }
    });

    video.addEventListener('ended', () => {
      stopActivePlayback();
      restoreVideoVolume();
    });
  }

  // --- Audio Ducking ---
  function applyAudioDucking() {
    const video = findVideoElement();
    if (!video || state.isDucking) return;

    state.isDucking = true;
    if (video.volume > 0 && !video.muted) {
      state.originalVideoVolume = video.volume;
      const target = Math.max(0.05, state.originalVideoVolume * state.duckVolume);
      fadeVolume(video, video.volume, target, 100);
    }
  }

  function restoreVideoVolume() {
    const video = findVideoElement();
    if (!video || !state.isDucking) return;

    state.isDucking = false;
    fadeVolume(video, video.volume, state.originalVideoVolume, 180);
  }

  function fadeVolume(mediaEl, startVol, endVol, durationMs) {
    const steps = 6;
    const stepTime = durationMs / steps;
    const volStep = (endVol - startVol) / steps;
    let step = 0;

    const interval = setInterval(() => {
      step++;
      const nextVol = startVol + volStep * step;
      mediaEl.volume = Math.min(1.0, Math.max(0.0, nextVol));
      if (step >= steps) {
        mediaEl.volume = Math.min(1.0, Math.max(0.0, endVol));
        clearInterval(interval);
      }
    }, stepTime);
  }

  // --- 1-Click "Start Dubbing" Main Execution Pipeline (2-Minute Narrative Buffer) ---
  async function startDubbingProcess() {
    if (state.isDubbingActive) {
      console.log('[ThaiDubbing] Dubbing already active, ignoring double click.');
      return;
    }
    console.log('[ThaiDubbing] >>> 1. Start Dubbing clicked (120s buffer)');
    unlockAudio();

    const videoId = getVideoId();
    if (!videoId) {
      alert('ไม่พบรหัสวิดีโอ YouTube ในหน้านี้');
      return;
    }

    state.isDubbingActive = true;
    state.isSyncBuffering = true;
    state.bufferedSeconds = 0;
    setNativeCaptionsHidden(true);

    // 1. Pause video cleanly while buffering
    pauseYouTubeVideo();
    renderHUD();
    updateHUDStatus('⏳ วิดีโอหยุดชั่วคราว: กำลังวิเคราะห์และเรียบเรียงภาษาไทยล่วงหน้า 3 นาที...');

    try {
      // 2. Fetch Structured Transcript via Background Proxy
      const transcriptRes = await fetchTranscriptDirect(videoId);
      console.log('[ThaiDubbing] >>> 2. Transcript response:', transcriptRes);

      if (transcriptRes && transcriptRes.success && transcriptRes.cues && transcriptRes.cues.length > 0) {
        state.timedCues = transcriptRes.cues.map((c) => ({
          ...c,
          translated: '',
          audioBuffer: null,
          status: 'pending',
        }));
        state.currentVideoId = videoId;
        console.log(`[ThaiDubbing] Loaded ${state.timedCues.length} cues. Pre-buffering 180 seconds...`);

        // 3. 3-Minute Golden Buffer: Pre-buffer 180 seconds for cohesive storytelling & flawless audio
        const video = findVideoElement();
        const cur = video ? video.currentTime : 0;
        const targetTime = cur + state.targetBufferSeconds;
        const batchCues = state.timedCues.filter((c) => c.end >= cur && c.start <= targetTime);
        const toFetch = (batchCues.length > 0 ? batchCues : state.timedCues).slice(0, 48);

        const chunkSize = 8;
        let totalFetchedCues = 0;

        for (let i = 0; i < toFetch.length; i += chunkSize) {
          if (!state.isDubbingActive) break;
          const chunk = toFetch.slice(i, i + chunkSize);
          chunk.forEach((c) => (c.status = 'fetching'));

          const progressPercent = Math.round((totalFetchedCues / toFetch.length) * 100);
          updateHUDStatus(`⏳ กำลังเรียบเรียงและสร้างเสียงพากย์ล่วงหน้า 3 นาที (${progressPercent}% - ท่อนที่ ${i + 1}/${toFetch.length})...`);

          const batchRes = await fetchDubBatchDirect(chunk);
          if (batchRes && batchRes.success && batchRes.results) {
            for (const item of batchRes.results) {
              const cue = state.timedCues.find((c) => c.id === item.id);
              if (cue) {
                cue.translated = item.translatedText || cue.text;
                cue.isMasterTrack = !!item.isMasterTrack;
                cue.speaker = item.speaker || 'Host';
                cue.emotion = item.emotion || 'normal';
                cue.orig_wpm = item.orig_wpm || 140;
                cue.appliedRate = item.appliedRate || '+0%';
                if (item.base64Audio) {
                  cue.audioBase64 = item.base64Audio;
                  cue.audioUrl = base64ToBlobUrl(item.base64Audio);
                }
                cue.status = 'ready';
                totalFetchedCues++;
              }
            }
            updateBufferGauge();
          }
        }

        // 4. 3-Minute buffer is ready -> Automatically Play Video & Start Background Lookahead!
        state.bufferedSeconds = state.targetBufferSeconds;
        updateBufferGauge();
        onBufferSyncComplete();
        startLookaheadWorkers();

      } else {
        console.warn('[ThaiDubbing] Video has no transcripts. Switching to Live Subtitle mode.');
        enableYouTubeCaptionsButton();
        showSystemToast('⚠️ วิดีโอนี้ไม่มี Subtitle ถอดเสียงสำเร็จ จึงเปิดโหมดพากย์สดอัตโนมัติ');
        onBufferSyncComplete();
        updateHUDStatus('🟢 โหมดพากย์สด (กำลังพากย์ตามซับ)');
      }
    } catch (err) {
      console.error('[ThaiDubbing] Error during startDubbingProcess:', err);
      stopDubbing();
      showSystemToast('❌ เกิดข้อผิดพลาดในการโหลดระบบพากย์ โปรดลองใหม่อีกครั้ง');
    }
  }

  function enableYouTubeCaptionsButton() {
    const ccBtn = document.querySelector('.ytp-subtitles-button');
    if (ccBtn && ccBtn.getAttribute('aria-pressed') !== 'true') {
      ccBtn.click();
    }
  }

  function stopDubbing() {
    console.log('[ThaiDubbing] >>> Stop Dubbing clicked!');
    state.isDubbingActive = false;
    state.isSyncBuffering = false;
    if (state.pauseEnforcerTimer) clearInterval(state.pauseEnforcerTimer);
    if (state.lookaheadTimer) clearInterval(state.lookaheadTimer);
    if (state.schedulerTimer) clearInterval(state.schedulerTimer);
    stopActivePlayback();
    clearCinemaSubtitle();
    setNativeCaptionsHidden(false);
    restoreVideoVolume();
    renderHUD();
    updateHUDStatus('⏸️ หยุดการพากย์เสียงแล้ว');
  }

  function onBufferSyncComplete() {
    if (!state.isSyncBuffering) return;
    console.log('[ThaiDubbing] >>> 180s Buffer Ready! Resuming video playback...');
    state.isSyncBuffering = false;

    // Automatically Resume Video Immediately
    resumeYouTubeVideo();
    renderHUD();
    updateHUDStatus('🟢 บัฟเฟอร์ 3 นาทีพร้อมแล้ว! วิดีโอกำลังเล่น');
  }

  // --- Continuous Lookahead Worker & Audio Scheduler ---
  function startLookaheadWorkers() {
    if (state.lookaheadTimer) clearInterval(state.lookaheadTimer);
    if (state.schedulerTimer) clearInterval(state.schedulerTimer);

    // Continuous Worker: Maintains 100-180s paragraph buffer ahead throughout entire video
    state.lookaheadTimer = setInterval(async () => {
      if (!state.isDubbingActive || state.timedCues.length === 0 || state.isPreFetching) return;
      const video = findVideoElement();
      const currentTime = video ? video.currentTime : 0;
      updateBufferGauge();

      // If buffer drops below 160s, keep fetching upcoming pending cues continuously!
      if (state.bufferedSeconds < 160) {
        const upcomingCues = state.timedCues.filter((c) => c.end >= currentTime - 1.0);
        const pendingCues = upcomingCues.filter((c) => c.status === 'pending');

        if (pendingCues.length > 0) {
          const nextBatch = pendingCues.slice(0, 12);
          nextBatch.forEach((c) => (c.status = 'fetching'));
          state.isPreFetching = true;

          try {
            const batchRes = await fetchDubBatchDirect(nextBatch);
            if (batchRes && batchRes.success && batchRes.results) {
              if (batchRes.speaker_count !== undefined && batchRes.speaker_count > state.speakerCount) {
                state.speakerCount = batchRes.speaker_count;
                state.maleCount = batchRes.male_count || 0;
                state.femaleCount = batchRes.female_count || 0;
                state.speakers = batchRes.speakers || [];
                renderHUD();
              }

              for (const item of batchRes.results) {
                const cue = state.timedCues.find((c) => c.id === item.id);
                if (cue) {
                  cue.translated = item.translatedText || cue.text;
                  cue.isMasterTrack = !!item.isMasterTrack;
                  cue.speaker = item.speaker || 'Host';
                  cue.emotion = item.emotion || 'normal';
                  cue.orig_wpm = item.orig_wpm || 140;
                  cue.appliedRate = item.appliedRate || '+0%';
                  if (item.base64Audio) {
                    cue.audioBase64 = item.base64Audio;
                    cue.audioUrl = base64ToBlobUrl(item.base64Audio);
                    cue.status = 'ready';
                  } else {
                    cue.audioUrl = null;
                    cue.audioBase64 = null;
                    cue.status = 'ready';
                  }
                }
              }
              updateBufferGauge();
            } else {
              nextBatch.forEach((c) => {
                if (c.status === 'fetching') c.status = 'pending';
              });
            }
          } catch (fetchErr) {
            console.error('[ThaiDubbing] Lookahead fetch error:', fetchErr);
            nextBatch.forEach((c) => {
              if (c.status === 'fetching') c.status = 'pending';
            });
          } finally {
            state.isPreFetching = false;
          }
        }
      }
    }, 300);

    // Audio Scheduler: Lightweight, ultra-smooth playback without CPU spikes or Safari freezes
    state.schedulerTimer = setInterval(() => {
      if (!state.isDubbingActive || state.timedCues.length === 0) return;
      const video = findVideoElement();
      if (!video || video.paused) return;

      if (state.isSyncBuffering) {
        if (!video.paused) {
          video.pause();
        }
        return;
      }

      const currentTime = video.currentTime;

      for (let i = 0; i < state.timedCues.length; i++) {
        const cue = state.timedCues[i];
        if (cue.status === 'ready' && currentTime >= cue.start - 0.08 && currentTime <= cue.end + 0.3) {
          cue.status = 'played';
          state.lastScheduledCue = cue;
          if (cue.audioUrl || cue.audioBase64) {
            schedulePlayAudio(cue);
          } else if (cue.translated) {
            const durMs = Math.max(800, Math.round((cue.end - cue.start) * 1000 + 400));
            renderCinemaSubtitle(cue.translated, durMs);
          }
          break;
        } else if (cue.start > currentTime + 0.5) {
          // Cues are sorted by start time, no need to check further into future
          break;
        }
      }
    }, 40);
  }

  function stopActivePlayback() {
    if (state.playSafetyTimeout) {
      clearTimeout(state.playSafetyTimeout);
      state.playSafetyTimeout = null;
    }
    const audio = getGlobalAudioPlayer();
    if (audio) {
      try {
        audio.pause();
        audio.currentTime = 0;
      } catch (e) {}
    }
    state.isPlaying = false;
    state.nextSpeechTime = 0;
  }

  // --- Strict Single-Track Monophonic Speech Engine (Zero Overlap & Zero Dropout) ---
  function schedulePlayAudio(cue) {
    if (!cue.audioUrl && !cue.audioBase64) return;

    stopActivePlayback();

    const video = findVideoElement();
    const videoSpeed = (video && video.playbackRate) ? video.playbackRate : 1.0;

    const audio = getGlobalAudioPlayer();
    if (!audio) return;

    const audioSrc = cue.audioUrl || base64ToBlobUrl(cue.audioBase64);
    audio.src = audioSrc;
    audio.volume = (typeof state.dubVolume === 'number' && !isNaN(state.dubVolume)) ? state.dubVolume : 1.0;
    try {
      audio.preservesPitch = true;
      audio.webkitPreservesPitch = true;
      audio.playbackRate = 1.0;
    } catch (rateErr) {}

    state.isPlaying = true;
    applyAudioDucking();

    // Safety watchdog: automatically unlock state.isPlaying if audio stalls or onended is dropped
    const expectedDurationMs = Math.max(1500, Math.round(((cue.end - cue.start) + 2.5) * 1000));
    state.playSafetyTimeout = setTimeout(() => {
      if (state.isPlaying) {
        console.log('[ThaiDubbing] Safety watchdog released isPlaying lock.');
        state.isPlaying = false;
        restoreVideoVolume();
      }
    }, expectedDurationMs);

    if (state.showSubtitles) {
      const durationMs = Math.max(800, Math.round((cue.end - cue.start) * 1000 + 400));
      renderCinemaSubtitle(cue.translated, durationMs);
    } else {
      clearCinemaSubtitle();
    }

    const rhythmTag = cue.orig_wpm ? `⚡ ${cue.orig_wpm} WPM (${cue.appliedRate || '+0%'}) | ` : '';
    updateHUDStatus(`🔊 ${rhythmTag}"${cue.translated.slice(0, 18)}..."`);

    audio.onended = () => {
      if (state.playSafetyTimeout) clearTimeout(state.playSafetyTimeout);
      state.isPlaying = false;
      clearCinemaSubtitle();
      restoreVideoVolume();
      updateBufferGauge();
    };

    audio.onerror = (err) => {
      console.error('[ThaiDubbing] Audio error:', err);
      if (state.playSafetyTimeout) clearTimeout(state.playSafetyTimeout);
      state.isPlaying = false;
      restoreVideoVolume();
    };

    audio.play().catch((playErr) => {
      console.warn('[ThaiDubbing] Audio play caught:', playErr);
      if (state.playSafetyTimeout) clearTimeout(state.playSafetyTimeout);
      state.isPlaying = false;
      restoreVideoVolume();
    });
  }

  function updateBufferGauge() {
    const video = findVideoElement();
    const cur = video ? video.currentTime : 0;
    const readyCues = state.timedCues.filter((c) => c.status === 'ready' && (c.audioUrl || c.audioBase64) && c.end >= cur - 1.0);

    if (readyCues.length > 0) {
      const readyDuration = readyCues.reduce((acc, c) => acc + (c.end - c.start), 0);
      const maxEnd = Math.max(...readyCues.map((c) => c.end));
      state.bufferedSeconds = Math.max(Math.round(readyDuration), Math.round(maxEnd - cur));
    } else {
      state.bufferedSeconds = 0;
    }

    const gaugeEl = document.getElementById('hud-buffer-text');
    const barEl = document.getElementById('hud-buffer-bar');
    if (gaugeEl) {
      if (state.isSyncBuffering) {
        gaugeEl.textContent = `⏳ ซิงค์ 3 นาที: ${state.bufferedSeconds}s/${state.targetBufferSeconds}s`;
      } else {
        gaugeEl.textContent = `⚡ บัฟเฟอร์ล่วงหน้า: ${state.bufferedSeconds}s`;
      }
    }
    if (barEl) {
      const percent = Math.min(100, Math.round((state.bufferedSeconds / state.targetBufferSeconds) * 100));
      barEl.style.width = `${percent}%`;
    }
  }

  // --- Live Subtitle Observer (Fallback for non-transcript videos) ---
  function observeCaptions() {
    const captionContainer =
      document.querySelector('.ytp-caption-window-bottom') ||
      document.querySelector('#movie_player .caption-window') ||
      document.querySelector('#ytp-caption-window-container') ||
      document.querySelector('#movie_player');

    if (!captionContainer) {
      setTimeout(observeCaptions, 1000);
      return;
    }

    if (state.captionObserver) state.captionObserver.disconnect();

    state.captionObserver = new MutationObserver(() => {
      if (!state.isDubbingActive || state.timedCues.length > 0) return;

      const segments = document.querySelectorAll('.ytp-caption-segment');
      if (segments && segments.length > 0) {
        const textContent = Array.from(segments)
          .map((s) => s.textContent)
          .join(' ')
          .trim();
        if (textContent) {
          handleLiveCaptionFragment(textContent);
        }
      }
    });

    state.captionObserver.observe(captionContainer, {
      childList: true,
      subtree: true,
      characterData: true,
    });
  }

  function handleLiveCaptionFragment(text) {
    if (!state.isDubbingActive || !text || state.timedCues.length > 0) return;
    const trimmed = text.replace(/[\r\n]+/g, ' ').trim();
    if (!trimmed || trimmed === state.pendingLiveChunks[state.pendingLiveChunks.length - 1]) return;

    if (state.liveChunkTimer) clearTimeout(state.liveChunkTimer);
    state.pendingLiveChunks.push(trimmed);

    state.liveChunkTimer = setTimeout(async () => {
      if (state.pendingLiveChunks.length > 0) {
        const full = state.pendingLiveChunks.join(' ');
        state.pendingLiveChunks = [];
        requestDubbingLive(full);
      }
    }, 350);
  }

  async function requestDubbingLive(sentence) {
    if (!state.isDubbingActive || !sentence || sentence.trim().length < 2) return;
    const cleanText = sentence.trim();
    if (cleanText === state.lastProcessedLiveText) return;
    state.lastProcessedLiveText = cleanText;

    updateHUDStatus(`🟡 แปล: "${cleanText.slice(0, 14)}..."`);

    const title = getVideoTitle();
    const dubRes = await fetchDubDirect({
      text: cleanText,
      context: title,
      engine: state.engine,
      voice: state.voice,
      gender: state.gender,
      style: state.style || 'auto',
      rate: state.rate,
      translationModel: state.translationModel || 'qwen-max',
      customQwenKey: state.customQwenKey,
    });

    if (dubRes && dubRes.success && dubRes.base64Audio) {
      if (dubRes.qwen_status === 'depleted') {
        showSystemToast('⚠️ โควต้า Qwen API Key หมดลงแล้ว (429)');
      } else if (dubRes.qwen_status === 'invalid') {
        showSystemToast('⚠️ Qwen API Key ไม่ถูกต้อง (400/401)');
      }
      playDirectLiveBuffer(dubRes.base64Audio, dubRes.translatedText);
    }
  }

  function playDirectLiveBuffer(audioBase64, translatedText) {
    if (!audioBase64) return;

    stopActivePlayback();

    const video = findVideoElement();
    const videoSpeed = (video && video.playbackRate) ? video.playbackRate : 1.0;

    const audio = getGlobalAudioPlayer();
    if (!audio) return;

    audio.src = base64ToBlobUrl(audioBase64);
    audio.volume = (typeof state.dubVolume === 'number' && !isNaN(state.dubVolume)) ? state.dubVolume : 1.0;
    try {
      audio.playbackRate = videoSpeed;
    } catch (e) {}

    state.isPlaying = true;
    applyAudioDucking();

    if (state.showSubtitles) {
      renderCinemaSubtitle(translatedText, 3500);
    } else {
      clearCinemaSubtitle();
    }

    updateHUDStatus(`🔊 พากย์: "${translatedText.slice(0, 15)}..."`);

    audio.onended = () => {
      state.isPlaying = false;
      clearCinemaSubtitle();
      restoreVideoVolume();
      updateHUDStatus('🟢 กำลังพากย์สด');
    };

    audio.onerror = (err) => {
      console.error('[ThaiDubbing] Live audio error:', err);
      state.isPlaying = false;
      restoreVideoVolume();
    };

    audio.play().catch((err) => console.warn('[ThaiDubbing] Live play caught:', err));
  }

  // --- Hide YouTube Native Captions during Dubbing ---
  function setNativeCaptionsHidden(hide) {
    let styleEl = document.getElementById('thai-dub-hide-cc-style');
    if (hide) {
      if (!styleEl) {
        styleEl = document.createElement('style');
        styleEl.id = 'thai-dub-hide-cc-style';
        styleEl.textContent = `
          .ytp-caption-window-bottom,
          .caption-window,
          .ytp-caption-segment,
          #ytp-caption-window-container {
            display: none !important;
            opacity: 0 !important;
            visibility: hidden !important;
          }
        `;
        document.head.appendChild(styleEl);
      }
    } else {
      if (styleEl) styleEl.remove();
    }
  }

  // --- Cinema-Grade 100% Synchronized Thai Subtitle Overlay ---
  function renderCinemaSubtitle(text, durationMs) {
    if (!text || !state.isDubbingActive || !state.showSubtitles) return;
    let sub = document.getElementById('thai-cinema-subtitles');
    if (!sub) {
      sub = document.createElement('div');
      sub.id = 'thai-cinema-subtitles';
      sub.style.cssText = `
        position: absolute;
        bottom: 75px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 2147483640;
        max-width: 86%;
        text-align: center;
        pointer-events: none;
        transition: opacity 0.15s ease-out;
      `;
      const player = document.querySelector('#movie_player') || document.querySelector('.html5-video-player') || document.body;
      player.appendChild(sub);
    }

    sub.innerHTML = `
      <div style="
        display: inline-block;
        background: rgba(0, 0, 0, 0.78);
        color: #ffffff;
        font-family: -apple-system, BlinkMacSystemFont, 'Noto Sans Thai', 'Thonburi', sans-serif;
        font-size: 22px;
        font-weight: 700;
        line-height: 1.45;
        padding: 6px 18px;
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.18);
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.85);
        text-shadow: 0 2px 4px rgba(0,0,0,0.9), 0 0 8px rgba(0,0,0,0.8);
        word-break: break-word;
      ">
        ${text}
      </div>
    `;
    sub.style.opacity = '1';
    sub.style.display = 'block';

    if (sub.fadeTimer) clearTimeout(sub.fadeTimer);
    if (durationMs && durationMs > 0) {
      sub.fadeTimer = setTimeout(() => {
        if (sub) {
          sub.style.opacity = '0';
        }
      }, durationMs);
    }
  }

  function clearCinemaSubtitle() {
    const sub = document.getElementById('thai-cinema-subtitles');
    if (sub) {
      sub.style.opacity = '0';
      if (sub.fadeTimer) clearTimeout(sub.fadeTimer);
    }
  }

  // --- Top Notification Toast (For System Alerts) ---
  function showSystemToast(text) {
    if (!text) return;
    let toast = document.getElementById('thai-dub-system-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'thai-dub-system-toast';
      toast.style.cssText = `
        position: fixed;
        top: 18px;
        left: 50%;
        transform: translateX(-50%);
        background: rgba(15, 23, 42, 0.95);
        color: #38bdf8;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans Thai", sans-serif;
        font-size: 13px;
        font-weight: 600;
        padding: 6px 16px;
        border-radius: 20px;
        border: 1px solid rgba(56, 189, 248, 0.4);
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.7);
        z-index: 2147483647;
        pointer-events: none;
        transition: opacity 0.2s ease;
        text-align: center;
        max-width: 90%;
      `;
      document.body.appendChild(toast);
    }
    toast.textContent = text;
    toast.style.opacity = '1';

    clearTimeout(toast.fadeTimer);
    toast.fadeTimer = setTimeout(() => {
      if (toast) toast.style.opacity = '0';
    }, 3500);
  }

  // --- Floating Control Pill (HUD Mounted Directly to Body) ---
  function createOrGetHUD() {
    let hud = document.getElementById('thai-dub-hud');
    if (!hud) {
      hud = document.createElement('div');
      hud.id = 'thai-dub-hud';
      hud.style.cssText = `
        position: fixed;
        top: 68px;
        right: 24px;
        z-index: 2147483647;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans Thai", sans-serif;
        font-size: 12px;
        user-select: none;
        pointer-events: auto;
        transition: all 0.2s ease;
      `;
      document.body.appendChild(hud);
    }
    return hud;
  }

  function renderHUD() {
    const hud = createOrGetHUD();
    if (!hud) return;

    // --- Collapsed State ---
    if (state.isCollapsed) {
      hud.innerHTML = `
        <div id="hud-expand-pill" style="
          background: rgba(15, 23, 42, 0.94);
          color: white;
          border: 1px solid rgba(99, 102, 241, 0.5);
          border-radius: 20px;
          padding: 5px 10px;
          display: flex;
          align-items: center;
          gap: 6px;
          cursor: pointer;
          backdrop-filter: blur(8px);
          box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        ">
          <span>🎙️</span>
          <span style="font-size: 11px; font-weight: 700; color: ${state.isDubbingActive ? '#10b981' : '#f59e0b'};">
            ${state.isDubbingActive ? (state.isSyncBuffering ? '⏳ 1M SYNC' : 'ON') : 'START'}
          </span>
          ${state.isDubbingActive ? `<span style="font-size: 10px; color: #38bdf8;">${state.bufferedSeconds}s</span>` : ''}
        </div>
      `;
      const expandBtn = document.getElementById('hud-expand-pill');
      if (expandBtn) {
        expandBtn.onclick = (e) => {
          e.stopPropagation();
          state.isCollapsed = false;
          saveSetting('isCollapsed', false);
          renderHUD();
        };
      }
      return;
    }

    // --- Compact Bar with Primary "เริ่มพากย์ไทย (1 นาที)" Button & Live 60s Buffer Gauge ---
    const voiceOpts = VOICES.map(
      (v) => `<option value="${v.id}" ${v.id === state.voice ? 'selected' : ''}>${v.name}</option>`
    ).join('');

    const bufferPercent = Math.min(100, Math.round((state.bufferedSeconds / state.targetBufferSeconds) * 100));

    hud.innerHTML = `
      <div style="
        background: rgba(15, 23, 42, 0.96);
        color: #f8fafc;
        border: 1px solid ${state.isSyncBuffering ? '#f59e0b' : (state.isDubbingActive ? 'rgba(16, 185, 129, 0.7)' : 'rgba(99, 102, 241, 0.6)')};
        border-radius: 18px;
        padding: 5px 12px;
        display: flex;
        align-items: center;
        gap: 8px;
        backdrop-filter: blur(12px);
        box-shadow: 0 6px 20px rgba(0,0,0,0.65);
      ">
        <!-- Main "เริ่มพากย์ไทย" / "หยุดพากย์" Button -->
        ${!state.isDubbingActive ? `
          <button id="hud-start-dub-btn" type="button" title="คลิกเพื่อหยุดวิดีโอ วิเคราะห์เนื้อหาและเรียบเรียงภาษาไทยล่วงหน้า 2 นาที แล้วเริ่มเล่นพร้อมพากย์ไทย" style="
            background: linear-gradient(135deg, #4f46e5, #2563eb);
            color: #ffffff;
            border: none;
            border-radius: 14px;
            padding: 5px 14px;
            font-size: 12px;
            font-weight: 700;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 6px;
            box-shadow: 0 2px 10px rgba(79, 70, 229, 0.5);
          ">
            <span>🚀</span>
            <span>เริ่มพากย์ไทย (3 นาที)</span>
          </button>
        ` : (state.isSyncBuffering ? `
          <button id="hud-skip-sync-btn" type="button" title="ข้ามการรอและเล่นวิดีโอทันที" style="
            background: #f59e0b;
            color: #0f172a;
            border: none;
            border-radius: 14px;
            padding: 5px 12px;
            font-size: 11px;
            font-weight: 700;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 4px;
          ">
            <span>▶</span>
            <span>เล่นทันที</span>
          </button>
        ` : `
          <button id="hud-stop-dub-btn" type="button" style="
            background: #ef4444;
            color: white;
            border: none;
            border-radius: 14px;
            padding: 5px 12px;
            font-size: 11px;
            font-weight: 700;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 4px;
          ">
            <span>⏹</span>
            <span>หยุดพากย์</span>
          </button>
        `)}

        <!-- 180-Second Golden Buffer Gauge Indicator -->
        <div style="display: flex; flex-direction: column; gap: 2px; min-width: 135px;">
          <span id="hud-buffer-text" style="font-size: 10px; font-weight: 600; color: ${state.isSyncBuffering ? '#f59e0b' : '#38bdf8'};">
            ${state.isSyncBuffering ? `⏳ ซิงค์ 3 นาที: ${state.bufferedSeconds}s/${state.targetBufferSeconds}s` : (state.isDubbingActive ? `⚡ บัฟเฟอร์ล่วงหน้า: ${state.bufferedSeconds}s` : 'พร้อมแปล (กดปุ่มเริ่ม)')}
          </span>
          <div style="width: 100%; height: 3px; background: rgba(255,255,255,0.15); border-radius: 2px; overflow: hidden;">
            <div id="hud-buffer-bar" style="width: ${state.isDubbingActive ? bufferPercent : 0}%; height: 100%; background: ${state.isSyncBuffering ? '#f59e0b' : '#10b981'}; transition: width 0.3s ease;"></div>
          </div>
        </div>

        <!-- Voice Selector Dropdown -->
        <select id="hud-voice-select" style="
          background: #1e293b;
          color: #f8fafc;
          border: 1px solid rgba(255,255,255,0.2);
          border-radius: 10px;
          padding: 3px 6px;
          font-size: 11px;
          outline: none;
          max-width: 155px;
          cursor: pointer;
        ">
          ${voiceOpts}
        </select>

        <!-- Test Sound Button -->
        <button id="hud-test-btn" type="button" title="ทดสอบเสียงพากย์" style="
          background: #6366f1;
          color: white;
          border: none;
          border-radius: 10px;
          padding: 3px 8px;
          font-size: 11px;
          font-weight: 600;
          cursor: pointer;
        ">🔊</button>

        <!-- Subtitle On/Off Toggle Button (Default: OFF) -->
        <button id="hud-subtitle-toggle-btn" type="button" title="เปิด/ปิด ซับไตเติลภาษาไทย (ค่าเริ่มต้น: ปิด)" style="
          background: ${state.showSubtitles ? 'rgba(56, 189, 248, 0.25)' : 'rgba(255, 255, 255, 0.08)'};
          color: ${state.showSubtitles ? '#38bdf8' : '#94a3b8'};
          border: 1px solid ${state.showSubtitles ? 'rgba(56, 189, 248, 0.6)' : 'rgba(255, 255, 255, 0.15)'};
          border-radius: 10px;
          padding: 3px 7px;
          font-size: 11px;
          font-weight: 600;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 3px;
        ">
          <span>💬</span>
          <span>${state.showSubtitles ? 'ซับ: เปิด' : 'ซับ: ปิด'}</span>
        </button>

        <!-- Settings Cog -->
        <button id="hud-settings-btn" type="button" title="ตั้งค่าสไตล์/ความเร็ว/ระดับเสียง" style="
          background: transparent;
          color: #94a3b8;
          border: none;
          padding: 3px 5px;
          font-size: 12px;
          cursor: pointer;
        ">⚙️</button>

        <!-- Minimize Button -->
        <button id="hud-minimize-btn" type="button" title="ย่อแถบควบคุม" style="
          background: transparent;
          color: #94a3b8;
          border: none;
          padding: 3px 5px;
          font-size: 12px;
          cursor: pointer;
        ">−</button>
      </div>

      <!-- Settings Dropdown Drawer -->
      <div id="hud-settings-drawer" style="
        display: ${state.showSettingsModal ? 'flex' : 'none'};
        flex-direction: column;
        gap: 6px;
        background: rgba(15, 23, 42, 0.96);
        border: 1px solid rgba(99, 102, 241, 0.4);
        border-radius: 10px;
        padding: 8px 12px;
        margin-top: 6px;
        box-shadow: 0 6px 18px rgba(0,0,0,0.6);
      ">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 11px; color: #94a3b8; font-weight: 600;">โมเดลเสียง AI:</span>
          <select id="hud-voice-select" style="
            background: #1e293b; color: #38bdf8; border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; padding: 2px 6px; font-size: 11px; outline: none; max-width: 200px;
          ">
            ${VOICES.map((v) => `<option value="${v.id}" ${v.id === state.voice ? 'selected' : ''}>${v.name}</option>`).join('')}
          </select>
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 11px; color: #94a3b8; font-weight: 600;">สไตล์ / ระดับภาษา:</span>
          <select id="hud-style-select" style="
            background: #1e293b; color: white; border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; padding: 2px 6px; font-size: 11px;
          ">
            ${STYLES.map((s) => `<option value="${s.id}" ${s.id === state.style ? 'selected' : ''}>${s.name}</option>`).join('')}
          </select>
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 11px; color: #94a3b8; font-weight: 600;">ลดเสียงคลิปเดิม (Ducking):</span>
          <input type="range" id="hud-duck-slider" min="0" max="50" value="${Math.round(state.duckVolume * 100)}" style="width: 80px; height: 4px;">
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 4px; border-top: 1px solid rgba(255,255,255,0.08);">
          <span style="font-size: 10px; color: #818cf8; font-weight: 600;">🧠 AI Self-Learning Engine:</span>
          <span style="font-size: 10px; color: #a5b4fc; background: rgba(99,102,241,0.2); padding: 1px 6px; border-radius: 4px;">เรียนรู้คลังคำศัพท์อัตโนมัติ</span>
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; gap: 4px;">
          <span style="font-size: 11px; color: #94a3b8; font-weight: 600;">Alibaba Qwen Key:</span>
          <input type="password" id="hud-qwen-input" placeholder="sk-ws-..." value="${state.customQwenKey || ''}" style="
            background: #1e293b; color: #10b981; border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; padding: 2px 6px; font-size: 10px; width: 170px; outline: none;
          ">
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; gap: 4px;">
          <span style="font-size: 11px; color: #94a3b8; font-weight: 600;">Backend URL (Cloud/Local):</span>
          <input type="text" id="hud-backend-input" placeholder="https://thai-dubbing-api.onrender.com" value="${state.backendUrl || 'https://thai-dubbing-api.onrender.com'}" style="
            background: #1e293b; color: #38bdf8; border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; padding: 2px 6px; font-size: 10px; width: 170px; outline: none;
          ">
        </div>

        <div id="hud-status-text" style="font-size: 10px; color: #38bdf8; text-align: center; margin-top: 2px;">
          ${state.isDubbingActive ? '🟢 ระบบกำลังพากย์สด' : '⏸️ กด "🚀 เริ่มพากย์ไทย (2 นาที)" เพื่อเริ่มซิงค์เสียง'}
        </div>
      </div>
    `;

    // Direct Click Handlers
    const startDubBtn = document.getElementById('hud-start-dub-btn');
    if (startDubBtn) {
      startDubBtn.onclick = (e) => {
        e.stopPropagation();
        startDubbingProcess();
      };
    }

    const stopDubBtn = document.getElementById('hud-stop-dub-btn');
    if (stopDubBtn) {
      stopDubBtn.onclick = (e) => {
        e.stopPropagation();
        stopDubbing();
      };
    }

    const skipSyncBtn = document.getElementById('hud-skip-sync-btn');
    if (skipSyncBtn) {
      skipSyncBtn.onclick = (e) => {
        e.stopPropagation();
        onBufferSyncComplete();
      };
    }

    const minBtn = document.getElementById('hud-minimize-btn');
    if (minBtn) {
      minBtn.onclick = (e) => {
        e.stopPropagation();
        state.isCollapsed = true;
        saveSetting('isCollapsed', true);
        renderHUD();
      };
    }

    const setBtn = document.getElementById('hud-settings-btn');
    if (setBtn) {
      setBtn.onclick = (e) => {
        e.stopPropagation();
        state.showSettingsModal = !state.showSettingsModal;
        renderHUD();
      };
    }

    const voiceSelect = document.getElementById('hud-voice-select');
    if (voiceSelect) {
      voiceSelect.onchange = (e) => {
        const selectedId = e.target.value;
        const found = VOICES.find((v) => v.id === selectedId);
        state.voice = selectedId;
        saveSetting('voice', selectedId);
        if (found) {
          state.engine = found.engine;
          state.gender = found.gender;
          saveSetting('engine', found.engine);
          saveSetting('gender', found.gender);
        }

        // If dubbing is active, invalidate buffered cues from the old voice so the new voice takes effect immediately!
        if (state.isDubbingActive && state.timedCues.length > 0) {
          const video = findVideoElement();
          const cur = video ? video.currentTime : 0;
          state.timedCues.forEach((c) => {
            if (c.start >= cur - 1.0) {
              c.status = 'pending';
              c.audioBuffer = null;
            }
          });
          updateBufferGauge();
          showSystemToast(`เปลี่ยนโมเดลเสียงเป็น "${found ? found.name : selectedId}"`);
        }
      };
    }

    const genderEl = document.getElementById('hud-gender-select');
    if (genderEl) {
      genderEl.onchange = (e) => {
        const val = e.target.value;
        state.gender = val;
        saveSetting('gender', val);
        showSystemToast(`เปลี่ยนโหมดเพศเป็น: ${val === 'female' ? '👩 ผู้หญิง (ค่ะ)' : (val === 'male' ? '👨 ผู้ชาย (ครับ)' : '🤖 อัตโนมัติ')}`);

        if (state.isDubbingActive && state.timedCues.length > 0) {
          const video = findVideoElement();
          const cur = video ? video.currentTime : 0;
          state.timedCues.forEach((c) => {
            if (c.start >= cur - 1.0) {
              c.status = 'pending';
              c.audioBuffer = null;
            }
          });
          updateBufferGauge();
        }
      };
    }

    const styleEl = document.getElementById('hud-style-select');
    if (styleEl) {
      styleEl.onchange = (e) => {
        saveSetting('style', e.target.value);
      };
    }

    const duckSlider = document.getElementById('hud-duck-slider');
    if (duckSlider) {
      duckSlider.oninput = (e) => {
        saveSetting('duckVolume', parseInt(e.target.value, 10) / 100);
      };
    }

    const fishInput = document.getElementById('hud-fish-input');
    if (fishInput) {
      fishInput.onchange = (e) => {
        const val = e.target.value.trim();
        saveSetting('fishApiKey', val);
        state.fishApiKey = val;
        updateHUDStatus(`🐟 บันทึก Fish Audio Key เรียบร้อย`);
      };
    }

    const qwenInput = document.getElementById('hud-qwen-input');
    if (qwenInput) {
      qwenInput.onchange = (e) => {
        const val = e.target.value.trim();
        saveSetting('customQwenKey', val);
        state.customQwenKey = val;
        updateHUDStatus('👑 บันทึก Alibaba Qwen Key เรียบร้อย');
      };
    }

    const backendInput = document.getElementById('hud-backend-input');
    if (backendInput) {
      backendInput.onchange = (e) => {
        const val = e.target.value.trim().replace(/\/+$/, '');
        saveSetting('backendUrl', val);
        state.backendUrl = val;
        updateHUDStatus(`🌐 บันทึก Backend URL: ${val}`);
      };
    }

    const subBtn = document.getElementById('hud-subtitle-toggle-btn');
    if (subBtn) {
      subBtn.onclick = (e) => {
        e.stopPropagation();
        state.showSubtitles = !state.showSubtitles;
        saveSetting('showSubtitles', state.showSubtitles);
        if (!state.showSubtitles) {
          clearCinemaSubtitle();
        }
        showSystemToast(state.showSubtitles ? '💬 เปิดซับไตเติลภาษาไทยแล้ว' : '💬 ปิดซับไตเติลภาษาไทยแล้ว');
        renderHUD();
      };
    }

    const testBtn = document.getElementById('hud-test-btn');
    if (testBtn) {
      testBtn.onclick = (e) => {
        e.stopPropagation();
        playDemoTestSound();
      };
    }
  }

  function updateHUDStatus(text) {
    const el = document.getElementById('hud-status-text');
    if (el) el.textContent = text;
  }

  function playDemoTestSound() {
    unlockAudio();
    updateHUDStatus('🟡 กำลังสร้างเสียงทดสอบ...');

    const sampleText = state.gender === 'female'
      ? 'ยินดีต้อนรับเข้าสู่ช่องของเรา นี่คือตัวอย่างเสียงพากย์ภาษาไทยแบบธรรมชาติ'
      : 'ยินดีต้อนรับเข้าสู่ช่องของเรา นี่คือตัวอย่างเสียงพากย์ภาษาไทยแบบธรรมชาติ';

    chrome.runtime.sendMessage({
      type: 'FETCH_DUB',
      payload: {
        backendUrl: state.backendUrl,
        text: sampleText,
        engine: state.engine,
        voice: state.voice,
        gender: state.gender,
        style: state.style,
        rate: state.rate,
        translationModel: state.translationModel || 'qwen-max',
        customQwenKey: state.customQwenKey,
      },
    }, (response) => {
      if (response && response.success && response.base64Audio) {
        playDirectLiveBuffer(response.base64Audio, response.translatedText || sampleText);
      } else {
        updateHUDStatus('❌ เชื่อมต่อ Backend ไม่ได้');
        alert(`เกิดข้อผิดพลาด: ${response ? response.error : 'กรุณารัน ./run_backend.sh'}`);
      }
    });
  }

  // --- Initialization & Page Transition Watcher ---
  async function init() {
    await loadSettings();
    findVideoElement();
    renderHUD();
    observeCaptions();

    let lastUrl = location.href;
    setInterval(() => {
      findVideoElement();
      if (location.href !== lastUrl) {
        lastUrl = location.href;
        const newVid = getVideoId();
        if (newVid && newVid !== state.currentVideoId) {
          state.isDubbingActive = false;
          state.isSyncBuffering = false;
          state.timedCues = [];
          renderHUD();
        }
      }
    }, 1500);

    // Watch YouTube SPA navigation events
    window.addEventListener('yt-navigate-finish', () => {
      findVideoElement();
      const newVid = getVideoId();
      if (newVid && newVid !== state.currentVideoId) {
        state.isDubbingActive = false;
        state.isSyncBuffering = false;
        state.timedCues = [];
        renderHUD();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
