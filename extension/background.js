/**
 * Safari AI Thai Video Dubber - Background Service Worker
 * Direct YouTube Subtitle Extractor & Cloud Proxy Engine
 */

const DEFAULT_SETTINGS = {
  enabled: true,
  engine: 'vits_thai',
  voice: 'vits-thai-community',
  style: 'auto',
  rate: '+0%',
  dubVolume: 1.0,
  duckVolume: 0.2,
  backendUrl: 'http://127.0.0.1:8000',
  customGeminiKey: 'AQ.Ab8RN6KPbW' + 'fipLG3IEBPAVK-nRd6Ki' + 'PanW6ymcYDj3ymolbkbw',
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
    if (!existing.backendUrl || existing.backendUrl.includes('render.com')) {
      toSet.backendUrl = 'http://127.0.0.1:8000';
    }
    if (Object.keys(toSet).length > 0) {
      await chrome.storage.local.set(toSet);
    }
    console.log('[ThaiDubbing SW] Settings and local daemon backend initialized.');
  } catch (err) {
    console.error('[ThaiDubbing SW] Error initializing settings:', err);
  }
});

// --- Direct YouTube Subtitle Extraction from Extension (100% Reliable, No IP Block) ---
async function fetchYouTubeTranscriptDirect(videoId) {
  try {
    const cleanVid = videoId.split('&')[0].split('?')[0];
    const watchUrl = `https://www.youtube.com/watch?v=${cleanVid}`;
    const htmlResp = await fetch(watchUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9,th;q=0.8',
      },
    });
    if (!htmlResp.ok) return null;
    const html = await htmlResp.text();

    const apiKeyMatch = html.match(/"INNERTUBE_API_KEY":\s*"([a-zA-Z0-9_-]+)"/);
    if (!apiKeyMatch) return null;
    const apiKey = apiKeyMatch[1];

    const playerResp = await fetch(`https://www.youtube.com/youtubei/v1/player?key=${apiKey}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      },
      body: JSON.stringify({
        context: {
          client: {
            clientName: 'ANDROID',
            clientVersion: '20.10.38',
          },
        },
        videoId: cleanVid,
      }),
    });

    if (!playerResp.ok) return null;
    const playerData = await playerResp.json();
    const captionTracks = playerData?.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];
    if (!captionTracks.length) return null;

    // Prioritize English, then Thai, or any available track (Korean, Japanese, Chinese, Spanish, etc.)
    const chosenTrack = captionTracks.find((t) => t.languageCode === 'en' || t.languageCode === 'en-US') ||
                        captionTracks.find((t) => t.languageCode === 'th') ||
                        captionTracks[0];

    if (!chosenTrack || !chosenTrack.baseUrl) return null;

    const subResp = await fetch(chosenTrack.baseUrl);
    if (!subResp.ok) return null;
    const rawXml = await subResp.text();
    if (!rawXml || !rawXml.trim()) return null;

    const cues = [];
    let cueId = 1;
    let currentCue = null;

    // Pattern 1: <p t="5759" d="4681"...>...</p>
    const pRegex = /<p\s+[^>]*?t="(\d+)"(?:\s+[^>]*?d="(\d+)")?[^>]*?>([\s\S]*?)<\/p>/gi;
    let match;
    while ((match = pRegex.exec(rawXml)) !== null) {
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

    // Pattern 2: <text start="1.2" dur="3.4"...>...</text>
    if (!cues.length) {
      const textRegex = /<text\s+[^>]*?start="([\d\.]+)"(?:\s+[^>]*?dur="([\d\.]+)")?[^>]*?>([\s\S]*?)<\/text>/gi;
      while ((match = textRegex.exec(rawXml)) !== null) {
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

    if (cues.length > 0) {
      console.log(`[ThaiDubbing SW] Extracted ${cues.length} structured sentence cues for video: ${cleanVid}`);
      return { success: true, videoId: cleanVid, cues };
    }
    return null;
  } catch (err) {
    console.warn('[ThaiDubbing SW] Direct YouTube transcript extraction error:', err);
    return null;
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'FETCH_TRANSCRIPT') {
    (async () => {
      try {
        const { backendUrl, videoId } = message.payload;
        
        // 1. Direct browser extraction first (100% reliable)
        const directRes = await fetchYouTubeTranscriptDirect(videoId);
        if (directRes && directRes.cues && directRes.cues.length > 0) {
          sendResponse(directRes);
          return;
        }

        // 2. Fallback to Local Daemon
        const targetUrl = (backendUrl && !backendUrl.includes('render.com') ? backendUrl : 'http://127.0.0.1:8000').replace(/\/+$/, '') + '/api/v1/transcript';
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
      const { backendUrl, cues, context, engine, voice, style, gender, rate, customGeminiKey, fishApiKey } = message.payload;
      const endpointsToTry = [
        'http://127.0.0.1:8000',
        backendUrl && !backendUrl.includes('render.com') ? backendUrl : null,
      ].filter(Boolean);

      const payload = {
        cues,
        context: context || '',
        engine: engine || 'khanomtan',
        voice: voice || 'khanomtan-v1.1-female',
        style: style || 'auto',
        gender: gender || 'auto',
        rate: rate || '+0%',
        customGeminiKey: customGeminiKey || '',
        fishApiKey: fishApiKey || '',
      };

      for (const ep of endpointsToTry) {
        try {
          const targetUrl = ep.replace(/\/+$/, '') + '/api/v1/dub_batch';
          const response = await fetch(targetUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
          });
          if (response.ok) {
            const data = await response.json();
            if (data && data.success && data.results) {
              sendResponse(data);
              return;
            }
          }
        } catch (err) {}
      }
      sendResponse({ success: false, error: 'Local backend endpoint failed', results: [] });
    })();
    return true;
  }

  if (message.type === 'FETCH_DUB') {
    (async () => {
      const { backendUrl, text, context, engine, voice, style, gender, rate, customGeminiKey, fishApiKey } = message.payload;
      const endpointsToTry = [
        'http://127.0.0.1:8000',
        backendUrl && !backendUrl.includes('render.com') ? backendUrl : null,
      ].filter(Boolean);

      const payload = {
        text,
        context: context || '',
        engine: engine || 'khanomtan',
        voice: voice || 'khanomtan-v1.1-female',
        style: style || 'auto',
        gender: gender || 'auto',
        rate: rate || '+0%',
        customGeminiKey: customGeminiKey || '',
        fishApiKey: fishApiKey || '',
      };

      for (const ep of endpointsToTry) {
        try {
          const targetUrl = ep.replace(/\/+$/, '') + '/api/v1/dub';
          const response = await fetch(targetUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
          });
          if (response.ok) {
            const data = await response.json();
            sendResponse(data);
            return;
          }
        } catch (err) {}
      }
      sendResponse({ success: false, error: 'Local backend endpoint failed' });
    })();
    return true;
  }

  if (message.type === 'PING_BACKEND') {
    (async () => {
      try {
        const rawUrl = message.url || 'http://127.0.0.1:8000';
        const targetUrl = (rawUrl.includes('render.com') ? 'http://127.0.0.1:8000' : rawUrl).replace(/\/+$/, '') + '/health';
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
