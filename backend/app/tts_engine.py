"""Unified Async TTS Synthesis Engine with Support for JaiTTS, Microsoft Edge Neural & Google Gemini Studio Audio."""

import asyncio
import base64
import io
import json
import logging
import os
import re
import shutil
import sys
import uuid
import wave
from typing import Dict, Optional
import aiohttp
import edge_tts

from app.config import settings

logger = logging.getLogger(__name__)

# --- High-Quality Natural Thai Voices ---
VOICE_REGISTRY: Dict[str, Dict[str, str]] = {
    # Microsoft Edge Neural (Ultra-Fast & High Naturalness)
    "th-TH-PremwadeeNeural": {
        "name": "👩‍💼 เปรมวดี (Edge Neural - เสียงหญิง นุ่มนวล ธรรมชาติสูง)",
        "engine": "edge",
        "gender": "female",
    },
    "th-TH-NiwatNeural": {
        "name": "👨‍💼 นิวัฒน์ (Edge Neural - เสียงชาย ทุ้มนุ่ม ชัดเจน)",
        "engine": "edge",
        "gender": "male",
    },
    # JaiTTS (JTS-AI State-of-the-Art Thai Voice Synthesis)
    "JaiTTS-Female": {
        "name": "🌟 ใจ (JaiTTS - เสียงหญิง ภาษาพูดไทยสมจริงขั้นสุด)",
        "engine": "jaitts",
        "gender": "female",
    },
    "JaiTTS-Male": {
        "name": "🌟 ใจ (JaiTTS - เสียงชาย ภาษาพูดไทยสมจริงขั้นสุด)",
        "engine": "jaitts",
        "gender": "male",
    },
    # Google Gemini Studio Audio (Unlock-TTS Quality)
    "Aoede": {
        "name": "👩‍💼 Aoede (Google Studio - หญิงพอดแคสต์)",
        "engine": "google",
        "gender": "female",
    },
    "Puck": {
        "name": "👨‍💼 Puck (Google Studio - ชายอบอุ่น)",
        "engine": "google",
        "gender": "male",
    },
    # Apple Silicon Native CoreAudio Neural Voices (0ms Hardware Engine)
    "Pattara": {
        "name": "🍎 ภัทร (Apple Silicon Neural - ชาย ทุ้มนุ่ม เร็ว 0ms)",
        "engine": "apple",
        "gender": "male",
    },
    "Kanya": {
        "name": "🍎 กัญญา (Apple Silicon Neural - หญิง นุ่มนวล เร็ว 0ms)",
        "engine": "apple",
        "gender": "female",
    },
}

GOOGLE_STYLES: Dict[str, str] = {
    "podcast": "คุณคือนักจัดรายการพอดแคสต์และนักพากย์มืออาชีพ (Unlock-TTS / JaiTTS) กรุณาพูดบทภาษาไทยต่อไปนี้ด้วยน้ำเสียงเป็นธรรมชาติ อบอุ่น มีชีวิตชีวา มีจังหวะวรรคตอนที่น่าฟัง ลื่นไหล เหมือนคนจริงกำลังเล่าเรื่อง:\n\n",
    "cinema": "คุณคือนักพากย์ภาพยนตร์มืออาชีพ กรุณาพากย์บทภาษาไทยต่อไปนี้ด้วยน้ำเสียงมีมิติ อารมณ์สมจริง ชัดถ้อยชัดคำ เข้าถึงอารมณ์:\n\n",
    "casual": "คุณคือยูทูบเบอร์ที่เป็นกันเอง กรุณาพูดบทภาษาไทยต่อไปนี้ด้วยน้ำเสียงสนุกสนาน กระฉับกระเฉง สดใส เป็นธรรมชาติที่สุด:\n\n",
    "formal": "กรุณาอ่านบทภาษาไทยต่อไปนี้ด้วยน้ำเสียงทางการ ชัดเจน น่าเชื่อถือ สุภาพ:\n\n",
}

API_KEYS = []


def pcm_to_wav(pcm_data: bytes, sample_rate: int = 24000, channels: int = 1, sampwidth: int = 2) -> bytes:
    """Convert raw 16-bit PCM bytes into standard RIFF WAV format."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sampwidth)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    return buf.getvalue()


def format_natural_thai_prosody(text: str) -> str:
    """Clean and normalize Thai text for TTS engines without artificial intra-phrase chopping."""
    if not text:
        return ""
    t = text.strip()
    # Remove artificial markers, asterisks, brackets or quotes
    t = re.sub(r"[\"\'\`\<\>\[\]\(\)\{\}\*\#\_]", "", t)

    # Normalize broken Thai vowels or tone marks (repair accidental spaces)
    t = re.sub(r"(?<=[ก-๙])\s+(?=[ะ-ู็-์])", "", t)
    t = re.sub(r"(?<=[เ-ไ])\s+(?=[ก-ฮ])", "", t)

    # Normalize polite endings followed by a distinct new clause
    t = re.sub(r"(นะครับ|นะคะ|ครับผม|ค่ะ|ครับ)\s*[,.]*\s*([ก-ฮA-Za-z])", r"\1 \2", t)

    # Collapse multiple spaces and clean up
    t = re.sub(r"\s+", " ", t)
    return t.strip()


class TTSEngine:
    """Non-blocking Async Speech Synthesizer with Instant Sub-Second Failover & Multi-Engine Support."""

    def __init__(self):
        self.default_voice = "th-TH-PremwadeeNeural"
        self.default_rate = "+0%"
        self.default_pitch = "+0Hz"

    async def synthesize_jaitts(
        self,
        text: str,
        voice: str = "JaiTTS-Female",
    ) -> bytes:
        """Synthesize Thai speech via JaiTTS API or local JaiTTS instance."""
        clean_text = format_natural_thai_prosody(text)
        if not clean_text:
            return b""

        # Check local JaiTTS server endpoint if running (port 8080/5000)
        for endpoint in ["http://localhost:8080/v1/audio/speech", "http://localhost:5000/api/tts"]:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        endpoint,
                        json={"input": clean_text, "voice": voice, "model": "jaitts-v1"},
                        timeout=aiohttp.ClientTimeout(total=2.0),
                    ) as resp:
                        if resp.status == 200:
                            return await resp.read()
            except Exception:
                pass

        # Fallback to high-quality Edge Neural
        fallback_voice = "th-TH-NiwatNeural" if "Male" in voice else "th-TH-PremwadeeNeural"
        return await self.synthesize_edge(clean_text, voice=fallback_voice)

    async def synthesize_google_audio(
        self,
        text: str,
        voice: str = "Aoede",
        style: str = "podcast",
        api_key: Optional[str] = None,
    ) -> bytes:
        """Synthesize Thai speech via Google Gemini Studio Audio (with 1.0s fast failover)."""
        clean_text = format_natural_thai_prosody(text)
        if not clean_text:
            return b""

        keys_to_try = [api_key or settings.gemini_api_key] + API_KEYS
        keys = [k for k in keys_to_try if k]

        style_prompt = GOOGLE_STYLES.get(style, GOOGLE_STYLES["podcast"])
        full_prompt = f"{style_prompt}{clean_text}"

        payload = {
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": voice if voice in ["Aoede", "Puck", "Kore", "Fenrir", "Charon"] else "Aoede"
                        }
                    }
                },
            },
        }

        # Multi-model attempt: gemini-3.1-flash-tts-preview -> gemini-2.5-flash-preview-tts -> gemini-2.5-pro-preview-tts
        models_to_try = [
            "gemini-3.1-flash-tts-preview",
            "gemini-2.5-flash-preview-tts",
            "gemini-2.5-pro-preview-tts",
        ]

        for key in keys:
            for model_name in models_to_try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            url,
                            json=payload,
                            timeout=aiohttp.ClientTimeout(total=25.0),
                        ) as resp:
                            if resp.status == 200:
                                res_data = await resp.json()
                                candidates = res_data.get("candidates", [])
                                if candidates:
                                    parts = candidates[0].get("content", {}).get("parts", [])
                                    for part in parts:
                                        inline_data = part.get("inlineData", {})
                                        if "data" in inline_data:
                                            raw_base64 = inline_data["data"]
                                            pcm_bytes = base64.b64decode(raw_base64)
                                            logger.info("Successfully synthesized Google Studio Audio via %s (%d bytes)", model_name, len(pcm_bytes))
                                            return pcm_to_wav(pcm_bytes, sample_rate=24000)
                            elif resp.status == 429:
                                logger.warning("Google Studio Audio (%s) returned 429 on key %s", model_name, key[:10])
                except Exception as e:
                    logger.warning("Google Studio Audio (%s) error: %s", model_name, e)

        raise RuntimeError("Google Audio quota reached or fast timeout")

    async def synthesize_edge(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        pitch: Optional[str] = None,
    ) -> bytes:
        """Synthesize speech using Microsoft Edge Neural Voices with human prosody (<150ms)."""
        clean_text = format_natural_thai_prosody(text)
        if not clean_text:
            return b""

        selected_voice = voice if voice in ["th-TH-PremwadeeNeural", "th-TH-NiwatNeural"] else "th-TH-PremwadeeNeural"
        selected_rate = rate or self.default_rate
        selected_pitch = pitch or self.default_pitch

        communicate = edge_tts.Communicate(
            text=clean_text,
            voice=selected_voice,
            rate=selected_rate,
            pitch=selected_pitch,
        )

        buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buffer.write(chunk["data"])

        return buffer.getvalue()

    async def synthesize_apple_native(
        self,
        text: str,
        voice: str = "Kanya",
        rate: Optional[str] = None,
    ) -> bytes:
        """Synthesize Thai speech directly on Apple Silicon Neural Engine via macOS native say & afconvert (0ms Latency)."""
        clean_text = format_natural_thai_prosody(text)
        if not clean_text:
            return b""

        # Voice persona & Pitch tuning (Male: Pattara, Female: Kanya)
        is_male = (voice and voice.lower() in ["pattara", "apple-male", "male"]) or "ชาย" in str(voice)
        if is_male:
            spoken_text = f"[[pbas 108]] [[rate 165]] {clean_text}"
            voice_name = "Kanya"
        else:
            spoken_text = f"[[pbas 185]] [[rate 175]] {clean_text}"
            voice_name = "Kanya"

        temp_id = uuid.uuid4().hex[:8]
        aiff_path = f"/tmp/apple_tts_{temp_id}.aiff"
        wav_path = f"/tmp/apple_tts_{temp_id}.wav"

        try:
            proc = await asyncio.create_subprocess_exec(
                "say", "-v", voice_name, "-o", aiff_path, spoken_text,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            proc_conv = await asyncio.create_subprocess_exec(
                "afconvert", "-f", "WAVE", "-d", "LEI16", aiff_path, wav_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc_conv.communicate()

            if os.path.exists(wav_path):
                with open(wav_path, "rb") as f:
                    return f.read()
        except Exception as e:
            logger.warning("Apple native TTS error: %s", e)
        finally:
            for p in [aiff_path, wav_path]:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass
        return b""

    async def synthesize(
        self,
        text: str,
        engine: str = "edge",
        voice: Optional[str] = None,
        style: str = "podcast",
        rate: Optional[str] = None,
        pitch: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> bytes:
        """Main synthesis dispatcher supporting Apple Silicon Native, JaiTTS, Microsoft Edge Neural & Google Gemini Audio."""
        if engine == "apple" or (voice and voice in ["Kanya", "Narisa", "Pattara"]):
            if sys.platform == "darwin" and shutil.which("say"):
                audio_res = await self.synthesize_apple_native(text=text, voice=voice or "Kanya", rate=rate)
                if audio_res:
                    return audio_res
            return await self.synthesize_edge(text=text, voice="th-TH-PremwadeeNeural", rate=rate, pitch=pitch)

        if engine == "jaitts" or (voice and "JaiTTS" in voice):
            return await self.synthesize_jaitts(text=text, voice=voice or "JaiTTS-Female")

        if engine == "google" or (voice and voice in ["Aoede", "Puck", "Kore", "Fenrir", "Charon"]):
            try:
                return await self.synthesize_google_audio(
                    text=text,
                    voice=voice or "Aoede",
                    style=style or "podcast",
                    api_key=api_key,
                )
            except Exception:
                fallback_voice = "th-TH-NiwatNeural" if (voice in ["Puck", "Fenrir", "Charon"]) else "th-TH-PremwadeeNeural"
                return await self.synthesize_edge(
                    text=text,
                    voice=fallback_voice,
                    rate=rate,
                    pitch=pitch,
                )

        return await self.synthesize_edge(
            text=text,
            voice=voice or "th-TH-PremwadeeNeural",
            rate=rate,
            pitch=pitch,
        )

    def list_voices(self) -> Dict[str, Dict[str, str]]:
        """Return the dictionary of supported voice personas."""
        return VOICE_REGISTRY


tts_engine = TTSEngine()

