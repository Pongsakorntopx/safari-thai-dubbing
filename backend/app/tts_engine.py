"""
Thai VITS & KhanomTan TTS Master Engine (โมเดล VITS ภาษาไทยแท้ & ขนมตาล)
Models:
  1. 🇹🇭 VITS Thai Community (facebook/mms-tts-tha) - End-to-End VITS Architecture
     Trained on massive Thai speech data (TSync2, Lotus Corpus, Thai Common Voice)
     Features: Ultra-precise 5 Thai tones (สามัญ เอก โท ตรี จัตวา) & vowel duration control.
  2. 🧁 KhanomTan TTS v1.0 (wannaphong/khanomtan-tts-v1.0) - By Wannaphong (PyThaiNLP)
  3. 🧁 KhanomTan TTS v1.1 (wannaphong/khanomtan-tts-v1.1) - Updated Open-Source VITS
"""

import asyncio
import io
import logging
import os
import re
import tempfile
import threading
from typing import Dict, Optional

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
except Exception as e:
    VitsModel = None
    AutoTokenizer = None

logger = logging.getLogger(__name__)

# Master Voice Registry for Thai VITS Models
VOICE_REGISTRY: Dict[str, Dict[str, str]] = {
    "vits-thai-community": {
        "id": "vits-thai-community",
        "name": "🇹🇭 VITS Thai Master (โมเดล VITS เสียงไทยแท้ • ชุมชน AI ไทย / PyThaiNLP)",
        "gender": "female",
        "engine": "vits_thai",
        "desc": "สถาปัตยกรรม VITS เทรนบนชุดข้อมูลเสียงไทยขนาดใหญ่ (TSync2/Lotus) แม่นยำวรรณยุกต์ 5 เสียงและสระสั้นยาว",
    },
    "khanomtan-v1": {
        "id": "khanomtan-v1",
        "name": "🧁 ขนมตาล (KhanomTan TTS v1.0 • PyThaiNLP YourTTS/VITS)",
        "gender": "female",
        "engine": "khanomtan",
        "desc": "โมเดลเสียงสังเคราะห์ภาษาไทยโอเพ่นซอร์ส KhanomTan v1.0 โดย วรรณพงษ์ ภัททิยไพบูลย์ (PyThaiNLP)",
    },
    "khanomtan-v1.1": {
        "id": "khanomtan-v1.1",
        "name": "🧁 ขนมตาล (KhanomTan TTS v1.1 • อัปเดตใหม่ Apache 2.0)",
        "gender": "female",
        "engine": "khanomtan",
        "desc": "โมเดลเสียงสังเคราะห์ภาษาไทย KhanomTan v1.1 ปรับปรุงใหม่",
    },
}


def clean_thai_text_for_speech(text: str) -> str:
    """Clean text for natural, fluent Thai speech synthesis in Thai VITS & KhanomTan."""
    if not text:
        return ""
    t = text.strip()
    t = re.sub(r"[\"\'\`\<\>\[\]\(\)\{\}\*\#\_]", "", t)

    # Expand common tech and acronyms to natural Thai phonetics
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

    t = re.sub(r"\s+", " ", t)
    return t.strip()


class ThaiVitsMasterEngine:
    """Master Thai VITS & KhanomTan TTS Engine with resilient cloud-first loader."""

    def __init__(self):
        self._vits_model = None
        self._vits_tokenizer = None
        self._khanomtan_v1 = None
        self._khanomtan_v11 = None
        self._lock = threading.Lock()

    def _get_vits_community(self):
        """Lazy load facebook/mms-tts-tha (Thai VITS Model)."""
        if self._vits_model is None:
            with self._lock:
                if self._vits_model is None:
                    logger.info("🇹🇭 Loading VITS Thai Community (facebook/mms-tts-tha)...")
                    self._vits_model = VitsModel.from_pretrained("facebook/mms-tts-tha")
                    self._vits_tokenizer = AutoTokenizer.from_pretrained("facebook/mms-tts-tha")
                    logger.info("✅ VITS Thai Community loaded successfully!")
        return self._vits_model, self._vits_tokenizer

    def _get_khanomtan(self, version: str = "1.0"):
        """Lazy load KhanomTan TTS (v1.0 or v1.1) with PyThaiTTS."""
        if version == "1.1":
            if self._khanomtan_v11 is None:
                with self._lock:
                    if self._khanomtan_v11 is None:
                        logger.info("🧁 Loading KhanomTan TTS v1.1...")
                        from pythaitts import TTS
                        self._khanomtan_v11 = TTS(pretrained="khanomtan", version="1.1")
                        logger.info("✅ KhanomTan TTS v1.1 loaded successfully!")
            return self._khanomtan_v11
        else:
            if self._khanomtan_v1 is None:
                with self._lock:
                    if self._khanomtan_v1 is None:
                        logger.info("🧁 Loading KhanomTan TTS v1.0...")
                        from pythaitts import TTS
                        self._khanomtan_v1 = TTS(pretrained="khanomtan", version="1.0")
                        logger.info("✅ KhanomTan TTS v1.0 loaded successfully!")
            return self._khanomtan_v1

    async def synthesize(
        self,
        text: str,
        voice: str = "vits-thai-community",
        engine: str = "vits_thai",
        style: str = "auto",
        gender: str = "female",
        rate: str = "+0%",
        pitch: str = "+0Hz",
        **kwargs,
    ) -> bytes:
        """
        Synthesize Thai speech using selected Thai VITS or KhanomTan Model.
        Returns WAV audio bytes.
        """
        cleaned_text = clean_thai_text_for_speech(text)
        if not cleaned_text:
            return b""

        loop = asyncio.get_event_loop()

        def _run_tts() -> bytes:
            # 1. KhanomTan TTS v1.1
            if voice == "khanomtan-v1.1":
                try:
                    model = self._get_khanomtan(version="1.1")
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
                    logger.warning("KhanomTan v1.1 fallback to MMS VITS: %s", e)

            # 2. KhanomTan TTS v1.0
            elif voice == "khanomtan-v1":
                try:
                    model = self._get_khanomtan(version="1.0")
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
                    logger.warning("KhanomTan v1.0 fallback to MMS VITS: %s", e)

            # 3. Default / Primary: VITS Thai Community (facebook/mms-tts-tha)
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
                logger.error("VITS Thai synthesis error: %s", e)

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
        """List registered Thai VITS voice models."""
        return VOICE_REGISTRY


# Singleton instance of Thai VITS Master Engine
tts_engine = ThaiVitsMasterEngine()
