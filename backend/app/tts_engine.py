"""
Fish Speech Master Engine - LLM-Based Zero-Shot Neural Text-to-Speech for Thai Video Dubbing.
Architectural Highlights:
1. Pure LLM-Based Autoregressive Neural Speech Synthesis for ultra-natural Thai prosody.
2. Zero-Shot Voice Cloning (5-10 second reference audio cloning).
3. Native Fish Audio Cloud API (https://api.fish.audio/v1/tts) + Local Fish Speech Server (http://127.0.0.1:8080).
4. Studio Thai Male, Thai Female, and Custom Cloned Voice Presets.
"""

import asyncio
import base64
import io
import logging
import os
import re
from typing import Dict, Optional, List

import aiohttp
import edge_tts

from app.config import settings

logger = logging.getLogger(__name__)

# Master Fish Speech Voice Registry
VOICE_REGISTRY: Dict[str, Dict[str, str]] = {
    "fish-thai-male": {
        "id": "fish-thai-male",
        "name": "🐟 Fish Speech: ชายไทยธรรมชาติ (Thai Male Master - LLM-Based)",
        "gender": "male",
        "engine": "fish_speech",
        "reference_id": "7f92f8afb8ec43bf81429cc1c9199cb1",
        "desc": "โมเดล Fish Speech LLM เสียงผู้ชายไทย ออกเสียงเป็นธรรมชาติ ลื่นไหล ไม่แข็งกระด้าง",
    },
    "fish-thai-female": {
        "id": "fish-thai-female",
        "name": "🐟 Fish Speech: หญิงไทยธรรมชาติ (Thai Female Master - LLM-Based)",
        "gender": "female",
        "engine": "fish_speech",
        "reference_id": "54b2d56122d64f0b9f07b1d44106511a",
        "desc": "โมเดล Fish Speech LLM เสียงผู้หญิงไทย หวานใส คมชัด น้ำเสียงมีชีวิตชีวาแบบมนุษย์",
    },
    "fish-thai-narrator": {
        "id": "fish-thai-narrator",
        "name": "🐟 Fish Speech: ผู้บรรยายสารคดี (Thai Documentary Narrator)",
        "gender": "male",
        "engine": "fish_speech",
        "reference_id": "e674b27877964b4c80302b406b025406",
        "desc": "โมเดล Fish Speech สำหรับงานบรรยายสารคดี พอดแคสต์ อบอุ่น ทุ้มนุ่มน่าเชื่อถือ",
    },
    "fish-custom-clone": {
        "id": "fish-custom-clone",
        "name": "🐟 Fish Speech: โคลนเสียงตัวอย่าง 5-10 วินาที (Zero-Shot Voice Clone)",
        "gender": "auto",
        "engine": "fish_speech",
        "reference_id": "",
        "desc": "โคลนเสียงจากตัวอย่างเสียงอ้างอิง 5–10 วินาทีด้วยเทคโนโลยี Zero-shot LLM",
    },
}


def clean_thai_text_for_speech(text: str) -> str:
    """Clean text for natural, fluent, continuous human speech synthesis in Fish Speech."""
    if not text:
        return ""
    t = text.strip()
    t = re.sub(r"[\"\'\`\<\>\[\]\(\)\{\}\*\#\_]", "", t)
    # Remove awkward spaces between Thai words that cause unnatural pauses
    t = re.sub(r"([ก-๙])\s+([ก-๙])", r"\1\2", t)
    t = re.sub(r"([ก-๙])\s+([ก-๙])", r"\1\2", t)
    t = re.sub(r"(?<=[ก-๙])\s+(?=[ะ-ู็-์])", "", t)
    t = re.sub(r"(?<=[เ-ไ])\s+(?=[ก-ฮ])", "", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


class FishSpeechEngine:
    """Master Fish Speech Text-to-Speech Engine."""

    def __init__(self):
        self.api_url = "https://api.fish.audio/v1/tts"
        self.local_url = os.getenv("FISH_SPEECH_LOCAL_URL", "http://127.0.0.1:8080/v1/tts")
        self.api_key = os.getenv("FISH_AUDIO_API_KEY", "").strip()

    async def synthesize(
        self,
        text: str,
        voice: str = "fish-thai-male",
        engine: str = "fish_speech",
        style: str = "auto",
        gender: str = "auto",
        rate: str = "+0%",
        pitch: str = "+0Hz",
        api_key: Optional[str] = None,
        reference_id: Optional[str] = None,
        reference_audio_base64: Optional[str] = None,
        reference_text: Optional[str] = None,
    ) -> bytes:
        """
        Synthesize Thai speech using Fish Speech LLM Architecture.
        Supports both Cloud API and Local Fish Speech Inference.
        """
        cleaned_text = clean_thai_text_for_speech(text)
        if not cleaned_text:
            return b""

        # 1. Determine Voice Configuration & Reference ID
        effective_key = (api_key or self.api_key or os.getenv("FISH_AUDIO_API_KEY", "")).strip()
        reg_entry = VOICE_REGISTRY.get(voice, VOICE_REGISTRY["fish-thai-male"])
        target_ref_id = reference_id or reg_entry.get("reference_id", "")

        # 2. Try Local Fish Speech Server first (if running on http://127.0.0.1:8080)
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "text": cleaned_text,
                    "reference_id": target_ref_id,
                    "format": "mp3",
                }
                if reference_audio_base64:
                    payload["references"] = [{
                        "audio": reference_audio_base64,
                        "text": reference_text or ""
                    }]
                async with session.post(self.local_url, json=payload, timeout=aiohttp.ClientTimeout(total=4.0)) as resp:
                    if resp.status == 200:
                        audio_data = await resp.read()
                        if audio_data and len(audio_data) > 500:
                            logger.info("✅ Fish Speech (Local Inference) generated %d bytes", len(audio_data))
                            return audio_data
        except Exception:
            pass

        # 3. Try Fish Audio Cloud API (https://api.fish.audio/v1/tts)
        if effective_key:
            try:
                headers = {
                    "Authorization": f"Bearer {effective_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "text": cleaned_text,
                    "format": "mp3",
                    "latency": "normal",
                    "normalize": True,
                }
                if target_ref_id:
                    payload["reference_id"] = target_ref_id
                if reference_audio_base64:
                    payload["references"] = [{
                        "audio": reference_audio_base64,
                        "text": reference_text or ""
                    }]

                async with aiohttp.ClientSession() as session:
                    async with session.post(self.api_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10.0)) as resp:
                        if resp.status == 200:
                            audio_data = await resp.read()
                            if audio_data and len(audio_data) > 500:
                                logger.info("✅ Fish Speech (Cloud API) synthesized %d bytes for: %s", len(audio_data), cleaned_text[:20])
                                return audio_data
                        else:
                            err_msg = await resp.text()
                            logger.warning("Fish Audio API error %d: %s", resp.status, err_msg)
            except Exception as e:
                logger.warning("Fish Audio API request failed: %s", e)

        # 4. Built-in Studio Fallback (High-Definition Neural Fallback matching requested gender)
        try:
            target_voice = "th-TH-PremwadeeNeural" if (reg_entry.get("gender") == "female" or gender == "female") else "th-TH-NiwatNeural"
            communicate = edge_tts.Communicate(cleaned_text, voice=target_voice, rate=rate, pitch=pitch)
            audio_buffer = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.write(chunk["data"])
            audio_bytes = audio_buffer.getvalue()
            if audio_bytes:
                logger.info("Generated studio neural fallback audio (%d bytes)", len(audio_bytes))
                return audio_bytes
        except Exception as e:
            logger.error("TTS synthesis fatal error: %s", e)

        return b""

    def list_voices(self) -> Dict[str, Dict[str, str]]:
        """Return the dictionary of supported voice personas."""
        return VOICE_REGISTRY


tts_engine = FishSpeechEngine()
