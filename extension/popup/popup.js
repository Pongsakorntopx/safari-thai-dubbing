/**
 * Safari AI Thai Video Dubber - Popup UI Controller (Fish Speech Integration)
 */

const FISH_VOICES = [
  { id: 'fish-thai-male', name: '🐟 Fish Speech: ชายไทยธรรมชาติ (Thai Male Master)' },
  { id: 'fish-thai-female', name: '🐟 Fish Speech: หญิงไทยธรรมชาติ (Thai Female Master)' },
  { id: 'fish-thai-narrator', name: '🐟 Fish Speech: ผู้บรรยายสารคดี (Thai Documentary Narrator)' },
  { id: 'fish-custom-clone', name: '🐟 Fish Speech: โคลนเสียงตัวอย่าง 5-10 วิ (Zero-Shot Clone)' },
];

document.addEventListener('DOMContentLoaded', async () => {
  // DOM Elements
  const enabledToggle = document.getElementById('enabledToggle');
  const statusBadge = document.getElementById('statusBadge');
  const engineSelect = document.getElementById('engineSelect');
  const voiceSelect = document.getElementById('voiceSelect');
  const styleGroup = document.getElementById('styleGroup');
  const styleSelect = document.getElementById('styleSelect');
  const rateSelect = document.getElementById('rateSelect');
  const dubVolumeSlider = document.getElementById('dubVolumeSlider');
  const dubVolumeVal = document.getElementById('dubVolumeVal');
  const duckVolumeSlider = document.getElementById('duckVolumeSlider');
  const duckVolumeVal = document.getElementById('duckVolumeVal');
  const backendUrlInput = document.getElementById('backendUrl');
  const customKeyInput = document.getElementById('customKey');
  const testBtn = document.getElementById('testBtn');
  const connResult = document.getElementById('connResult');

  function populateVoices(selectedVoice) {
    voiceSelect.innerHTML = '';
    FISH_VOICES.forEach((v) => {
      const opt = document.createElement('option');
      opt.value = v.id;
      opt.textContent = v.name;
      if (v.id === selectedVoice) opt.selected = true;
      voiceSelect.appendChild(opt);
    });
  }

  // Load Saved Settings from chrome.storage.local
  try {
    const data = await chrome.storage.local.get([
      'enabled',
      'engine',
      'voice',
      'style',
      'rate',
      'dubVolume',
      'duckVolume',
      'backendUrl',
      'customGeminiKey',
    ]);

    if (data.enabled !== undefined) {
      enabledToggle.checked = data.enabled;
    }
    updateStatusBadge(enabledToggle.checked);

    const activeEngine = data.engine || 'google';
    engineSelect.value = activeEngine;

    const defaultVoice = activeEngine === 'edge' ? 'th-TH-PremwadeeNeural' : 'Puck';
    populateVoices(activeEngine, data.voice || defaultVoice);

    if (data.style) styleSelect.value = data.style;
    if (data.rate) rateSelect.value = data.rate;

    if (data.dubVolume !== undefined) {
      const pct = Math.round(data.dubVolume * 100);
      dubVolumeSlider.value = pct;
      dubVolumeVal.textContent = `${pct}%`;
    }

    if (data.duckVolume !== undefined) {
      const pct = Math.round(data.duckVolume * 100);
      duckVolumeSlider.value = pct;
      duckVolumeVal.textContent = `${pct}%`;
    }

    let bUrl = data.backendUrl || 'http://127.0.0.1:8000';
    backendUrlInput.value = bUrl;

    const defaultKey = 'AQ.Ab8RN6KPbW' + 'fipLG3IEBPAVK-nRd6Ki' + 'PanW6ymcYDj3ymolbkbw';
    let geminiKey = data.customGeminiKey || defaultKey;
    if (geminiKey.startsWith('AIzaSyCcdm') || geminiKey.startsWith('AQ.Ab8RN6JU')) {
      geminiKey = defaultKey;
      chrome.storage.local.set({ customGeminiKey: geminiKey });
    }
    customKeyInput.value = geminiKey;
    if (!data.customGeminiKey) {
      chrome.storage.local.set({ customGeminiKey: geminiKey });
    }
  } catch (err) {
    console.error('Failed to load settings in popup:', err);
  }

  // --- Helper Functions ---
  function updateStatusBadge(isEnabled) {
    if (isEnabled) {
      statusBadge.textContent = 'เปิดใช้งาน';
      statusBadge.className = 'badge active';
    } else {
      statusBadge.textContent = 'ปิดการทำงาน';
      statusBadge.className = 'badge disabled';
    }
  }

  async function saveSetting(key, value) {
    try {
      await chrome.storage.local.set({ [key]: value });
    } catch (err) {
      console.error(`Failed to save setting ${key}:`, err);
    }
  }

  // --- Event Listeners ---
  enabledToggle.addEventListener('change', () => {
    const isChecked = enabledToggle.checked;
    updateStatusBadge(isChecked);
    saveSetting('enabled', isChecked);
  });

  engineSelect.addEventListener('change', () => {
    const eng = engineSelect.value;
    const defaultVoice = eng === 'edge' ? 'th-TH-PremwadeeNeural' : 'Aoede';
    populateVoices(eng, defaultVoice);
    saveSetting('engine', eng);
    saveSetting('voice', defaultVoice);
  });

  voiceSelect.addEventListener('change', () => {
    saveSetting('voice', voiceSelect.value);
  });

  styleSelect.addEventListener('change', () => {
    saveSetting('style', styleSelect.value);
  });

  rateSelect.addEventListener('change', () => {
    saveSetting('rate', rateSelect.value);
  });

  dubVolumeSlider.addEventListener('input', () => {
    const val = parseInt(dubVolumeSlider.value, 10);
    dubVolumeVal.textContent = `${val}%`;
    saveSetting('dubVolume', val / 100);
  });

  duckVolumeSlider.addEventListener('input', () => {
    const val = parseInt(duckVolumeSlider.value, 10);
    duckVolumeVal.textContent = `${val}%`;
    saveSetting('duckVolume', val / 100);
  });

  backendUrlInput.addEventListener('change', () => {
    const url = backendUrlInput.value.trim().replace(/\/+$/, '');
    backendUrlInput.value = url;
    saveSetting('backendUrl', url);
  });

  customKeyInput.addEventListener('change', () => {
    saveSetting('customGeminiKey', customKeyInput.value.trim());
  });

  // --- Test Connection Handler ---
  testBtn.addEventListener('click', async () => {
    const baseUrl = backendUrlInput.value.trim().replace(/\/+$/, '');
    connResult.className = 'conn-status';
    connResult.style.display = 'block';
    connResult.textContent = 'กำลังตรวจสอบการเชื่อมต่อ...';

    try {
      const res = await fetch(`${baseUrl}/health`, { method: 'GET' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      
      const geminiStatus = data.gemini_ready
        ? '✅ พร้อมใช้งาน (Gemini 2.0 & Unlock-TTS Ready)'
        : '⚠️ เชื่อมต่อได้ แต่ยังไม่ได้ตั้ง GEMINI_API_KEY';

      connResult.className = 'conn-status success';
      connResult.innerHTML = `<strong>เชื่อมต่อสำเร็จ!</strong><br>${geminiStatus}`;
    } catch (err) {
      connResult.className = 'conn-status error';
      connResult.innerHTML = `<strong>เชื่อมต่อล้มเหลว:</strong><br>${err.message}. ตรวจสอบว่า Backend รันอยู่หรือไม่`;
    }
  });
});
