"""
KhanomTan TTS Master Engine (โมเดลเสียงขนมตาล v1.0)
Model: https://huggingface.co/wannaphong/khanomtan-tts-v1.0
Author: Wannaphong Phatthiyaphaibun (PyThaiNLP / PyThaiTTS)
Architecture: Multilingual YourTTS / VITS for natural open-source Thai Speech Synthesis.
"""

import asyncio
import io
import logging
import os
import re
import tempfile
import threading
from typing import Dict, Optional

from pythaitts import TTS

logger = logging.getLogger(__name__)

# Master Voice Registry for KhanomTan TTS v1.0
VOICE_REGISTRY: Dict[str, Dict[str, str]] = {
    "khanomtan-v1": {
        "id": "khanomtan-v1",
        "name": "🧁 ขนมตาล (KhanomTan TTS v1.0 - Open-Source Thai VITS)",
        "gender": "female",
        "engine": "khanomtan",
        "speaker_idx": "Linda",
        "language_idx": "th-th",
        "desc": "โมเดลเสียงสังเคราะห์ภาษาไทยโอเพ่นซอร์ส KhanomTan v1.0 โดย วรรณพงษ์ ภัททิยไพบูลย์ (PyThaiNLP)",
    }
}


def clean_thai_text_for_speech(text: str) -> str:
    """Clean text for natural, fluent Thai speech synthesis in KhanomTan TTS."""
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


class KhanomTanTTSEngine:
    """Master KhanomTan TTS Engine (https://huggingface.co/wannaphong/khanomtan-tts-v1.0)."""

    def __init__(self):
        self._model = None
        self._lock = threading.Lock()
        self._loop = None

    def _get_model(self):
        """Lazy thread-safe initialization of KhanomTan TTS v1.0."""
        if self._model is None:
            with self._lock:
                if self._model is None:
                    logger.info("🧁 Loading KhanomTan TTS v1.0 model from Hugging Face...")
                    self._model = TTS(pretrained="khanomtan", version="1.0")
                    logger.info("✅ KhanomTan TTS v1.0 loaded successfully!")
        return self._model

    async def synthesize(
        self,
        text: str,
        voice: str = "khanomtan-v1",
        engine: str = "khanomtan",
        style: str = "auto",
        gender: str = "female",
        rate: str = "+0%",
        pitch: str = "+0Hz",
        api_key: Optional[str] = None,
        **kwargs,
    ) -> bytes:
        """
        Synthesize Thai speech using KhanomTan TTS v1.0 (Wannaphong Phatthiyaphaibun).
        Returns WAV audio bytes.
        """
        cleaned_text = clean_thai_text_for_speech(text)
        if not cleaned_text:
            return b""

        loop = asyncio.get_event_loop()

        def _run_tts() -> bytes:
            model = self._get_model()
            wav_path = model.tts(
                text=cleaned_text,
                speaker_idx="Linda",
                preprocess=True,
            )
            if wav_path and os.path.exists(wav_path):
                with open(wav_path, "rb") as f:
                    data = f.read()
                try:
                    os.remove(wav_path)
                except Exception:
                    pass
                return data
            return b""

        try:
            audio_bytes = await loop.run_in_executor(None, _run_tts)
            if audio_bytes:
                logger.info("🧁 KhanomTan TTS v1.0 synthesized %d bytes for: %s", len(audio_bytes), cleaned_text[:24])
                return audio_bytes
        except Exception as e:
            logger.error("KhanomTan TTS synthesis error: %s", e)

        return b""

    def list_voices(self) -> Dict[str, Dict[str, str]]:
        """List registered KhanomTan voice models."""
        return VOICE_REGISTRY


# Singleton instance of KhanomTan TTS Engine
tts_engine = KhanomTanTTSEngine()
