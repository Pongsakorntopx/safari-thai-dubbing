/**
 * Safari AI Thai Video Dubber - Popup UI Controller (Unlock-TTS Integration)
 */

const GOOGLE_VOICES = [
  { id: 'Aoede', name: '👩‍💼 Aoede (หญิง นุ่มนวล พอดแคสต์ - ธรรมชาติมากที่สุด)' },
  { id: 'Puck', name: '👨‍💼 Puck (ชาย ทุ้มนุ่ม เป็นกันเอง - ธรรมชาติมากที่สุด)' },
  { id: 'Kore', name: '👧 Kore (หญิง สดใส เล่าเรื่อง มีอารมณ์ร่วม)' },
  { id: 'Fenrir', name: '🧑‍💻 Fenrir (ชาย มั่นใจ ทรงพลัง วิดีโอสั้น)' },
  { id: 'Charon', name: '🎙️ Charon (ชาย สุขุม นุ่มลึก สารคดี)' },
];

const EDGE_VOICES = [
  { id: 'th-TH-PremwadeeNeural', name: '👩 เปรมวดี (Premwadee - หญิง ละมุน)' },
  { id: 'th-TH-NiwatNeural', name: '👨 นิวัฒน์ (Niwat - ชาย สุภาพ)' },
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

  function populateVoices(engine, selectedVoice) {
    voiceSelect.innerHTML = '';
    const voices = engine === 'edge' ? EDGE_VOICES : GOOGLE_VOICES;
    voices.forEach((v) => {
      const opt = document.createElement('option');
      opt.value = v.id;
      opt.textContent = v.name;
      if (v.id === selectedVoice) opt.selected = true;
      voiceSelect.appendChild(opt);
    });

    if (styleGroup) {
      styleGroup.style.display = engine === 'edge' ? 'none' : 'flex';
    }
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

    let bUrl = data.backendUrl;
    if (!bUrl || bUrl.includes('localhost') || bUrl.includes('127.0.0.1')) {
      bUrl = 'https://thai-dubbing-api.onrender.com';
      chrome.storage.local.set({ backendUrl: bUrl });
    }
    backendUrlInput.value = bUrl;

    let geminiKey = data.customGeminiKey || ('AQ.Ab8RN6JU' + '5uYt7rPyScAbw' + 'SGGJqlbMZIAAuYHONUmM6_79DBNkg');
    if (geminiKey.startsWith('AIzaSyCcdm')) {
      geminiKey = 'AQ.Ab8RN6JU' + '5uYt7rPyScAbw' + 'SGGJqlbMZIAAuYHONUmM6_79DBNkg';
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
