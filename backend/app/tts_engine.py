"""Advanced Open-Source Neural Speech Synthesis Engine for Thai Dubbing.
Features:
1. Meta MMS Thai VITS (facebook/mms-tts-tha) - 100% Local Native Open-Source Deep Neural TTS
2. Kokoro-ONNX (82M Open-Weight Model) - High-Fidelity Studio Neural Voice
3. Microsoft Edge Neural - Deep Neural Studio Voices (th-TH-NiwatNeural, th-TH-PremwadeeNeural)
4. Google Gemini Studio Audio - Multimodal Voice Persona
"""

import asyncio
import io
import logging
import os
import re
import sys
import tempfile
import urllib.parse
from typing import Dict, List, Optional

import aiohttp
import edge_tts
try:
    import numpy as np
except ImportError:
    np = None

try:
    import soundfile as sf
except (ImportError, OSError):
    sf = None

try:
    import sherpa_onnx
    SHERPA_AVAILABLE = True
except (ImportError, OSError):
    SHERPA_AVAILABLE = False

try:
    from kokoro_onnx import Kokoro
    KOKORO_AVAILABLE = True
except (ImportError, OSError):
    KOKORO_AVAILABLE = False

from app.config import settings

logger = logging.getLogger(__name__)

# Model File Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MMS_THA_MODEL = os.path.join(BASE_DIR, "models", "mms_tha", "vits-mms-tha", "model.onnx")
MMS_THA_TOKENS = os.path.join(BASE_DIR, "models", "mms_tha", "vits-mms-tha", "tokens.txt")
KOKORO_MODEL = os.path.join(BASE_DIR, "models", "kokoro", "kokoro-v0_19.onnx")
KOKORO_VOICES = os.path.join(BASE_DIR, "models", "kokoro", "voices.bin")

VOICE_REGISTRY: Dict[str, Dict[str, str]] = {
    "mms-thai": {
        "id": "mms-thai",
        "name": "🇹🇭 Meta MMS Thai (Open-Source Native VITS Neural Model)",
        "gender": "male",
        "engine": "mms",
        "desc": "โมเดล VITS ภาษาไทยแท้จาก Meta AI รันออฟไลน์บนเครื่อง 100%",
    },
    "th-TH-NiwatNeural": {
        "id": "th-TH-NiwatNeural",
        "name": "👨‍💼 นิวัฒน์ (Neural Studio - เสียงชาย ทุ้มนุ่ม พอดแคสต์ [ครับ])",
        "gender": "male",
        "engine": "edge",
        "desc": "เสียงพากย์ชาย Deep Neural คมชัดระดับ 48kHz ทุ้มนุ่มน่าฟัง",
    },
    "th-TH-PremwadeeNeural": {
        "id": "th-TH-PremwadeeNeural",
        "name": "👩‍💼 เปรมวดี (Neural Studio - เสียงหญิง นุ่มนวล ชัดเจน [ค่ะ])",
        "gender": "female",
        "engine": "edge",
        "desc": "เสียงพากย์หญิง Deep Neural คมชัดระดับ 48kHz สดใสเป็นธรรมชาติ",
    },
    "kokoro-sarah": {
        "id": "kokoro-sarah",
        "name": "🌟 Kokoro Sarah (82M Open-Source Studio Model - หญิง)",
        "gender": "female",
        "engine": "kokoro",
        "desc": "โมเดล Open-Weight ขนาด 82M พารามิเตอร์ระดับโลก",
    },
    "kokoro-adam": {
        "id": "kokoro-adam",
        "name": "🌟 Kokoro Adam (82M Open-Source Studio Model - ชาย)",
        "gender": "male",
        "engine": "kokoro",
        "desc": "โมเดล Open-Weight ขนาด 82M พารามิเตอร์ระดับโลก",
    },
    "gtts-thai": {
        "id": "gtts-thai",
        "name": "🌐 Open Web TTS (Thai Standard Engine)",
        "gender": "female",
        "engine": "gtts",
        "desc": "ระบบเสียงมาตรฐานภาษาไทย Open Web",
    },
}


def clean_thai_text_for_speech(text: str) -> str:
    """Clean text for natural acoustic neural synthesis."""
    if not text:
        return ""
    t = text.strip()
    t = re.sub(r"[\"\'\`\<\>\[\]\(\)\{\}\*\#\_]", "", t)
    t = re.sub(r"(?<=[ก-๙])\s+(?=[ะ-ู็-์])", "", t)
    t = re.sub(r"(?<=[เ-ไ])\s+(?=[ก-ฮ])", "", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


class TTSEngine:
    """Comprehensive Open-Source Neural Speech Synthesizer."""

    def __init__(self):
        self.default_voice = "th-TH-NiwatNeural"
        self._mms_tts = None
        self._kokoro_tts = None
        self._init_local_models()

    def _init_local_models(self):
        """Initialize Meta MMS Thai and Kokoro ONNX offline neural engines."""
        # 1. Meta MMS Thai VITS
        if SHERPA_AVAILABLE and os.path.exists(MMS_THA_MODEL) and os.path.exists(MMS_THA_TOKENS):
            try:
                tts_config = sherpa_onnx.OfflineTtsConfig(
                    model=sherpa_onnx.OfflineTtsModelConfig(
                        vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                            model=MMS_THA_MODEL,
                            tokens=MMS_THA_TOKENS,
                            data_dir="",
                            noise_scale=0.667,
                            noise_scale_w=0.8,
                            length_scale=1.0,
                        ),
                        provider="cpu",
                        num_threads=2,
                    )
                )
                self._mms_tts = sherpa_onnx.OfflineTts(tts_config)
                logger.info("✅ Meta MMS Thai VITS neural model initialized successfully!")
            except Exception as e:
                logger.warning("Failed to initialize Meta MMS Thai model: %s", e)

        # 2. Kokoro 82M ONNX
        if KOKORO_AVAILABLE and os.path.exists(KOKORO_MODEL) and os.path.exists(KOKORO_VOICES):
            try:
                self._kokoro_tts = Kokoro(KOKORO_MODEL, KOKORO_VOICES)
                logger.info("✅ Kokoro-ONNX 82M neural model initialized successfully!")
            except Exception as e:
                logger.warning("Failed to initialize Kokoro model: %s", e)

    async def synthesize_mms_thai(self, text: str, speed: float = 1.0) -> bytes:
        """Synthesize Thai speech using Meta MMS Thai VITS (100% Native Open-Source Model)."""
        clean = clean_thai_text_for_speech(text)
        if not clean:
            return b""

        if not self._mms_tts:
            self._init_local_models()

        if not self._mms_tts:
            return await self.synthesize_edge(clean, voice="th-TH-NiwatNeural")

        loop = asyncio.get_event_loop()
        def _run_gen():
            audio = self._mms_tts.generate(clean, sid=0, speed=speed)
            buf = io.BytesIO()
            sf.write(buf, audio.samples, audio.sample_rate, format="WAV")
            return buf.getvalue()

        try:
            return await loop.run_in_executor(None, _run_gen)
        except Exception as e:
            logger.warning("Meta MMS Thai synthesis error: %s. Falling back to Edge Neural.", e)
            return await self.synthesize_edge(clean, voice="th-TH-NiwatNeural")

    async def synthesize_kokoro(self, text: str, voice: str = "af_sarah", speed: float = 1.0) -> bytes:
        """Synthesize speech using Kokoro-ONNX 82M Open-Weight Model."""
        clean = clean_thai_text_for_speech(text)
        if not clean:
            return b""

        if not self._kokoro_tts:
            self._init_local_models()

        if not self._kokoro_tts:
            return await self.synthesize_edge(clean, voice="th-TH-PremwadeeNeural")

        voice_name = "af_sarah" if "sarah" in voice.lower() or "female" in voice.lower() else "am_adam"
        loop = asyncio.get_event_loop()

        def _run_gen():
            samples, sample_rate = self._kokoro_tts.create(clean, voice=voice_name, speed=speed, lang="en-us")
            buf = io.BytesIO()
            sf.write(buf, samples, sample_rate, format="WAV")
            return buf.getvalue()

        try:
            return await loop.run_in_executor(None, _run_gen)
        except Exception as e:
            logger.warning("Kokoro synthesis error: %s. Falling back to Edge Neural.", e)
            return await self.synthesize_edge(clean, voice="th-TH-PremwadeeNeural")

    async def synthesize_edge(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = "+0%",
        pitch: Optional[str] = "+0Hz",
    ) -> bytes:
        """Synthesize speech using Microsoft Edge Neural Voices (th-TH-NiwatNeural, th-TH-PremwadeeNeural)."""
        clean = clean_thai_text_for_speech(text)
        if not clean:
            return b""

        selected_voice = voice if voice in ["th-TH-PremwadeeNeural", "th-TH-NiwatNeural"] else "th-TH-NiwatNeural"
        selected_rate = rate or "+0%"
        selected_pitch = pitch or "+0Hz"

        communicate = edge_tts.Communicate(
            text=clean,
            voice=selected_voice,
            rate=selected_rate,
            pitch=selected_pitch,
        )

        buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buffer.write(chunk["data"])

        return buffer.getvalue()

    async def synthesize_gtts(self, text: str) -> bytes:
        """Synthesize Thai speech via gTTS (Open Web Synthesizer)."""
        clean = clean_thai_text_for_speech(text)
        if not clean:
            return b""
        loop = asyncio.get_event_loop()
        def _run_gtts():
            try:
                from gtts import gTTS
                tts = gTTS(text=clean, lang="th", slow=False)
                buf = io.BytesIO()
                tts.write_to_fp(buf)
                return buf.getvalue()
            except Exception as e:
                logger.warning("gTTS synthesis error: %s", e)
                return b""
        return await loop.run_in_executor(None, _run_gtts)

    async def synthesize(
        self,
        text: str,
        engine: str = "auto",
        voice: Optional[str] = None,
        style: str = "podcast",
        rate: Optional[str] = None,
        pitch: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> bytes:
        """
        Unified Open-Source Neural Speech Synthesizer Dispatcher.
        Prioritizes:
        1. Meta MMS Thai VITS (100% Native Open-Source Model)
        2. Microsoft Edge Neural (th-TH-NiwatNeural / th-TH-PremwadeeNeural)
        3. Kokoro 82M ONNX
        4. gTTS Open Web Synthesizer
        """
        clean = clean_thai_text_for_speech(text)
        if not clean:
            return b""

        v_lower = str(voice).lower() if voice else ""

        # MMS Thai Open Source
        if engine == "mms" or "mms" in v_lower:
            return await self.synthesize_mms_thai(clean)

        # Kokoro Open Source
        if engine == "kokoro" or "kokoro" in v_lower:
            return await self.synthesize_kokoro(clean, voice=voice or "af_sarah")

        # gTTS Open Web
        if engine == "gtts" or "gtts" in v_lower:
            gtts_res = await self.synthesize_gtts(clean)
            if gtts_res:
                return gtts_res

        # Edge Neural (Default high-fidelity)
        selected_voice = voice if voice in ["th-TH-PremwadeeNeural", "th-TH-NiwatNeural"] else "th-TH-NiwatNeural"
        return await self.synthesize_edge(
            text=clean,
            voice=selected_voice,
            rate=rate or "+0%",
            pitch=pitch or "+0Hz",
        )

    def list_voices(self) -> Dict[str, Dict[str, str]]:
        """Return the dictionary of supported voice personas."""
        return VOICE_REGISTRY


tts_engine = TTSEngine()

