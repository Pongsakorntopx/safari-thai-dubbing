"""
Thai VITS & KhanomTan TTS v1.1 Master Engine (โมเดล VITS ภาษาไทยแท้ & ขนมตาล v1.1)
Voices:
  1. 🧁 ขนมตาล v1.1: หญิง (khanomtan-v1.1-female) - Linda
  2. 🧁 ขนมตาล v1.1: ชาย (khanomtan-v1.1-male) - Thorsten
  3. 🇹🇭 VITS Thai: หญิง (vits-thai-female) - MMS VITS Standard
  4. 🇹🇭 VITS Thai: ชาย (vits-thai-male) - MMS VITS Resonant Male
"""

import asyncio
import io
import logging
import os
import re
import tempfile
import threading
from typing import Dict, Optional

import numpy as np
import scipy.signal
import soundfile as sf
import torch

# Compatibility patch for transformers with TTS library
try:
    import transformers.pytorch_utils
    if not hasattr(transformers.pytorch_utils, "isin_mps_friendly"):
        transformers.pytorch_utils.isin_mps_friendly = getattr(torch, "isin", None)
except Exception:
    pass

try:
    from transformers import AutoTokenizer, VitsModel
except Exception:
    VitsModel = None
    AutoTokenizer = None

logger = logging.getLogger(__name__)

# Master Voice Registry for KhanomTan v1.1 and VITS Thai
VOICE_REGISTRY: Dict[str, Dict[str, str]] = {
    "khanomtan-v1.1-female": {
        "id": "khanomtan-v1.1-female",
        "name": "🧁 ขนมตาล v1.1: หญิง (KhanomTan Thai Female • Apache 2.0)",
        "gender": "female",
        "engine": "khanomtan",
        "speaker_idx": "Linda",
        "desc": "โมเดลเสียงขนมตาล v1.1 เสียงผู้หญิง นุ่มนวล ชัดเจน เป็นธรรมชาติ",
    },
    "khanomtan-v1.1-male": {
        "id": "khanomtan-v1.1-male",
        "name": "🧁 ขนมตาล v1.1: ชาย (KhanomTan Thai Male • Apache 2.0)",
        "gender": "male",
        "engine": "khanomtan",
        "speaker_idx": "Thorsten",
        "desc": "โมเดลเสียงขนมตาล v1.1 เสียงผู้ชาย อบอุ่น ทุ้มนุ่ม ชัดถ้อยชัดคำ",
    },
    "vits-thai-female": {
        "id": "vits-thai-female",
        "name": "🇹🇭 VITS Thai: หญิง (VITS Thai Female • AI Community)",
        "gender": "female",
        "engine": "vits_thai",
        "desc": "โมเดล VITS เสียงไทยแท้ เสียงผู้หญิง วรรณยุกต์ 5 เสียงเป๊ะ สระสั้น-ยาวแม่นยำ",
    },
    "vits-thai-male": {
        "id": "vits-thai-male",
        "name": "🇹🇭 VITS Thai: ชาย (VITS Thai Male • AI Community)",
        "gender": "male",
        "engine": "vits_thai",
        "desc": "โมเดล VITS เสียงไทยแท้ เสียงผู้ชาย ทุ้มลึก สุภาพ ชัดเจน",
    },
}


def clean_thai_text_for_speech(text: str) -> str:
    """Clean text and apply AI Learned Phonetics for Thai VITS & KhanomTan models."""
    if not text:
        return ""
    t = text.strip()
    t = re.sub(r"[\"\'\`\<\>\[\]\(\)\{\}\*\#\_]", "", t)

    # 1. Expand common acronyms
    acronym_map = {
        r"\bAI\b": "เอไอ",
        r"\bAPI\b": "เอพีไอ",
        r"\bUI\b": "ยูไอ",
        r"\bUX\b": "ยูเอ็กซ์",
        r"\biOS\b": "ไอโอเอส",
        r"\bmacOS\b": "แมคโอเอส",
        r"\bPython\b": "ไพธอน",
        r"\bYouTube\b": "ยูทูป",
        r"\bSafari\b": "ซาฟารี",
        r"\bURL\b": "ยูอาร์แอล",
        r"\bCPU\b": "ซีพียู",
        r"\bGPU\b": "จีพียู",
        r"\bRAM\b": "แรม",
        r"\bApp\b": "แอป",
        r"\bApps\b": "แอป",
        r"\bWeb\b": "เว็บ",
    }
    for eng, th in acronym_map.items():
        t = re.sub(eng, th, t, flags=re.IGNORECASE)

    # 2. Apply AI Self-Learning Phonetic Memory (Dynamic vocabulary & custom learned pronunciations)
    try:
        from app.learning_engine import learning_engine
        t = learning_engine.apply_learned_phonetics(t)
    except Exception:
        pass

    t = re.sub(r"\s+", " ", t)
    return t.strip()


def pitch_shift_male(audio_np: np.ndarray, sr: int = 16000) -> np.ndarray:
    """Pitch shift to create a resonant, warm, natural Thai male voice from VITS."""
    try:
        import librosa
        shifted = librosa.effects.pitch_shift(audio_np, sr=sr, n_steps=-3.5)
        return shifted
    except Exception:
        # Fallback DSP pitch shift using resample + linear interpolation
        factor = 0.82
        indices = np.round(np.arange(0, len(audio_np), factor)).astype(int)
        indices = indices[indices < len(audio_np)]
        return audio_np[indices]


# Set PyTorch CPU thread limit to minimize memory overhead
try:
    torch.set_num_threads(1)
except Exception:
    pass


class ThaiVitsMasterEngine:
    """Master Thai VITS & KhanomTan TTS v1.1 Engine with Ultra-Lean 512MB RAM Management."""

    def __init__(self):
        self._vits_model = None
        self._vits_tokenizer = None
        self._khanomtan_v11 = None
        self._lock = threading.Lock()

    def _get_vits_community(self):
        """Lazy load facebook/mms-tts-tha (Thai VITS Model) with memory unloading."""
        if self._vits_model is None:
            with self._lock:
                if self._vits_model is None:
                    # Free KhanomTan to stay strictly below 512MB RAM on free cloud tiers
                    if self._khanomtan_v11 is not None:
                        del self._khanomtan_v11
                        self._khanomtan_v11 = None
                        gc.collect()

                    logger.info("🇹🇭 Loading VITS Thai Community (facebook/mms-tts-tha)...")
                    self._vits_model = VitsModel.from_pretrained("facebook/mms-tts-tha")
                    self._vits_tokenizer = AutoTokenizer.from_pretrained("facebook/mms-tts-tha")
                    gc.collect()
                    logger.info("✅ VITS Thai Community loaded successfully!")
        return self._vits_model, self._vits_tokenizer

    def _get_khanomtan(self):
        """Lazy load KhanomTan TTS v1.1 with memory unloading."""
        if self._khanomtan_v11 is None:
            with self._lock:
                if self._khanomtan_v11 is None:
                    # Free VITS model to stay strictly below 512MB RAM on free cloud tiers
                    if self._vits_model is not None:
                        del self._vits_model
                        del self._vits_tokenizer
                        self._vits_model = None
                        self._vits_tokenizer = None
                        gc.collect()

                    logger.info("🧁 Loading KhanomTan TTS v1.1...")
                    from pythaitts import TTS
                    self._khanomtan_v11 = TTS(pretrained="khanomtan", version="1.1")
                    gc.collect()
                    logger.info("✅ KhanomTan TTS v1.1 loaded successfully!")
        return self._khanomtan_v11

    async def synthesize(
        self,
        text: str,
        voice: str = "khanomtan-v1.1-female",
        engine: str = "khanomtan",
        style: str = "auto",
        gender: str = "female",
        rate: str = "+0%",
        pitch: str = "+0Hz",
        **kwargs,
    ) -> bytes:
        """
        Synthesize Thai speech using selected voice:
        - khanomtan-v1.1-female (Linda)
        - khanomtan-v1.1-male (Thorsten)
        - vits-thai-female (VITS Female)
        - vits-thai-male (VITS Male)
        """
        cleaned_text = clean_thai_text_for_speech(text)
        if not cleaned_text:
            return b""

        # Normalize legacy voice aliases
        if voice in ["khanomtan-v1.1", "khanomtan-v1", "khanomtan"]:
            voice = "khanomtan-v1.1-female" if gender == "female" else "khanomtan-v1.1-male"
        elif voice in ["vits-thai-community", "vits_thai"]:
            voice = "vits-thai-female" if gender == "female" else "vits-thai-male"

        loop = asyncio.get_event_loop()

        def _run_tts() -> bytes:
            # 1. KhanomTan TTS v1.1: Female (Linda)
            if voice == "khanomtan-v1.1-female":
                try:
                    model = self._get_khanomtan()
                    wav_path = model.tts(text=cleaned_text, speaker_idx="Linda", preprocess=True)
                    if wav_path and os.path.exists(wav_path):
                        with open(wav_path, "rb") as f:
                            data = f.read()
                        try:
                            os.remove(wav_path)
                        except Exception:
                            pass
                        return data
                except Exception as e:
                    logger.warning("KhanomTan v1.1 female fallback: %s", e)

            # 2. KhanomTan TTS v1.1: Male (Thorsten)
            elif voice == "khanomtan-v1.1-male":
                try:
                    model = self._get_khanomtan()
                    wav_path = model.tts(text=cleaned_text, speaker_idx="Thorsten", preprocess=True)
                    if wav_path and os.path.exists(wav_path):
                        with open(wav_path, "rb") as f:
                            data = f.read()
                        try:
                            os.remove(wav_path)
                        except Exception:
                            pass
                        return data
                except Exception as e:
                    logger.warning("KhanomTan v1.1 male fallback: %s", e)

            # 3. VITS Thai: Male
            elif voice == "vits-thai-male":
                try:
                    model, tokenizer = self._get_vits_community()
                    inputs = tokenizer(cleaned_text, return_tensors="pt")
                    with torch.no_grad():
                        output = model(**inputs).waveform
                    wav_np = output.squeeze().cpu().numpy()
                    sr = model.config.sampling_rate
                    wav_male = pitch_shift_male(wav_np, sr=sr)
                    buf = io.BytesIO()
                    sf.write(buf, wav_male, sr, format="WAV")
                    return buf.getvalue()
                except Exception as e:
                    logger.error("VITS Thai male synthesis error: %s", e)

            # 4. VITS Thai: Female (Default VITS)
            else:
                try:
                    model, tokenizer = self._get_vits_community()
                    inputs = tokenizer(cleaned_text, return_tensors="pt")
                    with torch.no_grad():
                        output = model(**inputs).waveform
                    wav_np = output.squeeze().cpu().numpy()
                    buf = io.BytesIO()
                    sf.write(buf, wav_np, model.config.sampling_rate, format="WAV")
                    return buf.getvalue()
                except Exception as e:
                    logger.error("VITS Thai female synthesis error: %s", e)

            return b""

        try:
            audio_bytes = await loop.run_in_executor(None, _run_tts)
            if audio_bytes:
                logger.info(
                    "🔊 VITS Engine (%s) synthesized %d bytes for: %s",
                    voice,
                    len(audio_bytes),
                    cleaned_text[:24],
                )
                return audio_bytes
        except Exception as e:
            logger.error("VITS TTS synthesis error (%s): %s", voice, e)

        return b""

    def list_voices(self) -> Dict[str, Dict[str, str]]:
        """List registered Thai VITS & KhanomTan voice models."""
        return VOICE_REGISTRY


# Singleton instance of Thai VITS Master Engine
tts_engine = ThaiVitsMasterEngine()
