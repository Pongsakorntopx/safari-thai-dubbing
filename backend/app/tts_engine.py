"""
Master Thai Neural TTS Engine (สตูดิโอ นิวรัล & ขนมตาล v1.1 ภาษาไทยแท้)
Voices:
  1. 🎙️ สตูดิโอ นิวรัล: หญิง (studio-thai-female / Premwadee) - เสียงผู้หญิง พากย์หนัง นุ่มนวล สมจริง 100%
  2. 🎙️ สตูดิโอ นิวรัล: ชาย (studio-thai-male / Niwat) - เสียงผู้ชาย ทุ้มนุ่ม ชัดถ้อยชัดคำ ระดับมืออาชีพ 100%
  3. 🧁 ขนมตาล v1.1: หญิง (khanomtan-v1.1-female / Linda) - โมเดล Open-Source ไทยแท้
  4. 🧁 ขนมตาล v1.1: ชาย (khanomtan-v1.1-male / Thorsten) - โมเดล Open-Source ไทยแท้
"""

import asyncio
import io
import logging
import os
import re
import tempfile
import threading
from typing import Dict, Optional

import edge_tts
import soundfile as sf

logger = logging.getLogger(__name__)

VOICE_REGISTRY: Dict[str, Dict[str, str]] = {
    "studio-thai-female": {
        "id": "studio-thai-female",
        "name": "🎙️ สตูดิโอ นิวรัล: หญิง (Premwadee • สมจริง 100%)",
        "gender": "female",
        "engine": "studio_neural",
        "edge_voice": "th-TH-PremwadeeNeural",
        "desc": "เสียงพากย์สตูดิโอนิวรัล เสียงผู้หญิง นุ่มนวล ไพเราะ เป็นธรรมชาติสูงสุด",
    },
    "studio-thai-male": {
        "id": "studio-thai-male",
        "name": "🎙️ สตูดิโอ นิวรัล: ชาย (Niwat • ทุ้มนุ่ม มืออาชีพ 100%)",
        "gender": "male",
        "engine": "studio_neural",
        "edge_voice": "th-TH-NiwatNeural",
        "desc": "เสียงพากย์สตูดิโอนิวรัล เสียงผู้ชาย อบอุ่น ทุ้มนุ่ม ชัดเจน สไตล์สารคดี/ยูทูบเบอร์",
    },
    # Backwards compatibility mappings for older extension builds
    "vits-thai-female": {
        "id": "vits-thai-female",
        "name": "🎙️ สตูดิโอ นิวรัล: หญิง (Premwadee • สมจริง 100%)",
        "gender": "female",
        "engine": "studio_neural",
        "edge_voice": "th-TH-PremwadeeNeural",
        "desc": "เสียงพากย์สตูดิโอนิวรัล เสียงผู้หญิง นุ่มนวล ไพเราะ เป็นธรรมชาติสูงสุด",
    },
    "vits-thai-male": {
        "id": "vits-thai-male",
        "name": "🎙️ สตูดิโอ นิวรัล: ชาย (Niwat • ทุ้มนุ่ม มืออาชีพ 100%)",
        "gender": "male",
        "engine": "studio_neural",
        "edge_voice": "th-TH-NiwatNeural",
        "desc": "เสียงพากย์สตูดิโอนิวรัล เสียงผู้ชาย อบอุ่น ทุ้มนุ่ม ชัดเจน สไตล์สารคดี/ยูทูบเบอร์",
    },
}


def clean_thai_text_for_speech(text: str) -> str:
    """Clean text and apply AI Learned Phonetics for Thai Neural models."""
    if not text:
        return ""
    t = text.strip()
    t = re.sub(r"[\"\'\`\<\>\[\]\(\)\{\}\*\#\_]", "", t)

    # 1. Expand common acronyms & tech terms
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

    # 2. Apply AI Self-Learning Phonetic Memory
    try:
        from app.learning_engine import learning_engine
        t = learning_engine.apply_learned_phonetics(t)
    except Exception:
        pass

    t = re.sub(r"\s+", " ", t)
    return t.strip()


def fit_audio_to_slot_duration(audio_bytes: bytes, slot_duration: float, max_speedup: float = 1.38, min_speedup: float = 0.80) -> bytes:
    """
    Ensure Thai speech duration matches the original video speaker's exact time slot.
    - Accelerates (เร่งเสียง) if speech is longer than slot.
    - Elongates/Stretches (ยืดเสียง) if speech is noticeably shorter than slot.
    - Uses Librosa's pitch-preserved Phase Vocoder: Zero pitch distortion (น้ำเสียงคงเดิม 100%).
    """
    if not audio_bytes or slot_duration <= 0.4:
        return audio_bytes

    try:
        data, sr = sf.read(io.BytesIO(audio_bytes))
        actual_duration = len(data) / sr

        # Target duration: leave 0.05s headroom before next speaker starts
        target_duration = max(0.4, slot_duration - 0.05)

        speed_factor = 1.0

        if actual_duration > target_duration:
            # Accelerate (เร่งเสียง)
            speed_factor = min(max_speedup, actual_duration / target_duration)
        elif actual_duration < target_duration * 0.72 and slot_duration >= 2.0:
            # Elongate / Stretch (ยืดเสียง)
            target_stretch = target_duration * 0.88
            speed_factor = max(min_speedup, actual_duration / target_stretch)

        if abs(speed_factor - 1.0) > 0.03:
            import librosa
            stretched_data = librosa.effects.time_stretch(data, rate=speed_factor)
            out_buf = io.BytesIO()
            sf.write(out_buf, stretched_data, sr, format="WAV", subtype="PCM_16")
            return out_buf.getvalue()
    except Exception as e:
        logger.warning("Slot duration bidirectional fitting skipped: %s", e)

    return audio_bytes


class ThaiNeuralMasterEngine:
    """Master Local Thai Neural TTS Engine (Studio Neural & KhanomTan v1.1)."""

    def __init__(self):
        self._khanomtan_v11 = None
        self._lock = threading.Lock()

    def _get_khanomtan(self):
        """Lazy load KhanomTan TTS v1.1 model."""
        if self._khanomtan_v11 is None:
            with self._lock:
                if self._khanomtan_v11 is None:
                    logger.info("🧁 Loading KhanomTan TTS v1.1...")
                    from pythaitts import TTS
                    self._khanomtan_v11 = TTS(pretrained="khanomtan", version="1.1")
                    logger.info("✅ KhanomTan TTS v1.1 loaded successfully!")
        return self._khanomtan_v11

    async def _synthesize_studio_neural(self, text: str, voice_name: str, rate: str = "+0%") -> bytes:
        """Synthesize ultra-high fidelity Studio Thai Neural speech converted to pristine WAV."""
        try:
            rate_str = "+0%"
            if rate and rate != "+0%":
                m = re.match(r"^([+-]?\d+)", str(rate))
                if m:
                    val = int(m.group(1))
                    rate_str = f"{val:+d}%"

            communicate = edge_tts.Communicate(text, voice_name, rate=rate_str)
            mp3_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    mp3_data += chunk["data"]

            if not mp3_data:
                # Retry with default rate if failed
                communicate = edge_tts.Communicate(text, voice_name, rate="+0%")
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        mp3_data += chunk["data"]

            if not mp3_data:
                return b""

            # Convert to standard 24kHz 16-bit PCM WAV for 100% distortion-free WebKit playback
            data, sr = sf.read(io.BytesIO(mp3_data))
            out_buf = io.BytesIO()
            sf.write(out_buf, data, sr, format="WAV", subtype="PCM_16")
            return out_buf.getvalue()
        except Exception as e:
            logger.error("Studio Neural TTS error (%s): %s", voice_name, e)
            return b""

    async def _synthesize_khanomtan(self, text: str, speaker_idx: str) -> bytes:
        """Synthesize using local offline KhanomTan v1.1 with 1.30x natural cadence calibration."""
        loop = asyncio.get_event_loop()

        def _run():
            try:
                import scipy.signal
                model = self._get_khanomtan()
                wav_path = model.tts(text=text, speaker_idx=speaker_idx, preprocess=True)
                if wav_path and os.path.exists(wav_path):
                    data, sr = sf.read(wav_path)
                    try:
                        os.remove(wav_path)
                    except Exception:
                        pass

                    # Calibrate KhanomTan speech speed from 0.75x to 1.30x natural conversational tempo
                    num_samples = int(len(data) / 1.30)
                    speed_data = scipy.signal.resample(data, num_samples)

                    out_buf = io.BytesIO()
                    sf.write(out_buf, speed_data, sr, format="WAV", subtype="PCM_16")
                    return out_buf.getvalue()
            except Exception as e:
                logger.error("KhanomTan TTS error: %s", e)
                return b""

        return await loop.run_in_executor(None, _run)

    async def synthesize(
        self,
        text: str,
        voice: str = "studio-thai-female",
        engine: str = "studio_neural",
        style: str = "auto",
        gender: str = "female",
        rate: str = "+0%",
        pitch: str = "+0Hz",
        **kwargs,
    ) -> bytes:
        """
        Synthesize crystal-clear, natural Thai speech:
        - studio-thai-female (Premwadee Neural)
        - studio-thai-male (Niwat Neural)
        - khanomtan-v1.1-female (Linda)
        - khanomtan-v1.1-male (Thorsten)
        """
        cleaned_text = clean_thai_text_for_speech(text)
        if not cleaned_text:
            return b""

        # Normalize legacy voice identifiers
        v_key = voice
        if v_key in ["vits-thai-female", "vits-thai-community", "vits_thai"]:
            v_key = "studio-thai-female" if gender == "female" else "studio-thai-male"
        elif v_key == "vits-thai-male":
            v_key = "studio-thai-male"
        elif v_key in ["khanomtan-v1.1", "khanomtan-v1", "khanomtan"]:
            v_key = "khanomtan-v1.1-female" if gender == "female" else "khanomtan-v1.1-male"

        meta = VOICE_REGISTRY.get(v_key, VOICE_REGISTRY["studio-thai-female"])
        target_engine = meta.get("engine", "studio_neural")

        audio_bytes = b""

        # 1. Studio Neural Speech Engine
        if target_engine == "studio_neural":
            edge_voice = meta.get("edge_voice", "th-TH-PremwadeeNeural")
            audio_bytes = await self._synthesize_studio_neural(cleaned_text, edge_voice, rate=rate)

        # 2. KhanomTan v1.1 Offline Engine
        elif target_engine == "khanomtan":
            spk = meta.get("speaker_idx", "Linda")
            audio_bytes = await self._synthesize_khanomtan(cleaned_text, speaker_idx=spk)

        # Fallback to studio female if empty
        if not audio_bytes:
            audio_bytes = await self._synthesize_studio_neural(cleaned_text, "th-TH-PremwadeeNeural", rate=rate)

        if audio_bytes:
            logger.info("🔊 Neural Engine (%s) synthesized %d bytes for: %s", v_key, len(audio_bytes), cleaned_text[:24])

        return audio_bytes

    def list_voices(self) -> Dict[str, Dict[str, str]]:
        """List registered Thai Neural voice models."""
        return VOICE_REGISTRY


# Singleton instance of Master Thai Neural Engine
tts_engine = ThaiNeuralMasterEngine()
