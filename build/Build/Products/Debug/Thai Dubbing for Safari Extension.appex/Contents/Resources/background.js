/**
 * Safari AI Thai Video Dubber - Background Service Worker
 */

const DEFAULT_SETTINGS = {
  enabled: true,
  voice: 'th-TH-PremwadeeNeural',
  rate: '+5%',
  dubVolume: 1.0,
  duckVolume: 0.2, // Duck YouTube volume down to 20%
  backendUrl: 'http://localhost:8000',
  customGeminiKey: '',
};

// Initialize default settings on install or update
chrome.runtime.onInstalled.addListener(async (details) => {
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
    console.log('[ThaiDubbing] Extension installed/updated. Default settings initialized.');
  } catch (err) {
    console.error('[ThaiDubbing] Error initializing settings:', err);
  }
});

// Relay messages if needed between popup and active tabs
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'PING') {
    sendResponse({ status: 'PONG' });
    return false;
  }
  return false;
});
