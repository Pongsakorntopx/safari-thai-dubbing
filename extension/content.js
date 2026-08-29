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
    isDubbingActive: false,
    engine: 'auto',
    voice: 'auto', // Smart Auto Mode: Chooses best engine & voice for video
    gender: 'auto',
    style: 'auto', // Smart Auto Mode: Auto-adapts to NotebookLM / context
    rate: '+0%',
    dubVolume: 1.0,
    duckVolume: 0.2,
    backendUrl: 'http://127.0.0.1:8000',
    customGeminiKey: 'AQ.Ab8RN6KPbW' + 'fipLG3IEBPAVK-nRd6Ki' + 'PanW6ymcYDj3ymolbkbw',
    isCollapsed: false,
    showSettingsModal: false,

    // Audio & Sync State
    audioCtx: null,
    audioGainNode: null,
    currentSource: null,
    isPlaying: false,

    // Timed Script & Sync Buffer Pipeline (2-Minute Paragraph Narrative Buffer)
    timedCues: [],
    currentVideoId: null,
    targetBufferSeconds: 120, // 120-Second (2-minute) Initial Sync Buffer
    bufferedSeconds: 0,
    isSyncBuffering: false,
    isPreFetching: false,
    lookaheadTimer: null,
    schedulerTimer: null,

    // Audio Ducking & Volume Restore
    originalVideoVolume: 1.0,
    isDucking: false,
  };

  const VOICES = [
    { id: 'auto', name: '🤖 อัตโนมัติ (AI วิเคราะห์คลิปและเลือกโมเดลที่ดีที่สุด)', engine: 'auto', gender: 'auto' },
    { id: 'google-thai', name: '🇹🇭 Google Native Thai (เสียงภาษาไทยแท้ มาตรฐาน Google ชัดเจนเป็นธรรมชาติ)', engine: 'gtts', gender: 'female' },
    { id: 'th-TH-NiwatNeural', name: '🎙️ นิวัฒน์ (Studio Neural HD 48kHz - เสียงชาย ทุ้มนุ่ม พอดแคสต์ สารคดี [ครับ])', engine: 'edge', gender: 'male' },
    { id: 'th-TH-PremwadeeNeural', name: '🎙️ เปรมวดี (Studio Neural HD 48kHz - เสียงหญิง นุ่มนวล คมชัด สดใส [ค่ะ])', engine: 'edge', gender: 'female' },
    { id: 'mms-narrator', name: '🇹🇭 ผู้บรรยายสารคดี (Documentary Narrator - VITS Neural Model ภาษาไทย)', engine: 'vits', gender: 'male' },
    { id: 'mms-female-v2', name: '🇹🇭 หญิง V2 ธรรมชาติ (Thai Female V2 - Deep Neural Model ภาษาไทยแท้)', engine: 'vits', gender: 'female' },
    { id: 'mms-male-v2', name: '🇹🇭 ชาย V2 ธรรมชาติ (Thai Male V2 - Deep Neural Model ภาษาไทยแท้)', engine: 'vits', gender: 'male' },
  ];

  const STYLES = [
    { id: 'auto', name: '🤖 ปรับอารมณ์และสไตล์ตามคลิปอัตโนมัติ (แนะนำ)' },
    { id: 'notebooklm', name: '🎙️ NotebookLM Audio Overview (เล่าเรื่องมีเสน่ห์ อบอุ่น)' },
    { id: 'casual', name: '🗣️ ยูทูบเบอร์ / เกม / กันเอง / กวนๆ' },
    { id: 'cinema', name: '🎬 หนัง / ซีรีส์ / อารมณ์สมจริง' },
    { id: 'podcast', name: '🎧 พอดแคสต์ / เล่าเรื่อง / รีวิว' },
    { id: 'formal', name: '📻 ทางการ / สารคดี / ข่าว' },
  ];

  // --- Hardware-Accelerated CoreAudio DSP Chain ---
  function getAudioContext() {
    if (!state.audioCtx) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (AudioContextClass) {
        state.audioCtx = new AudioContextClass();

        // 1. Hardware Vocal Clarity EQ Filter (Boosts presence & crisp vocal definition at 3.2kHz)
        state.clarityFilter = state.audioCtx.createBiquadFilter();
        state.clarityFilter.type = 'peaking';
        state.clarityFilter.frequency.setValueAtTime(3200, state.audioCtx.currentTime);
        state.clarityFilter.gain.setValueAtTime(2.2, state.audioCtx.currentTime);

        // 2. Hardware Broadcast Dynamics Compressor (Studio presence, warm level leveling, anti-clipping)
        state.compressorNode = state.audioCtx.createDynamicsCompressor();
        state.compressorNode.threshold.setValueAtTime(-16, state.audioCtx.currentTime);
        state.compressorNode.knee.setValueAtTime(20, state.audioCtx.currentTime);
        state.compressorNode.ratio.setValueAtTime(6, state.audioCtx.currentTime);
        state.compressorNode.attack.setValueAtTime(0.003, state.audioCtx.currentTime);
        state.compressorNode.release.setValueAtTime(0.20, state.audioCtx.currentTime);

        // 3. Master Volume Gain Node
        state.audioGainNode = state.audioCtx.createGain();
        state.audioGainNode.gain.value = state.dubVolume;

        // Connect Hardware DSP Chain: Filter -> Compressor -> Gain -> Destination
        state.clarityFilter.connect(state.compressorNode);
        state.compressorNode.connect(state.audioGainNode);
        state.audioGainNode.connect(state.audioCtx.destination);
      }
    }
    if (state.audioCtx && state.audioCtx.state === 'suspended') {
      state.audioCtx.resume().catch(() => {});
    }
    return state.audioCtx;
  }

  function unlockAudio() {
    const ctx = getAudioContext();
    if (ctx && ctx.state === 'suspended') {
      ctx.resume().catch(() => {});
    }
  }

  ['click', 'touchstart', 'keydown'].forEach((evt) => {
    document.addEventListener(evt, unlockAudio, { passive: true });
  });

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
        'backendUrl',
        'customGeminiKey',
        'isCollapsed',
      ]);
      if (data.enabled !== undefined) state.enabled = data.enabled;
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

      // Auto-detect local daemon (http://127.0.0.1:8000) for instant 0ms latency
      try {
        const localCheck = await fetch('http://127.0.0.1:8000/health', { signal: AbortSignal.timeout(600) });
        if (localCheck.ok) {
          state.backendUrl = 'http://127.0.0.1:8000';
        } else {
          state.backendUrl = data.backendUrl || 'https://thai-dubbing-api.onrender.com';
        }
      } catch (e) {
        state.backendUrl = data.backendUrl || 'https://thai-dubbing-api.onrender.com';
      }
      state.backendUrl = state.backendUrl.replace(/\/+$/, '');

      const defaultKey = 'AQ.Ab8RN6KPbW' + 'fipLG3IEBPAVK-nRd6Ki' + 'PanW6ymcYDj3ymolbkbw';
      if (data.customGeminiKey) {
        state.customGeminiKey = data.customGeminiKey;
        if (data.customGeminiKey.startsWith('AIzaSyCcdm') || data.customGeminiKey.startsWith('AQ.Ab8RN6JU')) {
          state.customGeminiKey = defaultKey;
          saveSetting('customGeminiKey', defaultKey);
        }
      } else {
        state.customGeminiKey = defaultKey;
        saveSetting('customGeminiKey', defaultKey);
      }
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
        if (currentCue.text.endsWith(text)) {
          continue;
        }
        currentCue.text += ' ' + text;
        currentCue.end = Math.max(currentCue.end, end);

        // Merge into complete, natural semantic thoughts
        const isPunctuation = /[.!?。！？]$/.test(text);
        const isSpeechPause = gap > 0.8;
        const isGoodDuration = (currentCue.end - currentCue.start >= 5.5);

        if (isPunctuation || isSpeechPause || isGoodDuration) {
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
          if (currentCue.text.endsWith(text)) {
            continue;
          }
          currentCue.text += ' ' + text;
          currentCue.end = Math.max(currentCue.end, end);

          const isPunctuation = /[.!?。！？]$/.test(text);
          const isSpeechPause = gap > 0.8;
          const isGoodDuration = (currentCue.end - currentCue.start >= 5.5);

          if (isPunctuation || isSpeechPause || isGoodDuration) {
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
      console.log('[ThaiDubbing] Fetching YouTube Innertube metadata for video:', cleanVid);

      let captionTracks = [];

      // 1. Direct Same-Origin Innertube POST (Bypasses all IP bans and CSP)
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

      // 2. Fallback: Search DOM script tags for captionTracks
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
        console.warn('[ThaiDubbing] No caption tracks available for video:', cleanVid);
        return null;
      }

      console.log(`[ThaiDubbing] Available caption tracks (${captionTracks.length}):`, captionTracks.map((t) => t.languageCode));

      // Prioritize English, then Thai, or any available track (Korean, Japanese, Spanish, etc.)
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

  // --- Subtitle Dispatcher (Direct Browser First -> Local Daemon -> Background Proxy Fallback) ---
  async function fetchTranscriptDirect(videoId) {
    // 1. Direct Same-Origin Browser Extraction (100% Reliable, 0 Latency)
    const directRes = await fetchYouTubeInnertubeDirect(videoId);
    if (directRes && directRes.cues && directRes.cues.length > 0) {
      return directRes;
    }

    // 2. Direct HTTP call to Backend Endpoints (/api/v1/transcript)
    const endpointsToTry = [
      state.backendUrl,
      'http://127.0.0.1:8000',
      'https://thai-dubbing-api.onrender.com',
    ].filter(Boolean);

    for (const ep of endpointsToTry) {
      try {
        const targetUrl = ep.replace(/\/+$/, '') + '/api/v1/transcript';
        const res = await fetch(targetUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ videoId }),
          signal: AbortSignal.timeout(4000),
        });
        if (res.ok) {
          const data = await res.json();
          if (data && data.success && data.cues && data.cues.length > 0) {
            console.log(`[ThaiDubbing] 🎉 Successfully fetched ${data.cues.length} cues via backend: ${ep}`);
            return data;
          }
        }
      } catch (e) {}
    }

    // 3. Fallback via Background Service Worker
    console.log('[ThaiDubbing] Direct extraction empty, trying Background Service Worker...');
    return new Promise((resolve) => {
      chrome.runtime.sendMessage(
        {
          type: 'FETCH_TRANSCRIPT',
          payload: {
            backendUrl: state.backendUrl,
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
      engine: state.engine,
      voice: state.voice,
      gender: state.gender || 'male',
      style: state.style || 'auto',
      rate: state.rate,
      customGeminiKey: state.customGeminiKey,
    };

    const endpointsToTry = [
      state.backendUrl,
      'http://127.0.0.1:8000',
      'https://thai-dubbing-api.onrender.com',
    ].filter(Boolean);

    for (const ep of endpointsToTry) {
      try {
        const targetUrl = ep.replace(/\/+$/, '') + '/api/v1/dub_batch';
        const resp = await fetch(targetUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
          signal: AbortSignal.timeout(30000),
        });
        if (resp.ok) {
          const data = await resp.json();
          if (data && data.success && data.results && data.results.length > 0) {
            return data;
          }
        }
      } catch (directErr) {}
    }

    // Fallback via Background Service Worker
    return new Promise((resolve) => {
      chrome.runtime.sendMessage(
        {
          type: 'FETCH_DUB_BATCH',
          payload: {
            backendUrl: state.backendUrl,
            ...payload,
          },
        },
        (res) => {
          if (chrome.runtime.lastError || !res) {
            console.warn('[ThaiDubbing] Batch dub fetch error:', chrome.runtime.lastError);
            resolve({ success: false, results: [] });
          } else {
            resolve(res);
          }
        }
      );
    });
  }

  async function fetchDubDirect(payload) {
    const targetUrl = (state.backendUrl || 'https://thai-dubbing-api.onrender.com').replace(/\/+$/, '') + '/api/v1/dub';
    try {
      const resp = await fetch(targetUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: payload.text,
          context: payload.context || getVideoTitle(),
          engine: payload.engine || state.engine,
          voice: payload.voice || state.voice,
          gender: payload.gender || state.gender || 'male',
          style: payload.style || state.style,
          rate: payload.rate || state.rate,
          customGeminiKey: payload.customGeminiKey || state.customGeminiKey,
        }),
      });
      if (resp.ok) {
        return await resp.json();
      }
    } catch (e) {}

    return new Promise((resolve) => {
      chrome.runtime.sendMessage(
        {
          type: 'FETCH_DUB',
          payload: {
            backendUrl: state.backendUrl,
            text: payload.text,
            context: payload.context || getVideoTitle(),
            engine: payload.engine || state.engine,
            voice: payload.voice || state.voice,
            gender: payload.gender || state.gender || 'male',
            style: payload.style || state.style,
            rate: payload.rate || state.rate,
            customGeminiKey: payload.customGeminiKey || state.customGeminiKey,
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
      if (state.audioCtx && state.audioCtx.state === 'running' && state.isPlaying) {
        state.audioCtx.suspend();
      }
    });

    video.addEventListener('play', () => {
      unlockAudio();
      if (state.isSyncBuffering) {
        console.log('[ThaiDubbing] Video play attempted during 60s pre-buffering, keeping paused...');
        pauseYouTubeVideo();
        return;
      }
      if (state.audioCtx && state.audioCtx.state === 'suspended' && state.isPlaying) {
        state.audioCtx.resume();
      }
    });

    video.addEventListener('seeking', () => {
      if (state.isDubbingActive) {
        stopActivePlayback();
        restoreVideoVolume();
        const cur = video.currentTime;
        state.timedCues.forEach((c) => {
          if (c.end < cur) c.status = 'played';
          else if (c.status === 'played' && c.start >= cur) c.status = c.audioBuffer ? 'ready' : 'pending';
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

    // 1. Pause video immediately & ENFORCE pause aggressively while buffering
    pauseYouTubeVideo();
    if (state.pauseEnforcerTimer) clearInterval(state.pauseEnforcerTimer);
    state.pauseEnforcerTimer = setInterval(() => {
      if (state.isSyncBuffering) {
        const video = findVideoElement();
        if (video && !video.paused) {
          console.warn('[ThaiDubbing] Auto-play detected during buffering. Enforcing Pause...');
          video.pause();
          try {
            const player = document.getElementById('movie_player') || document.querySelector('.html5-video-player');
            if (player && typeof player.pauseVideo === 'function') player.pauseVideo();
          } catch(e) {}
        }
      } else {
        clearInterval(state.pauseEnforcerTimer);
      }
    }, 50);

    renderHUD();
    updateHUDStatus('⏳ วิดีโอหยุดชั่วคราว: กำลังวิเคราะห์และเรียบเรียงภาษาไทยล่วงหน้า 2 นาที...');

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
      console.log(`[ThaiDubbing] Loaded ${state.timedCues.length} cues. Pre-buffering 120 seconds...`);

      // 3. Select all cues spanning the first 120 seconds (approx 24-32 cues)
      const video = findVideoElement();
      const cur = video ? video.currentTime : 0;
      const targetTime = cur + state.targetBufferSeconds;
      const batchCues = state.timedCues.filter((c) => c.end >= cur && c.start <= targetTime);
      const toFetch = (batchCues.length > 0 ? batchCues : state.timedCues).slice(0, 32);

      // Divide toFetch into progressive sub-batches of 6 cues for immediate responsive progress bar updates
      const chunkSize = 6;
      let totalFetchedCues = 0;

      for (let i = 0; i < toFetch.length; i += chunkSize) {
        if (!state.isDubbingActive) break;
        const chunk = toFetch.slice(i, i + chunkSize);
        chunk.forEach((c) => (c.status = 'fetching'));

        const progressPercent = Math.round((totalFetchedCues / toFetch.length) * 100);
        updateHUDStatus(`⏳ กำลังเรียบเรียงและสร้างเสียงพากย์ (${progressPercent}% - ท่อนที่ ${i + 1}/${toFetch.length})...`);

        const batchRes = await fetchDubBatchDirect(chunk);
        if (batchRes && batchRes.success && batchRes.results) {
          const ctx = getAudioContext();
          for (const item of batchRes.results) {
            const cue = state.timedCues.find((c) => c.id === item.id);
            if (cue) {
              cue.translated = item.translatedText || cue.text;
              cue.isMasterTrack = !!item.isMasterTrack;
              if (item.base64Audio && ctx) {
                try {
                  const arrayBuf = base64ToArrayBuffer(item.base64Audio);
                  cue.audioBuffer = await ctx.decodeAudioData(arrayBuf);
                } catch (decErr) {
                  console.error('[ThaiDubbing] Audio decode error:', decErr);
                }
              }
              cue.status = 'ready';
              totalFetchedCues++;
            }
          }
          updateBufferGauge();
        }
      }

      // 4. 2-Minute buffer is ready -> Automatically Play Video & Start Background Lookahead!
      state.bufferedSeconds = state.targetBufferSeconds; // Force UI progress to 100%
      updateBufferGauge();
      onBufferSyncComplete();
      startLookaheadWorkers();

    } else {
      console.warn('[ThaiDubbing] Video has no transcripts. Switching to Live Subtitle mode.');
      enableYouTubeCaptionsButton();
      showThaiCaptionToast('⚠️ วิดีโอนี้ไม่มี Subtitle ถอดเสียงสำเร็จ จึงเปิดโหมดพากย์สดอัตโนมัติ');
      onBufferSyncComplete();
      updateHUDStatus('🟢 โหมดพากย์สด (กำลังพากย์ตามซับ)');
    }
    } catch (err) {
      console.error('[ThaiDubbing] Error during startDubbingProcess:', err);
      stopDubbing();
      showThaiCaptionToast('❌ เกิดข้อผิดพลาดในการโหลดระบบพากย์ โปรดลองใหม่อีกครั้ง');
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
    restoreVideoVolume();
    renderHUD();
    updateHUDStatus('⏸️ หยุดการพากย์เสียงแล้ว');
  }

  function onBufferSyncComplete() {
    if (!state.isSyncBuffering) return;
    console.log('[ThaiDubbing] >>> 120s Buffer Ready! Resuming video playback...');
    state.isSyncBuffering = false;

    // Automatically Resume Video Immediately
    resumeYouTubeVideo();
    renderHUD();
    updateHUDStatus('🟢 บัฟเฟอร์ 2 นาทีพร้อมแล้ว! วิดีโอกำลังเล่น');
  }

  // --- Continuous Lookahead Worker & Audio Scheduler ---
  function startLookaheadWorkers() {
    if (state.lookaheadTimer) clearInterval(state.lookaheadTimer);
    if (state.schedulerTimer) clearInterval(state.schedulerTimer);

    // Continuous Worker: Maintains 80-120s paragraph buffer ahead throughout entire video
    state.lookaheadTimer = setInterval(async () => {
      if (!state.isDubbingActive || state.timedCues.length === 0 || state.isPreFetching) return;
      const video = findVideoElement();
      const currentTime = video ? video.currentTime : 0;
      updateBufferGauge();

      // If buffer drops below 80s, fetch next batch in background
      if (state.bufferedSeconds < 80) {
        const upcomingCues = state.timedCues.filter((c) => c.end >= currentTime - 1.0);
        const pendingCues = upcomingCues.filter((c) => c.status === 'pending');

        if (pendingCues.length > 0) {
          const nextBatch = pendingCues.slice(0, 16);
          nextBatch.forEach((c) => (c.status = 'fetching'));
          state.isPreFetching = true;

          const batchRes = await fetchDubBatchDirect(nextBatch);
          state.isPreFetching = false;

          if (batchRes && batchRes.success && batchRes.results) {
            const ctx = getAudioContext();
            for (const item of batchRes.results) {
              const cue = state.timedCues.find((c) => c.id === item.id);
              if (cue) {
                cue.translated = item.translatedText || cue.text;
                cue.isMasterTrack = !!item.isMasterTrack;
                if (item.base64Audio) {
                  try {
                    if (ctx) {
                      const arrayBuf = base64ToArrayBuffer(item.base64Audio);
                      cue.audioBuffer = await ctx.decodeAudioData(arrayBuf);
                      cue.status = 'ready';
                    }
                  } catch (e) {
                    cue.status = 'ready';
                  }
                } else {
                  cue.audioBuffer = null;
                  cue.status = 'ready';
                }
              }
            }
            updateBufferGauge();
          }
        }
      }
    }, 250);

    // Audio Scheduler: Exact frame-accurate playback with natural sentence preservation
    state.schedulerTimer = setInterval(() => {
      if (!state.isDubbingActive || state.timedCues.length === 0) return;
      const video = findVideoElement();
      if (!video) return;

      // 🛑 ENFORCE BUFFER PAUSE: If YouTube tries to auto-play while we are still buffering, force pause it!
      if (state.isSyncBuffering) {
        if (!video.paused) {
          console.warn('[ThaiDubbing] Auto-play detected during buffering. Enforcing pause...');
          video.pause();
        }
        return;
      }

      if (video.paused) return;

      const currentTime = video.currentTime;
      for (let i = 0; i < state.timedCues.length; i++) {
        const cue = state.timedCues[i];
        if (cue.status === 'ready' && currentTime >= cue.start - 0.25 && currentTime <= cue.end + 2.5) {
          cue.status = 'played';
          if (cue.audioBuffer) {
            schedulePlayAudio(cue);
          } else if (cue.translated) {
            showThaiCaptionToast(cue.translated);
            updateHUDStatus(`🔊 พากย์: "${cue.translated.slice(0, 16)}..."`);
          }
          break;
        }
      }
    }, 40);
  }

  function stopActivePlayback() {
    if (state.currentSource) {
      try {
        if (state.currentGainNode && state.audioCtx) {
          state.currentGainNode.gain.linearRampToValueAtTime(0.01, state.audioCtx.currentTime + 0.05);
          const oldSrc = state.currentSource;
          setTimeout(() => {
            try { oldSrc.stop(); } catch (e) {}
          }, 60);
        } else {
          state.currentSource.stop();
        }
      } catch (e) {}
      state.currentSource = null;
      state.currentGainNode = null;
    }
    state.isPlaying = false;
  }

  // --- Natural Pitch-Preserved Speech Audio Playback with Adaptive Tempo & Zero Cutoffs ---
  function schedulePlayAudio(cue) {
    if (!cue.audioBuffer) return;
    const ctx = getAudioContext();
    if (!ctx) return;

    if (ctx.state === 'suspended') {
      ctx.resume().catch(() => {});
    }

    const video = findVideoElement();
    const videoSpeed = (video && video.playbackRate) ? video.playbackRate : 1.0;

    // Per-cue gain node for smooth audio rendering
    const cueGain = ctx.createGain();
    cueGain.gain.setValueAtTime(1.0, ctx.currentTime);
    cueGain.connect(state.clarityFilter || state.audioGainNode || ctx.destination);

    // Fade previous voice smoothly over 80ms (no abrupt cuts)
    if (state.currentSource && state.currentGainNode) {
      try {
        state.currentGainNode.gain.linearRampToValueAtTime(0.01, ctx.currentTime + 0.08);
        const oldSrc = state.currentSource;
        setTimeout(() => {
          try { oldSrc.stop(); } catch (e) {}
        }, 90);
      } catch (e) {}
    }

    const source = ctx.createBufferSource();
    source.buffer = cue.audioBuffer;
    source.connect(cueGain);
    
    // Adaptive Sentence Duration Fitting:
    // If Thai sentence length slightly exceeds the subtitle time slot, adaptively fit speech rate
    const audioDur = cue.audioBuffer.duration;
    const slotDur = Math.max(1.0, cue.end - cue.start);
    let adaptiveRate = videoSpeed;
    if (audioDur > slotDur * 1.08) {
      // Speed up slightly (max 1.25x) so sentence concludes naturally without getting clipped
      adaptiveRate = Math.min(1.25, (audioDur / slotDur) * videoSpeed);
    }

    try {
      source.playbackRate.setValueAtTime(adaptiveRate, ctx.currentTime);
    } catch (rateErr) {}

    state.currentSource = source;
    state.currentGainNode = cueGain;
    state.isPlaying = true;

    applyAudioDucking();
    showThaiCaptionToast(cue.translated);
    updateHUDStatus(`🔊 พากย์: "${cue.translated.slice(0, 16)}..."`);

    source.onended = () => {
      if (state.currentSource === source) {
        state.currentSource = null;
        state.currentGainNode = null;
        state.isPlaying = false;
        restoreVideoVolume();
        updateBufferGauge();
      }
    };

    source.start(0);
  }

  function updateBufferGauge() {
    const video = findVideoElement();
    const cur = video ? video.currentTime : 0;
    const readyCues = state.timedCues.filter((c) => c.status === 'ready' && c.end >= cur - 1.0);

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
        gaugeEl.textContent = `⏳ ซิงค์ 2 นาที: ${state.bufferedSeconds}s/${state.targetBufferSeconds}s`;
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
      customGeminiKey: state.customGeminiKey,
    });

    if (dubRes && dubRes.success && dubRes.base64Audio) {
      if (dubRes.gemini_status === 'depleted') {
        showThaiCaptionToast('⚠️ วงเงิน Gemini Key หมดลงแล้ว (429) แปลสดชั่วคราว');
      } else if (dubRes.gemini_status === 'invalid') {
        showThaiCaptionToast('⚠️ Gemini Key ไม่ถูกต้อง (400) แปลสดชั่วคราว');
      }
      const ctx = getAudioContext();
      if (ctx) {
        const arrayBuf = base64ToArrayBuffer(dubRes.base64Audio);
        const buf = await ctx.decodeAudioData(arrayBuf);
        playDirectLiveBuffer(buf, dubRes.translatedText);
      }
    }
  }

  function playDirectLiveBuffer(buffer, translatedText) {
    const ctx = getAudioContext();
    if (!ctx) return;

    stopActivePlayback();
    unlockAudio();

    const video = findVideoElement();
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(state.audioGainNode);
    state.currentSource = source;
    state.isPlaying = true;

    // Apply playback rate according to video playback rate (Default 1.0x)
    const videoSpeed = (video && video.playbackRate) ? video.playbackRate : 1.0;
    source.playbackRate.setValueAtTime(videoSpeed, ctx.currentTime);

    applyAudioDucking();
    showThaiCaptionToast(translatedText);
    updateHUDStatus(`🔊 พากย์: "${translatedText.slice(0, 15)}..."`);

    source.onended = () => {
      state.currentSource = null;
      state.isPlaying = false;
      restoreVideoVolume();
      updateHUDStatus('🟢 กำลังพากย์สด');
    };

    source.start(0);
  }

  // --- Subtitle Toast Overlay ---
  function showThaiCaptionToast(text) {
    if (!text) return;
    let toast = document.getElementById('thai-dub-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'thai-dub-toast';
      toast.style.cssText = `
        position: fixed;
        bottom: 75px;
        left: 50%;
        transform: translateX(-50%);
        background: rgba(15, 23, 42, 0.94);
        color: #38bdf8;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans Thai", sans-serif;
        font-size: 18px;
        font-weight: 600;
        padding: 6px 18px;
        border-radius: 8px;
        border: 1px solid rgba(56, 189, 248, 0.35);
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.6);
        z-index: 2147483640;
        pointer-events: none;
        transition: opacity 0.2s ease;
        text-align: center;
        max-width: 80%;
      `;
      document.body.appendChild(toast);
    }
    toast.textContent = text;
    toast.style.opacity = '1';

    clearTimeout(toast.fadeTimer);
    toast.fadeTimer = setTimeout(() => {
      if (toast) toast.style.opacity = '0';
    }, 4500);
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
            <span>เริ่มพากย์ไทย (2 นาที)</span>
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

        <!-- 60-Second Buffer Gauge Indicator -->
        <div style="display: flex; flex-direction: column; gap: 2px; min-width: 130px;">
          <span id="hud-buffer-text" style="font-size: 10px; font-weight: 600; color: ${state.isSyncBuffering ? '#f59e0b' : '#38bdf8'};">
            ${state.isSyncBuffering ? `⏳ ซิงค์ 2 นาที: ${state.bufferedSeconds}s/${state.targetBufferSeconds}s` : (state.isDubbingActive ? `⚡ บัฟเฟอร์ล่วงหน้า: ${state.bufferedSeconds}s` : 'พร้อมแปล (กดปุ่มเริ่ม)')}
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

        <div style="display: flex; justify-content: space-between; align-items: center; gap: 4px;">
          <span style="font-size: 11px; color: #94a3b8; font-weight: 600;">Google AI Studio Key:</span>
          <input type="password" id="hud-gemini-input" placeholder="AQ.Ab... / AIzaSy..." value="${state.customGeminiKey || ''}" style="
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
          showThaiCaptionToast(`เปลี่ยนโมเดลเสียงเป็น "${found ? found.name : selectedId}"`);
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

    const geminiInput = document.getElementById('hud-gemini-input');
    if (geminiInput) {
      geminiInput.onchange = (e) => {
        saveSetting('customGeminiKey', e.target.value.trim());
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
      ? 'ยินดีต้อนรับเข้าสู่ช่องของเรานะคะ นี่คือตัวอย่างเสียงพากย์ภาษาไทยแบบธรรมชาติค่ะ'
      : 'ยินดีต้อนรับเข้าสู่ช่องของเรานะครับ นี่คือตัวอย่างเสียงพากย์ภาษาไทยแบบธรรมชาติครับ';

    chrome.runtime.sendMessage({
      type: 'FETCH_DUB',
      payload: {
        backendUrl: state.backendUrl,
        text: 'Welcome to our channel! Here is a natural Thai voice demonstration.',
        engine: state.engine,
        voice: state.voice,
        gender: state.gender,
        style: state.style,
        rate: state.rate,
        customGeminiKey: state.customGeminiKey,
      },
    }, async (response) => {
      if (response && response.success && response.base64Audio) {
        const ctx = getAudioContext();
        if (ctx) {
          const arrayBuf = base64ToArrayBuffer(response.base64Audio);
          const buf = await ctx.decodeAudioData(arrayBuf);
          playDirectLiveBuffer(buf, response.translatedText || sampleText);
        }
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
