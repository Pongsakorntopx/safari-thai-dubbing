/**
 * Safari AI Thai Video Dubber - Background Service Worker
 * Proxies HTTP requests to avoid Safari Mixed Content and CORS restrictions.
 */

const DEFAULT_SETTINGS = {
  enabled: true,
  engine: 'edge',
  voice: 'th-TH-PremwadeeNeural',
  style: 'auto',
  rate: '+0%',
  dubVolume: 1.0,
  duckVolume: 0.2,
  backendUrl: 'https://pongsakorntopz-thai-dubbing-api.hf.space',
  customGeminiKey: '',
};

chrome.runtime.onInstalled.addListener(async () => {
  try {
    const existing = await chrome.storage.local.get(null);
    const toSet = {};
    for (const [key, value] of Object.entries(DEFAULT_SETTINGS)) {
      if (existing[key] === undefined) {
        toSet[key] = value;
      }
    }
    if (Object.keys(toSet).length > 0) {
      await chrome.storage.local.set(toSet);
    }
    console.log('[ThaiDubbing SW] Default settings initialized.');
  } catch (err) {
    console.error('[ThaiDubbing SW] Error initializing settings:', err);
  }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'FETCH_TRANSCRIPT') {
    (async () => {
      try {
        const { backendUrl, videoId } = message.payload;
        const targetUrl = (backendUrl || 'http://localhost:8000').replace(/\/+$/, '') + '/api/v1/transcript';
        const res = await fetch(targetUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ videoId }),
        });
        if (!res.ok) {
          const errText = await res.text();
          sendResponse({ success: false, error: `HTTP ${res.status}: ${errText}`, cues: [] });
          return;
        }
        const data = await res.json();
        sendResponse(data);
      } catch (err) {
        console.error('[ThaiDubbing SW] Transcript fetch error:', err);
        sendResponse({ success: false, error: err.message, cues: [] });
      }
    })();
    return true;
  }

  if (message.type === 'FETCH_DUB_BATCH') {
    (async () => {
      try {
        const { backendUrl, cues, context, engine, voice, style, gender, rate, customGeminiKey } = message.payload;
        const targetUrl = (backendUrl || 'http://localhost:8000').replace(/\/+$/, '') + '/api/v1/dub_batch';

        const response = await fetch(targetUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            cues,
            context: context || '',
            engine: engine || 'edge',
            voice: voice || 'th-TH-PremwadeeNeural',
            style: style || 'auto',
            gender: gender || 'auto',
            rate: rate || '+0%',
            customGeminiKey: customGeminiKey || '',
          }),
        });

        if (!response.ok) {
          const errText = await response.text();
          sendResponse({ success: false, error: `HTTP ${response.status}: ${errText}`, results: [] });
          return;
        }

        const data = await response.json();
        sendResponse(data);
      } catch (err) {
        console.error('[ThaiDubbing SW] Batch Dub error:', err);
        sendResponse({ success: false, error: err.message, results: [] });
      }
    })();
    return true;
  }

  if (message.type === 'FETCH_DUB') {
    (async () => {
      try {
        const { backendUrl, text, context, engine, voice, style, gender, rate, customGeminiKey } = message.payload;
        const targetUrl = (backendUrl || 'http://localhost:8000').replace(/\/+$/, '') + '/api/v1/dub';

        const response = await fetch(targetUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text,
            context: context || '',
            engine: engine || 'edge',
            voice: voice || 'th-TH-PremwadeeNeural',
            style: style || 'auto',
            gender: gender || 'auto',
            rate: rate || '+0%',
            customGeminiKey: customGeminiKey || '',
          }),
        });

        if (!response.ok) {
          const errText = await response.text();
          sendResponse({ success: false, error: `HTTP ${response.status}: ${errText}` });
          return;
        }

        const data = await response.json();
        sendResponse({
          success: true,
          translatedText: data.translatedText || '',
          base64Audio: data.base64Audio || '',
          cached: !!data.cached,
        });
      } catch (err) {
        console.error('[ThaiDubbing SW] Fetch Dub error:', err);
        sendResponse({ success: false, error: err.message });
      }
    })();
    return true;
  }

  if (message.type === 'PING_BACKEND') {
    (async () => {
      try {
        const targetUrl = (message.url || 'http://localhost:8000').replace(/\/+$/, '') + '/health';
        const res = await fetch(targetUrl);
        const data = await res.json();
        sendResponse({ success: true, data });
      } catch (err) {
        sendResponse({ success: false, error: err.message });
      }
    })();
    return true;
  }

  return false;
});
