/**
 * Safari AI Thai Video Dubber - Popup UI Controller (Alibaba Qwen Integration)
 */

const VITS_VOICES = [
  { id: 'qwen-thai-female', name: '👑 Alibaba Qwen-Max: หญิง (เปรมวดี • นุ่มนวล สมจริง 100% แนะนำ)' },
  { id: 'qwen-thai-male', name: '👑 Alibaba Qwen-Max: ชาย (นิวัฒน์ • ทุ้มนุ่ม มืออาชีพ สมจริง 100%)' },
];

document.addEventListener('DOMContentLoaded', async () => {
  // DOM Elements
  const enabledToggle = document.getElementById('enabledToggle');
  const subtitleToggle = document.getElementById('subtitleToggle');
  const statusBadge = document.getElementById('statusBadge');
  const engineSelect = document.getElementById('engineSelect');
  const translationModelSelect = document.getElementById('translationModelSelect');
  const voiceSelect = document.getElementById('voiceSelect');
  const styleGroup = document.getElementById('styleGroup');
  const styleSelect = document.getElementById('styleSelect');
  const rateSelect = document.getElementById('rateSelect');
  const dubVolumeSlider = document.getElementById('dubVolumeSlider');
  const dubVolumeVal = document.getElementById('dubVolumeVal');
  const duckVolumeSlider = document.getElementById('duckVolumeSlider');
  const duckVolumeVal = document.getElementById('duckVolumeVal');
  const backendUrlInput = document.getElementById('backendUrl');
  const customQwenKeyInput = document.getElementById('customQwenKey');
  const testBtn = document.getElementById('testBtn');
  const connResult = document.getElementById('connResult');

  function populateVoices(selectedVoice) {
    voiceSelect.innerHTML = '';
    VITS_VOICES.forEach((v) => {
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
      'showSubtitles',
      'engine',
      'translationModel',
      'voice',
      'style',
      'rate',
      'dubVolume',
      'duckVolume',
      'backendUrl',
      'customQwenKey',
    ]);

    if (data.enabled !== undefined) {
      enabledToggle.checked = data.enabled;
    }
    updateStatusBadge(enabledToggle.checked);

    if (subtitleToggle) {
      subtitleToggle.checked = !!data.showSubtitles;
    }

    const activeEngine = data.engine || 'qwen_tts';
    if (engineSelect) engineSelect.value = 'qwen_tts';

    if (translationModelSelect) {
      translationModelSelect.value = data.translationModel || 'qwen-max';
    }

    const defaultVoice = 'qwen-thai-female';
    populateVoices(data.voice || defaultVoice);

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

    const defaultQwenKey = 'sk-ws-H.DDLIDRI.FjEo.MEYCIQClFrpLY4yP_rpWWLjU-jTAsiMqqOeXOoMLE3s-6K08lAIhAJB8ZZVuWXYGmzhIxp9RXsZY-2AP_7ywEQCOWuEAmz_s';
    let qKey = data.customQwenKey || defaultQwenKey;
    if (customQwenKeyInput) {
      customQwenKeyInput.value = qKey;
    }
    if (!data.customQwenKey) {
      chrome.storage.local.set({ customQwenKey: qKey });
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

  if (subtitleToggle) {
    subtitleToggle.addEventListener('change', () => {
      saveSetting('showSubtitles', subtitleToggle.checked);
    });
  }

  engineSelect.addEventListener('change', () => {
    const eng = engineSelect.value;
    const defaultVoice = 'qwen-thai-female';
    populateVoices(defaultVoice);
    saveSetting('engine', eng);
    saveSetting('voice', defaultVoice);
  });

  if (translationModelSelect) {
    translationModelSelect.addEventListener('change', () => {
      saveSetting('translationModel', translationModelSelect.value);
    });
  }

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

  if (customQwenKeyInput) {
    customQwenKeyInput.addEventListener('change', () => {
      saveSetting('customQwenKey', customQwenKeyInput.value.trim());
    });
  }

  // --- AI Self-Learning Lexicon Handlers ---
  const learnedCountBadge = document.getElementById('learnedCountBadge');
  const learnTermInput = document.getElementById('learnTermInput');
  const learnPhoneticInput = document.getElementById('learnPhoneticInput');
  const learnSubmitBtn = document.getElementById('learnSubmitBtn');
  const learnResult = document.getElementById('learnResult');

  async function refreshLearnedCount() {
    const baseUrl = backendUrlInput.value.trim().replace(/\/+$/, '') || 'http://127.0.0.1:8000';
    try {
      const res = await fetch(`${baseUrl}/api/v1/learning/lexicon`);
      if (res.ok) {
        const data = await res.json();
        if (data && data.count && learnedCountBadge) {
          learnedCountBadge.textContent = `เรียนรู้แล้ว ${data.count} คำ`;
        }
      }
    } catch (e) {}
  }

  refreshLearnedCount();

  if (learnSubmitBtn) {
    learnSubmitBtn.addEventListener('click', async () => {
      const term = (learnTermInput.value || '').trim();
      const phonetic = (learnPhoneticInput.value || '').trim();
      if (!term || !phonetic) {
        alert('กรุณากรอกทั้งคำเดิมและคำอ่านภาษาไทย');
        return;
      }

      learnSubmitBtn.disabled = true;
      learnSubmitBtn.textContent = '⏳ กำลังบันทึก...';
      const baseUrl = backendUrlInput.value.trim().replace(/\/+$/, '') || 'http://127.0.0.1:8000';

      try {
        const res = await fetch(`${baseUrl}/api/v1/learning/learn`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ term, phonetic_thai: phonetic, category: 'user_taught' }),
        });

        if (res.ok) {
          learnResult.style.display = 'block';
          learnResult.style.color = '#4ade80';
          learnResult.textContent = `✅ AI เรียนรู้คำว่า "${term}" ➔ "${phonetic}" เรียบร้อยแล้ว!`;
          learnTermInput.value = '';
          learnPhoneticInput.value = '';
          refreshLearnedCount();
        } else {
          throw new Error('บันทึกล้มเหลว');
        }
      } catch (err) {
        learnResult.style.display = 'block';
        learnResult.style.color = '#f87171';
        learnResult.textContent = `❌ เกิดข้อผิดพลาด: ${err.message}`;
      } finally {
        learnSubmitBtn.disabled = false;
        learnSubmitBtn.textContent = '➕ สอน AI และบันทึกคำอ่าน';
        setTimeout(() => {
          if (learnResult) learnResult.style.display = 'none';
        }, 4000);
      }
    });
  }

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
      
      const qwenStatus = data.qwen_ready
        ? '✅ พร้อมใช้งาน (Alibaba Qwen-Max Flagship Ready)'
        : '⚠️ เชื่อมต่อได้ แต่ยังไม่ได้ตั้ง QWEN_API_KEY';

      const learnStats = data.learned_terms_count ? `<br>🧠 AI เรียนรู้คลังคำศัพท์แล้ว: ${data.learned_terms_count} คำ` : '';

      connResult.className = 'conn-status success';
      connResult.innerHTML = `<strong>เชื่อมต่อสำเร็จ!</strong><br>${qwenStatus}${learnStats}`;
      refreshLearnedCount();
    } catch (err) {
      connResult.className = 'conn-status error';
      connResult.innerHTML = `<strong>เชื่อมต่อล้มเหลว:</strong><br>${err.message}. ตรวจสอบว่า Backend รันอยู่หรือไม่`;
    }
  });
});
