/**
 * Safari AI Thai Video Dubber - Popup UI Controller
 */

document.addEventListener('DOMContentLoaded', async () => {
  // DOM Elements
  const enabledToggle = document.getElementById('enabledToggle');
  const statusBadge = document.getElementById('statusBadge');
  const voiceSelect = document.getElementById('voiceSelect');
  const rateSelect = document.getElementById('rateSelect');
  const dubVolumeSlider = document.getElementById('dubVolumeSlider');
  const dubVolumeVal = document.getElementById('dubVolumeVal');
  const duckVolumeSlider = document.getElementById('duckVolumeSlider');
  const duckVolumeVal = document.getElementById('duckVolumeVal');
  const backendUrlInput = document.getElementById('backendUrl');
  const customKeyInput = document.getElementById('customKey');
  const testBtn = document.getElementById('testBtn');
  const connResult = document.getElementById('connResult');

  // Load Saved Settings from chrome.storage.local
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

    if (data.enabled !== undefined) {
      enabledToggle.checked = data.enabled;
    }
    updateStatusBadge(enabledToggle.checked);

    if (data.voice) voiceSelect.value = data.voice;
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

    if (data.backendUrl) {
      backendUrlInput.value = data.backendUrl;
    }

    if (data.customGeminiKey) {
      customKeyInput.value = data.customGeminiKey;
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

  voiceSelect.addEventListener('change', () => {
    saveSetting('voice', voiceSelect.value);
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
        ? '✅ พร้อมใช้งาน (Gemini Key ตั้งค่าแล้ว)'
        : '⚠️ เชื่อมต่อได้ แต่ยังไม่ได้ตั้ง GEMINI_API_KEY';

      connResult.className = 'conn-status success';
      connResult.innerHTML = `<strong>เชื่อมต่อสำเร็จ!</strong><br>${geminiStatus}`;
    } catch (err) {
      connResult.className = 'conn-status error';
      connResult.innerHTML = `<strong>เชื่อมต่อล้มเหลว:</strong><br>${err.message}. ตรวจสอบว่า Backend รันอยู่หรือไม่`;
    }
  });
});
