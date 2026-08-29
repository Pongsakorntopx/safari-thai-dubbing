"""
Master-Level Open-Source & Studio Neural Text-to-Speech (TTS) Engine for Thai Video Dubbing.
Completely replaces legacy synthetic engines with the highest-fidelity Thai speech models:
1. Google Native Thai Neural (gTTS) - Authentic, native Thai pronunciation & natural cadence
2. Microsoft Studio Neural HD 48kHz (Niwat & Premwadee) - Studio broadcast grade podcast & narrative
3. Thai Documentary Narrator (VIZINTZOR Male Narrator VITS) - Deep documentary narration
4. Thai Female V2 Deep Neural (VIZINTZOR Female V2 VITS) - Natural modern female voice
5. Thai Male V2 Deep Neural (VIZINTZOR Male V2 VITS) - Natural modern male voice
"""

import asyncio
import io
import logging
import os
import re
from typing import Dict, Optional

import edge_tts
import gtts
import numpy as np
import scipy.io.wavfile
import soundfile as sf
import torch

try:
    from transformers import AutoTokenizer, VitsModel
    TRANSFORMERS_AVAILABLE = True
except (ImportError, OSError):
    TRANSFORMERS_AVAILABLE = False

from app.config import settings

logger = logging.getLogger(__name__)

VOICE_REGISTRY: Dict[str, Dict[str, str]] = {
    "google-thai": {
        "id": "google-thai",
        "name": "🇹🇭 Google Native Thai (เสียงภาษาไทยแท้ มาตรฐาน Google ชัดเจนเป็นธรรมชาติ)",
        "gender": "female",
        "engine": "gtts",
        "desc": "เสียงพากย์ภาษาไทยแท้จาก Google ออกเสียงแม่นยำ ลื่นไหล ไร้สำเนียงแปลกปลอม",
    },
    "th-TH-NiwatNeural": {
        "id": "th-TH-NiwatNeural",
        "name": "🎙️ นิวัฒน์ (Studio Neural HD 48kHz - เสียงชาย ทุ้มนุ่ม พอดแคสต์ สารคดี [ครับ])",
        "gender": "male",
        "engine": "edge",
        "desc": "เสียงพากย์ชาย Deep Neural คมชัดระดับ 48kHz ทุ้มนุ่มน่าฟัง สไตล์พอดแคสต์",
    },
    "th-TH-PremwadeeNeural": {
        "id": "th-TH-PremwadeeNeural",
        "name": "🎙️ เปรมวดี (Studio Neural HD 48kHz - เสียงหญิง นุ่มนวล คมชัด สดใส [ค่ะ])",
        "gender": "female",
        "engine": "edge",
        "desc": "เสียงพากย์หญิง Deep Neural คมชัดระดับ 48kHz นุ่มนวล เป็นธรรมชาติ",
    },
    "mms-narrator": {
        "id": "mms-narrator",
        "name": "🇹🇭 ผู้บรรยายสารคดี (Documentary Narrator - VITS Neural Model ภาษาไทย)",
        "gender": "male",
        "engine": "vits",
        "model_id": "VIZINTZOR/MMS-TTS-THAI-MALE-NARRATOR",
        "desc": "โมเดลเสียงผู้บรรยายสารคดีภาษาไทย VITS Deep Neural เสียงทุ้มคมชัด",
    },
    "mms-female-v2": {
        "id": "mms-female-v2",
        "name": "🇹🇭 หญิง V2 ธรรมชาติ (Thai Female V2 - Deep Neural Model ภาษาไทยแท้)",
        "gender": "female",
        "engine": "vits",
        "model_id": "VIZINTZOR/MMS-TTS-THAI-FEMALEV2",
        "desc": "โมเดลเสียงหญิงรุ่นใหม่ V2 ภาษาไทยแท้ อารมณ์สดใส พูดเป็นธรรมชาติ",
    },
    "mms-male-v2": {
        "id": "mms-male-v2",
        "name": "🇹🇭 ชาย V2 ธรรมชาติ (Thai Male V2 - Deep Neural Model ภาษาไทยแท้)",
        "gender": "male",
        "engine": "vits",
        "model_id": "VIZINTZOR/MMS-TTS-THAI-MALEV2",
        "desc": "โมเดลเสียงชายรุ่นใหม่ V2 ภาษาไทยแท้ สไตล์สนทนา คล่องแคล่ว",
    },
}


def clean_thai_text_for_speech(text: str) -> str:
    """Clean text for natural, fluent, continuous human speech synthesis."""
    if not text:
        return ""
    t = text.strip()
    t = re.sub(r"[\"\'\`\<\>\[\]\(\)\{\}\*\#\_]", "", t)
    # Remove awkward spaces between Thai words that cause unnatural pauses
    t = re.sub(r"([ก-๙])\s+([ก-๙])", r"\1\2", t)
    t = re.sub(r"([ก-๙])\s+([ก-๙])", r"\1\2", t)  # 2nd pass for multi-word chains
    t = re.sub(r"(?<=[ก-๙])\s+(?=[ะ-ู็-์])", "", t)
    t = re.sub(r"(?<=[เ-ไ])\s+(?=[ก-ฮ])", "", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


class TTSEngine:
    """Comprehensive Open-Source & Studio Neural Speech Synthesizer."""

    def __init__(self):
        self.default_voice = "google-thai"
        self._vits_models: Dict[str, tuple] = {}
        self._lock = asyncio.Lock()

    def _get_vits_model(self, model_id: str):
        """Lazy load and cache Vits models in memory."""
        if model_id in self._vits_models:
            return self._vits_models[model_id]

        if not TRANSFORMERS_AVAILABLE:
            logger.warning("Transformers not available for VITS model: %s", model_id)
            return None, None

        try:
            logger.info("Loading VITS Neural Model: %s ...", model_id)
            tok = AutoTokenizer.from_pretrained(model_id)
            mod = VitsModel.from_pretrained(model_id)
            self._vits_models[model_id] = (tok, mod)
            logger.info("✅ VITS Neural Model [%s] loaded successfully!", model_id)
            return tok, mod
        except Exception as e:
            logger.warning("Failed to load VITS model %s: %s", model_id, e)
            return None, None

    async def synthesize_gtts(self, text: str) -> bytes:
        """Synthesize Thai speech using Google Translate Native Neural Voice with retry."""
        clean = clean_thai_text_for_speech(text)
        if not clean:
            return b""

        loop = asyncio.get_event_loop()
        def _run():
            for attempt in range(3):
                try:
                    tts = gtts.gTTS(text=clean, lang="th", slow=False)
                    buf = io.BytesIO()
                    tts.write_to_fp(buf)
                    val = buf.getvalue()
                    if val:
                        return val
                except Exception as e:
                    logger.warning("gTTS synthesis attempt %d failed: %s", attempt + 1, e)
            return b""

        return await loop.run_in_executor(None, _run)

    async def synthesize_vits(self, text: str, model_id: str) -> bytes:
        """Synthesize speech using Hugging Face VITS Neural Thai Model with MPS acceleration."""
        clean = clean_thai_text_for_speech(text)
        if not clean:
            return b""

        tok, mod = self._get_vits_model(model_id)
        if not tok or not mod:
            logger.warning("VITS model not available for %s", model_id)
            return b""

        loop = asyncio.get_event_loop()
        def _run():
            try:
                device = "mps" if torch.backends.mps.is_available() else "cpu"
                mod.to(device)
                inputs = tok(clean, return_tensors="pt").to(device)
                with torch.no_grad():
                    output = mod(**inputs).waveform.squeeze().cpu().numpy()
                buf = io.BytesIO()
                scipy.io.wavfile.write(buf, rate=mod.config.sampling_rate, data=output)
                return buf.getvalue()
            except Exception as e:
                logger.warning("VITS synthesis error for %s: %s", model_id, e)
                return b""

        return await loop.run_in_executor(None, _run)

    async def synthesize_edge(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = "+0%",
        pitch: Optional[str] = "+0Hz",
    ) -> bytes:
        """Synthesize speech using Microsoft Edge Neural Voices (48kHz HD)."""
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
        Unified Open-Source & Studio Neural Speech Synthesizer Dispatcher.
        """
        clean = clean_thai_text_for_speech(text)
        if not clean:
            return b""

        v_lower = str(voice).lower() if voice else ""

        # 1. Google Native Thai (Default Clean Human Voice)
        if engine == "gtts" or "google" in v_lower:
            return await self.synthesize_gtts(clean)

        # 2. VITS Thai Models (Documentary Narrator, Female V2, Male V2)
        if engine == "vits" or "mms" in v_lower or "narrator" in v_lower:
            if "narrator" in v_lower:
                model_id = "VIZINTZOR/MMS-TTS-THAI-MALE-NARRATOR"
            elif "female" in v_lower:
                model_id = "VIZINTZOR/MMS-TTS-THAI-FEMALEV2"
            else:
                model_id = "VIZINTZOR/MMS-TTS-THAI-MALEV2"
            return await self.synthesize_vits(clean, model_id=model_id)

        # 3. Microsoft Studio 48kHz HD Neural
        if engine == "edge" or "niwat" in v_lower or "premwadee" in v_lower:
            selected_voice = "th-TH-PremwadeeNeural" if "premwadee" in v_lower else "th-TH-NiwatNeural"
            return await self.synthesize_edge(
                text=clean,
                voice=selected_voice,
                rate=rate or "+0%",
                pitch=pitch or "+0Hz",
            )

        # Default fallback: Google Native Thai or Studio Niwat
        return await self.synthesize_gtts(clean)

    def list_voices(self) -> Dict[str, Dict[str, str]]:
        """Return the dictionary of supported voice personas."""
        return VOICE_REGISTRY


# Global singleton instance
tts_engine = TTSEngine()
