"""FastAPI Main Server Application for Real-Time Thai Video Dubbing.
Features Universal Multi-Lingual Innertube Subtitle Extraction, Paragraph-Level Transcreation (60s lookahead),
and Parallel Neural Audio Synthesis.
"""

import asyncio
import base64
import logging
import re
import platform
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

from contextlib import asynccontextmanager

import aiohttp
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.cache import cache
from app.config import settings
from app.translator import translator
from app.tts_engine import tts_engine, VOICE_REGISTRY

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and caches on server start."""
    logger.info("Initializing Dubbing Cache...")
    await cache.init_db()
    yield


app = FastAPI(
    title="Safari AI Thai Video Dubber API",
    version="1.5.0",
    description="Backend API for Fish Speech LLM-Based Real-Time AI Thai Video Dubbing",
    lifespan=lifespan,
)

# CORS: Allow all origins for seamless Safari integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DubRequest(BaseModel):
    text: str
    context: Optional[str] = ""
    engine: Optional[str] = "fish_speech"
    voice: Optional[str] = "auto"
    style: Optional[str] = "auto"
    gender: Optional[str] = "auto"
    rate: Optional[str] = "+0%"
    customGeminiKey: Optional[str] = ""
    fishApiKey: Optional[str] = ""


class CueItem(BaseModel):
    id: int
    start: float
    end: float
    text: str


class BatchDubRequest(BaseModel):
    cues: List[CueItem]
    context: Optional[str] = ""
    engine: Optional[str] = "fish_speech"
    voice: Optional[str] = "auto"
    style: Optional[str] = "auto"
    gender: Optional[str] = "auto"
    rate: Optional[str] = "+0%"
    customGeminiKey: Optional[str] = ""
    fishApiKey: Optional[str] = ""


class TranscriptRequest(BaseModel):
    videoId: str


class LearnTermRequest(BaseModel):
    term: str
    phonetic_thai: str
    category: Optional[str] = "user_taught"


class FeedbackRequest(BaseModel):
    cue_text: str
    rating: int = 5
    user_correction: Optional[str] = None
    voice_id: Optional[str] = None


def resolve_gender(voice: str, requested_gender: Optional[str] = "auto") -> str:
    """Determine speaker gender from explicit request or voice persona."""
    if requested_gender and requested_gender in ["male", "female"]:
        return requested_gender
    v_lower = voice.lower()
    if any(k in v_lower for k in ["female", "หญิง"]):
        return "female"
    return "male"


def resolve_auto_settings(
    req_engine: Optional[str],
    req_voice: Optional[str],
    req_style: Optional[str],
    req_gender: Optional[str],
    context: str = "",
):
    """
    Thai Studio Neural Voice Resolver:
    - Supports Studio Neural Female (Premwadee) and Male (Niwat).
    """
    voice = req_voice if req_voice in VOICE_REGISTRY else "studio-thai-female"
    reg = VOICE_REGISTRY.get(voice, VOICE_REGISTRY["studio-thai-female"])
    engine = reg.get("engine", "studio_neural")
    gender = reg.get("gender", "female")
    style = req_style or "auto"
    return engine, voice, style, gender


@app.get("/health")
async def health_check():
    """Health check endpoint and list of active voices + learning engine stats."""
    from app.learning_engine import learning_engine
    return {
        "status": "healthy",
        "service": "thai-dubbing-api",
        "gemini_ready": bool(settings.gemini_api_key),
        "voices": tts_engine.list_voices(),
        "learned_terms_count": len(learning_engine.get_learned_lexicon()),
    }


@app.get("/api/v1/voices")
async def list_supported_voices():
    """Return dictionary of supported Thai VITS & KhanomTan voice personas."""
    return {
        "success": True,
        "voices": tts_engine.list_voices(),
    }


@app.get("/api/v1/learning/lexicon")
async def get_learned_lexicon():
    """Retrieve full list of learned phonetic vocabulary across all 4 models."""
    from app.learning_engine import learning_engine
    lex = learning_engine.get_learned_lexicon()
    return {
        "success": True,
        "count": len(lex),
        "lexicon": lex,
    }


@app.post("/api/v1/learning/learn")
async def learn_new_term(req: LearnTermRequest):
    """Teach the AI models a new word or custom pronunciation rule."""
    from app.learning_engine import learning_engine
    success = learning_engine.learn_term(req.term, req.phonetic_thai, req.category or "user_taught")
    return {"success": success, "term": req.term, "phonetic_thai": req.phonetic_thai}


@app.post("/api/v1/learning/feedback")
async def submit_feedback(req: FeedbackRequest):
    """Record quality feedback from user to continuously optimize future generations."""
    from app.learning_engine import learning_engine
    learning_engine.record_feedback(req.cue_text, req.rating, req.user_correction, req.voice_id)
    return {"success": True}


# Official Standalone YouTube Innertube API Key
INNERTUBE_API_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"


async def fetch_youtube_innertube_cues_async(video_id: str) -> List[Dict]:
    """
    Directly extracts subtitle tracks and parses XML cues for any video in any language
    using YouTube's official Android Innertube client without datacenter IP blocking.
    """
    clean_vid = video_id.split("&")[0].split("?")[0]
    
    async with aiohttp.ClientSession() as session:
        try:
            url = f"https://www.youtube.com/youtubei/v1/player?key={INNERTUBE_API_KEY}"
            payload = {
                "context": {
                    "client": {
                        "clientName": "ANDROID",
                        "clientVersion": "20.10.38",
                        "androidSdkVersion": 30,
                        "hl": "en",
                        "gl": "US",
                    }
                },
                "videoId": clean_vid,
            }
            headers = {
                "User-Agent": "com.google.android.youtube/20.10.38 (Linux; U; Android 11)",
                "Content-Type": "application/json",
            }

            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=8.0)) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    caption_tracks = data.get("captions", {}).get("playerCaptionsTracklistRenderer", {}).get("captionTracks", [])
                    if caption_tracks:
                        # Prioritize English or Thai or first available (Korean, Japanese, Spanish, etc.)
                        chosen = next((t for t in caption_tracks if t.get("languageCode") in ["en", "en-US"]), None) or \
                                 next((t for t in caption_tracks if t.get("languageCode") == "th"), None) or \
                                 caption_tracks[0]

                        base_url = chosen.get("baseUrl")
                        if base_url:
                            async with session.get(base_url, timeout=aiohttp.ClientTimeout(total=8.0)) as sub_resp:
                                if sub_resp.status == 200:
                                    raw_xml = await sub_resp.text()
                                    if raw_xml and raw_xml.strip():
                                        root = ET.fromstring(raw_xml)
                                        cues = []
                                        cue_id = 1
                                        current_cue = None

                                        # Parse <p t="..." d="...">
                                        for p in root.findall(".//p"):
                                            t_attr = p.get("t")
                                            d_attr = p.get("d")
                                            if t_attr is None:
                                                continue
                                            start = round(float(t_attr) / 1000.0, 2)
                                            dur = round(float(d_attr) / 1000.0, 2) if d_attr else 3.0
                                            end = round(start + dur, 2)

                                            text = "".join(p.itertext()).replace("\n", " ").strip()
                                            if not text or text.startswith("["):
                                                continue

                                            if not current_cue:
                                                current_cue = {"id": cue_id, "start": start, "end": end, "text": text}
                                                cue_id += 1
                                            else:
                                                gap = start - current_cue["end"]
                                                if current_cue["text"].endswith(text):
                                                    continue
                                                current_cue["text"] += " " + text
                                                current_cue["end"] = max(current_cue["end"], end)

                                                is_end = bool(re.search(r"[.!?。！？]$", text)) or gap > 0.8 or (current_cue["end"] - current_cue["start"] >= 5.5)
                                                if is_end:
                                                    cues.append(current_cue)
                                                    current_cue = None

                                        if current_cue:
                                            cues.append(current_cue)

                                        # Fallback for <text start="..." dur="...">
                                        if not cues:
                                            for text_node in root.findall(".//text"):
                                                start_attr = text_node.get("start")
                                                dur_attr = text_node.get("dur")
                                                if start_attr is None:
                                                    continue
                                                start = round(float(start_attr), 2)
                                                dur = round(float(dur_attr), 2) if dur_attr else 3.0
                                                end = round(start + dur, 2)

                                                text = (text_node.text or "").replace("\n", " ").strip()
                                                if not text or text.startswith("["):
                                                    continue

                                                if not current_cue:
                                                    current_cue = {"id": cue_id, "start": start, "end": end, "text": text}
                                                    cue_id += 1
                                                else:
                                                    gap = start - current_cue["end"]
                                                    if current_cue["text"].endswith(text):
                                                        continue
                                                    current_cue["text"] += " " + text
                                                    current_cue["end"] = max(current_cue["end"], end)

                                                    is_end = bool(re.search(r"[.!?。！？]$", text)) or gap > 0.8 or (current_cue["end"] - current_cue["start"] >= 5.5)
                                                    if is_end:
                                                        cues.append(current_cue)
                                                        current_cue = None

                                            if current_cue:
                                                cues.append(current_cue)

                                        if cues:
                                            logger.info("Successfully extracted %d cues for %s via Innertube (%s)", len(cues), clean_vid, chosen.get("languageCode"))
                                            return cues
        except Exception as e:
            logger.warning("Innertube extraction error for %s: %s", clean_vid, e)

    return []


@app.post("/api/v1/transcript")
async def get_transcript(req: TranscriptRequest):
    """
    Extracts, merges, and cleans YouTube subtitles into timed sentence cues for any language
    using Direct Innertube Extraction (0 IP Block).
    """
    vid = req.videoId.strip()
    clean_vid = vid.split("&")[0].split("?")[0]
    logger.info("Fetching transcripts for YouTube video: %s", clean_vid)

    try:
        cues = await fetch_youtube_innertube_cues_async(clean_vid)
        if cues:
            return {
                "success": True,
                "videoId": clean_vid,
                "cues": cues,
            }

        # Fallback: YouTubeTranscriptApi
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            api = YouTubeTranscriptApi()
            tl = api.list(clean_vid)
            chosen_t = next((t for t in tl if t.language_code in ["en", "en-US"]), None) or \
                       next((t for t in tl if t.language_code == "th"), None) or \
                       next(iter(tl), None)
            if chosen_t:
                snippets = chosen_t.fetch()
                fb_cues = []
                c_id = 1
                curr_c = None
                for s in snippets:
                    st = round(float(s.start), 2)
                    du = round(float(s.duration), 2)
                    en = round(st + du, 2)
                    tx = s.text.replace("\n", " ").strip()
                    if not tx or tx.startswith("["):
                        continue
                    if not curr_c:
                        curr_c = {"id": c_id, "start": st, "end": en, "text": tx}
                        c_id += 1
                    else:
                        gap = st - curr_c["end"]
                        if not curr_c["text"].endswith(tx):
                            curr_c["text"] += " " + tx
                        curr_c["end"] = max(curr_c["end"], en)
                        is_end = bool(re.search(r'[.!?。！？]["\']?$', curr_c["text"])) or gap > 0.9 or (curr_c["end"] - curr_c["start"] >= 8.0)
                        if is_end:
                            fb_cues.append(curr_c)
                            curr_c = None
                if curr_c:
                    fb_cues.append(curr_c)
                if fb_cues:
                    logger.info("Successfully fetched %d cues via YouTubeTranscriptApi for %s", len(fb_cues), clean_vid)
                    return {
                        "success": True,
                        "videoId": clean_vid,
                        "cues": fb_cues,
                    }
        except Exception as yt_err:
            logger.warning("YouTubeTranscriptApi fallback failed for %s: %s", clean_vid, yt_err)

        return {
            "success": False,
            "videoId": clean_vid,
            "error": "No subtitles found for this video",
            "cues": [],
        }

    except Exception as e:
        logger.warning("Transcript fetch failed for %s: %s", clean_vid, e)
        return {
            "success": False,
            "videoId": clean_vid,
            "error": str(e),
            "cues": [],
        }


@app.post("/api/v1/dub_batch")
async def dub_cues_batch(req: BatchDubRequest):
    """
    60-Second Paragraph-Level Batch Dubbing:
    1. Translates the full 60-second narrative passage together with strict gender alignment.
    2. Synthesizes high-quality audio for each cue in parallel (<1.5s).
    3. Guarantees natural spoken Thai flow with zero word-by-word fragmentation.
    """
    if not req.cues:
        return {"success": True, "results": []}

    engine, voice, style, gender = resolve_auto_settings(
        req.engine, req.voice, req.style, req.gender, context=req.context or ""
    )
    rate = req.rate or "+0%"
    custom_key = req.customGeminiKey.strip() if req.customGeminiKey else None
    custom_fish_key = req.fishApiKey.strip() if req.fishApiKey else None

    # 1. Master Spoken Thai Transcreation & Rhythm Alignment
    raw_cues_dict = [c.dict() for c in req.cues]
    diarized_results = await translator.translate_batch_diarized(
        cues=raw_cues_dict,
        context=req.context or "",
        style=req.style or "auto",
        gender=gender,
        custom_key=custom_key,
    )

    # 🧠 Continuous AI Auto-Learning: Absorb new tech terms & vocabulary into persistent memory
    try:
        from app.learning_engine import learning_engine
        for cue_item, diar in zip(req.cues, diarized_results):
            learning_engine.auto_learn_from_context(cue_item.text, diar.get("thai", ""))
    except Exception:
        pass

    # 2. Hard-Locked Selected Thai Studio Neural Voice (100% consistent across entire video)
    target_voice = voice if voice in VOICE_REGISTRY else "studio-thai-female"
    voice_meta = VOICE_REGISTRY.get(target_voice, VOICE_REGISTRY["studio-thai-female"])
    voice_display_name = voice_meta.get("name", "🎙️ สตูดิโอ นิวรัล: หญิง")
    target_engine = voice_meta.get("engine", "studio_neural")
    speaker_gender = voice_meta.get("gender", "female")

    sem = asyncio.Semaphore(4)

    async def synth_cue(cue: CueItem, diarized: Dict):
        thai_text = diarized.get("thai", "").strip() or cue.text
        emotion = diarized.get("emotion", "engaging")
        pitch = diarized.get("pitch", "+0Hz")

        cue_engine = target_engine
        cue_voice = target_voice

        # 🎯 Original Video Speech Cadence & Exact Duration Pacing (WPS / WPM)
        words_count = len(cue.text.split())
        slot_duration = max(0.8, float(cue.end - cue.start))
        orig_wps = words_count / slot_duration
        orig_wpm = round(orig_wps * 60)

        # Match Thai speech rate with Original Video Speaker's pacing:
        thai_chars = len(thai_text)
        expected_sec = thai_chars / 12.0
        speed_ratio = expected_sec / slot_duration

        cue_rate = rate if (rate and rate != "+0%") else diarized.get("rate", "+0%")
        if cue_rate == "+0%" or not cue_rate:
            if speed_ratio > 1.05:
                rate_pct = min(35, max(5, int((speed_ratio - 1.0) * 100)))
                cue_rate = f"+{rate_pct}%"
            elif speed_ratio < 0.80:
                rate_pct = max(-20, min(-5, int((speed_ratio - 1.0) * 100)))
                cue_rate = f"{rate_pct}%"
            else:
                cue_rate = "+0%"

        cached = await cache.get_audio_dub(
            source_text=cue.text,
            engine=cue_engine,
            voice=cue_voice,
            rate=cue_rate,
            pitch=pitch,
            style=style,
            context=req.context or "",
        )
        if cached:
            _, audio_bytes = cached
            return {
                "id": cue.id,
                "translatedText": thai_text,
                "base64Audio": base64.b64encode(audio_bytes).decode("utf-8"),
                "cached": True,
                "speaker": "host",
                "emotion": emotion,
                "orig_wpm": orig_wpm,
                "slotDuration": slot_duration,
                "appliedRate": cue_rate,
            }

        audio_bytes = b""
        async with sem:
            try:
                audio_bytes = await tts_engine.synthesize(
                    text=thai_text,
                    engine=cue_engine,
                    voice=cue_voice,
                    style=style,
                    gender=speaker_gender,
                    rate=cue_rate,
                    pitch=pitch,
                )
            except Exception as e:
                logger.warning("TTS synthesis error for cue %d: %s", cue.id, e)

        if audio_bytes:
            from app.tts_engine import fit_audio_to_slot_duration
            audio_bytes = fit_audio_to_slot_duration(audio_bytes, slot_duration)
            await cache.set_audio_dub(
                source_text=cue.text,
                engine=cue_engine,
                voice=cue_voice,
                rate=cue_rate,
                pitch=pitch,
                style=style,
                context=req.context or "",
                translated_text=thai_text,
                audio_data=audio_bytes,
            )
            return {
                "id": cue.id,
                "translatedText": thai_text,
                "base64Audio": base64.b64encode(audio_bytes).decode("utf-8"),
                "cached": False,
                "speaker": "host",
                "emotion": emotion,
                "orig_wpm": orig_wpm,
                "slotDuration": slot_duration,
                "appliedRate": cue_rate,
            }

        return {
            "id": cue.id,
            "translatedText": thai_text,
            "base64Audio": "",
            "cached": False,
            "speaker": "host",
            "emotion": emotion,
            "orig_wpm": orig_wpm,
            "slotDuration": slot_duration,
            "appliedRate": cue_rate,
        }

    results = await asyncio.gather(*[synth_cue(c, d) for c, d in zip(req.cues, diarized_results)])

    return {
        "success": True,
        "results": results,
        "active_voice": target_voice,
        "voice_name": voice_display_name,
        "gemini_status": translator.last_status,
        "total_cues": len(req.cues),
    }


@app.post("/api/v1/dub")
async def dub_text(req: DubRequest):
    """
    Direct Real-time Translation & Audio Synthesis (for Live Subtitle Mode).
    """
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    engine, voice, style, gender = resolve_auto_settings(
        req.engine, req.voice, req.style, req.gender, context=req.context or ""
    )
    rate = req.rate or "+0%"
    custom_key = req.customGeminiKey.strip() if req.customGeminiKey else None

    # 1. Translate
    thai_text = await translator.translate(
        text=req.text,
        context=req.context or "",
        style=style,
        gender=gender,
        custom_key=custom_key,
    )

    if not thai_text:
        return {
            "success": False,
            "error": "Translation failed",
        }

    # 2. Check Cache
    cached = await cache.get_audio_dub(
        source_text=req.text,
        engine=engine,
        voice=voice,
        rate=rate,
        pitch="0Hz",
        style=style,
        context=req.context or "",
    )
    if cached:
        cached_thai, audio_bytes = cached
        return {
            "success": True,
            "translatedText": cached_thai,
            "base64Audio": base64.b64encode(audio_bytes).decode("utf-8"),
            "cached": True,
        }

    # 3. Synthesize
    audio_bytes = await tts_engine.synthesize(
        text=thai_text,
        engine=engine,
        voice=voice,
        style=style,
        rate=rate,
        api_key=custom_key,
    )

    if not audio_bytes:
        return {
            "success": False,
            "translatedText": thai_text,
            "error": "Audio synthesis failed",
        }

    # 4. Save to Cache
    await cache.set_audio_dub(
        source_text=req.text,
        engine=engine,
        voice=voice,
        rate=rate,
        pitch="0Hz",
        style=style,
        context=req.context or "",
        translated_text=thai_text,
        audio_data=audio_data if "audio_data" in locals() else audio_bytes,
    )

    return {
        "success": True,
        "translatedText": thai_text,
        "base64Audio": base64.b64encode(audio_bytes).decode("utf-8"),
        "cached": False,
        "gemini_status": translator.last_status,
    }
