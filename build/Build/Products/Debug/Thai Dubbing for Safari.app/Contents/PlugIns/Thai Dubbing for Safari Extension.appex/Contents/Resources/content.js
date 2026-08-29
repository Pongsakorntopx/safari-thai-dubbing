/**
 * Safari AI Thai Video Dubber - YouTube Content Script
 * Handles:
 * 1. YouTube Subtitle Interception & Sentence Chunking
 * 2. Backend Translation & TTS Audio Fetching
 * 3. Audio Playback Queue Management
 * 4. Video Audio Ducking (Smart Volume Dimming & Restoration)
 * 5. Player Sync (Pause, Seek, Playback rate matching)
 */

(function () {
  'use strict';

  // --- Configuration & State ---
  const state = {
    enabled: true,
    voice: 'th-TH-PremwadeeNeural',
    rate: '+5%',
    dubVolume: 1.0,
    duckVolume: 0.2,
    backendUrl: 'http://localhost:8000',
    customGeminiKey: '',
    
    // Internal Runtime State
    lastProcessedText: '',
    recentContext: [],
    audioQueue: [],
    isPlaying: false,
    currentAudio: null,
    isDucking: false,
    originalVideoVolume: 1.0,
    videoElement: null,
    captionObserver: null,
    chunkTimer: null,
    pendingChunks: [],
  };

  // --- Settings Loader & Realtime Sync ---
  async function loadSettings() {
    try {
      const data = await chrome.storage.local.get([
        'enabled',
        'voice',
        'rate',
        'dubVolume',
        'duckVolume',
        'backendUrl',
        'customGeminiKey',
      ]);
      if (data.enabled !== undefined) state.enabled = data.enabled;
      if (data.voice) state.voice = data.voice;
      if (data.rate) state.rate = data.rate;
      if (data.dubVolume !== undefined) state.dubVolume = data.dubVolume;
      if (data.duckVolume !== undefined) state.duckVolume = data.duckVolume;
      if (data.backendUrl) state.backendUrl = data.backendUrl.replace(/\/+$/, '');
      if (data.customGeminiKey) state.customGeminiKey = data.customGeminiKey;
      console.log('[ThaiDubbing] Settings loaded:', state);
    } catch (err) {
      console.error('[ThaiDubbing] Failed to load settings:', err);
    }
  }

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'local') {
      for (const [key, change] of Object.entries(changes)) {
        state[key] = change.newValue;
        if (key === 'enabled' && !change.newValue) {
          clearQueueAndStop();
          restoreVideoVolume();
        }
      }
      console.log('[ThaiDubbing] Settings updated dynamically:', changes);
    }
  });

  // --- Video Element Management & Event Hooks ---
  function findVideoElement() {
    const video = document.querySelector('video.html5-main-video') || document.querySelector('video');
    if (video && video !== state.videoElement) {
      state.videoElement = video;
      state.originalVideoVolume = video.volume;
      attachVideoEvents(video);
      console.log('[ThaiDubbing] Attached to video element.');
    }
    return state.videoElement;
  }

  function attachVideoEvents(video) {
    video.addEventListener('pause', () => {
      if (state.currentAudio && !state.currentAudio.paused) {
        state.currentAudio.pause();
      }
    });

    video.addEventListener('play', () => {
      if (state.currentAudio && state.currentAudio.paused && state.isPlaying) {
        state.currentAudio.play().catch(() => {});
      }
    });

    video.addEventListener('seeking', () => {
      console.log('[ThaiDubbing] Video seeking detected. Clearing dub queue.');
      clearQueueAndStop();
      restoreVideoVolume();
    });

    video.addEventListener('ended', () => {
      clearQueueAndStop();
      restoreVideoVolume();
    });

    video.addEventListener('volumechange', () => {
      // If volume change occurred when not ducked, update user's base volume
      if (!state.isDucking && video.volume > 0) {
        state.originalVideoVolume = video.volume;
      }
    });
  }

  // --- Audio Ducking (Smooth Volume Transitions) ---
  function applyAudioDucking() {
    const video = findVideoElement();
    if (!video || state.isDucking) return;

    state.isDucking = true;
    if (video.volume > 0 && !video.muted) {
      state.originalVideoVolume = video.volume;
      const targetVolume = Math.max(0.05, state.originalVideoVolume * state.duckVolume);
      fadeVolume(video, video.volume, targetVolume, 150);
    }
  }

  function restoreVideoVolume() {
    const video = findVideoElement();
    if (!video || !state.isDucking) return;

    state.isDucking = false;
    const targetVolume = state.originalVideoVolume;
    fadeVolume(video, video.volume, targetVolume, 250);
  }

  function fadeVolume(mediaEl, startVol, endVol, durationMs) {
    const steps = 10;
    const stepTime = durationMs / steps;
    const volStep = (endVol - startVol) / steps;
    let currentStep = 0;

    const interval = setInterval(() => {
      currentStep++;
      const nextVol = startVol + volStep * currentStep;
      mediaEl.volume = Math.min(1.0, Math.max(0.0, nextVol));
      if (currentStep >= steps) {
        mediaEl.volume = Math.min(1.0, Math.max(0.0, endVol));
        clearInterval(interval);
      }
    }, stepTime);
  }

  // --- Audio Queue & Playback Management ---
  function clearQueueAndStop() {
    state.audioQueue = [];
    state.pendingChunks = [];
    if (state.chunkTimer) {
      clearTimeout(state.chunkTimer);
      state.chunkTimer = null;
    }
    if (state.currentAudio) {
      state.currentAudio.pause();
      state.currentAudio.src = '';
      state.currentAudio = null;
    }
    state.isPlaying = false;
  }

  function enqueueDubbingAudio(audioBlobUrl, translatedText) {
    state.audioQueue.push({ url: audioBlobUrl, text: translatedText });
    if (!state.isPlaying) {
      playNextInQueue();
    }
  }

  function playNextInQueue() {
    if (!state.enabled || state.audioQueue.length === 0) {
      state.isPlaying = false;
      restoreVideoVolume();
      return;
    }

    const video = findVideoElement();
    if (video && video.paused) {
      // Don't start next audio if video is paused
      state.isPlaying = false;
      return;
    }

    state.isPlaying = true;
    const item = state.audioQueue.shift();
    const audio = new Audio(item.url);
    state.currentAudio = audio;
    audio.volume = Math.min(1.0, Math.max(0.0, state.dubVolume));

    // Duck video volume
    applyAudioDucking();

    // Show on-screen toast indicator
    showThaiCaptionToast(item.text);

    audio.onended = () => {
      URL.revokeObjectURL(item.url);
      state.currentAudio = null;
      if (state.audioQueue.length === 0) {
        state.isPlaying = false;
        restoreVideoVolume();
      } else {
        playNextInQueue();
      }
    };

    audio.onerror = (err) => {
      console.warn('[ThaiDubbing] Audio playback error:', err);
      URL.revokeObjectURL(item.url);
      state.currentAudio = null;
      playNextInQueue();
    };

    audio.play().catch((err) => {
      console.warn('[ThaiDubbing] Audio play prevented:', err);
      state.currentAudio = null;
      playNextInQueue();
    });
  }

  // --- Subtitle Toast Overlay ---
  function showThaiCaptionToast(text) {
    if (!text) return;
    let toast = document.getElementById('thai-dub-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'thai-dub-toast';
      toast.style.cssText = `
        position: absolute;
        bottom: 75px;
        left: 50%;
        transform: translateX(-50%);
        background: rgba(15, 23, 42, 0.85);
        color: #38bdf8;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans Thai", sans-serif;
        font-size: 18px;
        font-weight: 600;
        padding: 6px 16px;
        border-radius: 8px;
        border: 1px solid rgba(56, 189, 248, 0.3);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
        z-index: 9999;
        pointer-events: none;
        transition: opacity 0.2s ease;
        text-align: center;
        max-width: 80%;
      `;
      const player = document.querySelector('#movie_player') || document.body;
      player.appendChild(toast);
    }
    toast.textContent = text;
    toast.style.opacity = '1';

    // Auto fade after 4 seconds
    clearTimeout(toast.fadeTimer);
    toast.fadeTimer = setTimeout(() => {
      if (toast) toast.style.opacity = '0';
    }, 4000);
  }

  // --- Subtitle Extraction & Chunking Logic ---
  async function requestDubbing(sentence) {
    if (!state.enabled || !sentence || sentence.trim().length < 2) return;

    const cleanText = sentence.trim();
    if (cleanText === state.lastProcessedText) return;
    state.lastProcessedText = cleanText;

    const contextStr = state.recentContext.slice(-2).join(' ');

    console.log(`[ThaiDubbing] Processing English subtitle: "${cleanText}"`);

    try {
      const headers = { 'Content-Type': 'application/json' };
      if (state.customGeminiKey) {
        headers['X-Gemini-Key'] = state.customGeminiKey;
      }

      const response = await fetch(`${state.backendUrl}/api/v1/dub`, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({
          text: cleanText,
          context: contextStr,
          voice: state.voice,
          rate: state.rate,
        }),
      });

      if (!response.ok) {
        throw new Error(`Dubbing API returned ${response.status} ${response.statusText}`);
      }

      // Extract translated text from header
      let translatedText = '';
      const encodedHeader = response.headers.get('X-Translated-Text');
      if (encodedHeader) {
        try {
          translatedText = decodeURIComponent(encodedHeader);
        } catch (e) {
          translatedText = encodedHeader;
        }
      }

      // Update recent context ring buffer
      state.recentContext.push(cleanText);
      if (state.recentContext.length > 5) state.recentContext.shift();

      const blob = await response.blob();
      const audioUrl = URL.createObjectURL(blob);
      enqueueDubbingAudio(audioUrl, translatedText);
    } catch (err) {
      console.error('[ThaiDubbing] Failed to fetch dubbing audio:', err);
    }
  }

  function handleCaptionFragment(text) {
    if (!state.enabled || !text) return;
    const trimmed = text.replace(/[\r\n]+/g, ' ').trim();
    if (!trimmed || trimmed === state.pendingChunks[state.pendingChunks.length - 1]) return;

    // Check if sentence looks complete (ends in punctuation or long pause)
    const isPunctuationEnding = /[.!?]$/.test(trimmed);

    if (state.chunkTimer) {
      clearTimeout(state.chunkTimer);
    }

    state.pendingChunks.push(trimmed);

    if (isPunctuationEnding) {
      const fullSentence = state.pendingChunks.join(' ');
      state.pendingChunks = [];
      requestDubbing(fullSentence);
    } else {
      // Debounce: Wait 500ms for caption stream to settle before dispatching chunk
      state.chunkTimer = setTimeout(() => {
        if (state.pendingChunks.length > 0) {
          const combined = state.pendingChunks.join(' ');
          state.pendingChunks = [];
          requestDubbing(combined);
        }
      }, 500);
    }
  }

  // --- YouTube Caption DOM Observer ---
  function observeCaptions() {
    const captionContainer =
      document.querySelector('.ytp-caption-window-bottom') ||
      document.querySelector('#movie_player .caption-window') ||
      document.querySelector('#movie_player');

    if (!captionContainer) {
      setTimeout(observeCaptions, 1000);
      return;
    }

    if (state.captionObserver) {
      state.captionObserver.disconnect();
    }

    state.captionObserver = new MutationObserver((mutations) => {
      if (!state.enabled) return;

      const segments = document.querySelectorAll('.ytp-caption-segment');
      if (segments && segments.length > 0) {
        const textContent = Array.from(segments)
          .map((s) => s.textContent)
          .join(' ')
          .trim();
        if (textContent) {
          handleCaptionFragment(textContent);
        }
      }
    });

    state.captionObserver.observe(captionContainer, {
      childList: true,
      subtree: true,
      characterData: true,
    });

    console.log('[ThaiDubbing] Caption observer attached to YouTube player.');
  }

  // --- Initialization ---
  async function init() {
    await loadSettings();
    findVideoElement();
    observeCaptions();

    // Re-verify observer periodically in case of YouTube SPA page transitions
    setInterval(() => {
      findVideoElement();
      const currentContainer = document.querySelector('.ytp-caption-window-bottom') || document.querySelector('#movie_player');
      if (currentContainer && (!state.captionObserver || !document.contains(currentContainer))) {
        observeCaptions();
      }
    }, 3000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
