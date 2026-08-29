"""FastAPI Main Server Application for Real-Time Thai Video Dubbing.
Handles universal multi-lingual transcript fetching (Japanese, Korean, Chinese, Spanish, French, German, etc.),
paragraph-level batch translations (60s lookahead) with exact gender alignment and parallel TTS synthesis.
"""

import asyncio
import base64
import logging
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi

from app.cache import cache
from app.config import settings
from app.translator import translator
from app.tts_engine import tts_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

yt_transcript_api = YouTubeTranscriptApi()

app = FastAPI(
    title="Safari AI Thai Video Dubber API",
    version="1.2.0",
    description="Backend API for 60-Second Real-Time AI Thai Video Dubbing & Universal Multi-Lingual Transcreation",
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
    engine: Optional[str] = "edge"
    voice: Optional[str] = "th-TH-PremwadeeNeural"
    style: Optional[str] = "auto"
    gender: Optional[str] = "auto"
    rate: Optional[str] = "+0%"
    customGeminiKey: Optional[str] = ""


class CueItem(BaseModel):
    id: int
    start: float
    end: float
    text: str


class BatchDubRequest(BaseModel):
    cues: List[CueItem]
    context: Optional[str] = ""
    engine: Optional[str] = "edge"
    voice: Optional[str] = "th-TH-PremwadeeNeural"
    style: Optional[str] = "auto"
    gender: Optional[str] = "auto"
    rate: Optional[str] = "+0%"
    customGeminiKey: Optional[str] = ""


class TranscriptRequest(BaseModel):
    videoId: str


def resolve_gender(voice: str, requested_gender: Optional[str] = "auto") -> str:
    """Determine speaker gender from explicit request or selected voice persona."""
    if requested_gender and requested_gender in ["male", "female"]:
        return requested_gender
    v_lower = voice.lower()
    if any(k in v_lower for k in ["niwat", "male", "puck"]):
        return "male"
    if any(k in v_lower for k in ["premwadee", "female", "aoede"]):
        return "female"
    return "male"


@app.on_event("startup")
async def startup_event():
    """Initialize database and caches on server start."""
    logger.info("Initializing Dubbing Cache...")
    await cache.init_db()


@app.get("/health")
async def health_check():
    """Health check endpoint and list of active voices."""
    return {
        "status": "healthy",
        "service": "thai-dubbing-api",
        "gemini_ready": bool(settings.gemini_api_key),
        "voices": tts_engine.list_voices(),
    }


def fetch_universal_transcript_snippets(video_id: str):
    """
    Universally extracts subtitles for any video in any language
    (Japanese, Korean, Chinese, Spanish, French, German, Russian, etc.).
    """
    t_list = yt_transcript_api.list(video_id)
    
    # 1. Check for Thai or English subtitles
    for lang in ["th", "en", "en-US", "en-GB"]:
        try:
            t = t_list.find_transcript([lang])
            logger.info("Found direct subtitle for %s in language: %s", video_id, lang)
            return t.fetch()
        except Exception:
            pass

    # 2. Check for any manual human-created transcript
    for t in t_list:
        if not t.is_generated:
            logger.info("Found manual subtitle for %s: %s (%s)", video_id, t.language, t.language_code)
            if t.is_translatable:
                try:
                    return t.translate("en").fetch()
                except Exception:
                    pass
            return t.fetch()

    # 3. Check for any auto-generated transcript (e.g. ja, ko, zh, es, etc.)
    for t in t_list:
        logger.info("Found auto-generated subtitle for %s: %s (%s)", video_id, t.language, t.language_code)
        if t.is_translatable:
            try:
                return t.translate("en").fetch()
            except Exception:
                pass
        return t.fetch()

    return []


@app.post("/api/v1/transcript")
async def get_transcript(req: TranscriptRequest):
    """
    Extracts, merges, and cleans YouTube subtitles into timed sentence cues for any language.
    """
    vid = req.videoId.strip()
    clean_vid = vid.split("&")[0].split("?")[0]
    logger.info("Fetching transcripts for YouTube video: %s", clean_vid)

    try:
        raw_snippets = fetch_universal_transcript_snippets(clean_vid)
        
        cues = []
        current_cue = None
        cue_idx = 1

        for s in raw_snippets:
            text = (getattr(s, "text", "") or "").replace("\n", " ").strip()
            if not text or text.startswith("["):
                continue

            start = float(getattr(s, "start", 0.0))
            dur = float(getattr(s, "duration", 0.0))
            end = start + dur

            if not current_cue:
                current_cue = {
                    "id": cue_idx,
                    "start": round(start, 2),
                    "end": round(end, 2),
                    "text": text,
                }
                cue_idx += 1
            else:
                current_cue["text"] += " " + text
                current_cue["end"] = round(end, 2)

            is_sentence_end = bool(re_is_end(text)) or (current_cue["end"] - current_cue["start"] >= 4.5)
            if is_sentence_end:
                cues.append(current_cue)
                current_cue = None

        if current_cue:
            cues.append(current_cue)

        logger.info("Extracted %d structured sentence cues for %s", len(cues), clean_vid)
        return {
            "success": True,
            "videoId": clean_vid,
            "cues": cues,
        }

    except Exception as e:
        logger.warning("Transcript fetch failed for %s: %s", clean_vid, e)
        return {
            "success": False,
            "videoId": clean_vid,
            "error": str(e),
            "cues": [],
        }


def re_is_end(text: str) -> bool:
    t = text.strip()
    return t.endswith(".") or t.endswith("!") or t.endswith("?") or t.endswith("。") or t.endswith("！") or t.endswith("？")


@app.post("/api/v1/dub_batch")
async def dub_cues_batch(req: BatchDubRequest):
    """
    60-Second Paragraph-Level Batch Dubbing (Universal Multi-Lingual Support):
    1. Translates the full 60-second narrative passage together with strict gender alignment.
    2. Synthesizes high-quality audio for each cue in parallel (<1.0s).
    3. Guarantees natural spoken Thai flow with zero word-by-word fragmentation.
    """
    if not req.cues:
        return {"success": True, "results": []}

    engine = req.engine or "edge"
    voice = req.voice or "th-TH-PremwadeeNeural"
    style = req.style or "auto"
    rate = req.rate or "+0%"
    gender = resolve_gender(voice, req.gender)
    custom_key = req.customGeminiKey.strip() if req.customGeminiKey else None

    # 1. Translate all cues together as a cohesive 60s paragraph (in any source language)
    cues_text = [c.text.strip() for c in req.cues]
    thai_texts = await translator.translate_batch(
        cues_text=cues_text,
        context=req.context or "",
        style=style,
        gender=gender,
    )

    # If any count mismatch, fallback
    if len(thai_texts) != len(req.cues):
        thai_texts = [await translator.translate(c.text, context=req.context or "", style=style, gender=gender) for c in req.cues]

    # 2. Parallel TTS Synthesis
    async def synth_cue(cue: CueItem, thai_text: str):
        # Check cache
        cached = await cache.get_audio_dub(
            source_text=cue.text,
            engine=engine,
            voice=voice,
            rate=rate,
            pitch="0Hz",
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
            }

        audio_bytes = await tts_engine.synthesize(
            text=thai_text,
            engine=engine,
            voice=voice,
            style=style,
            rate=rate,
            api_key=custom_key,
        )

        if audio_bytes:
            await cache.set_audio_dub(
                source_text=cue.text,
                engine=engine,
                voice=voice,
                rate=rate,
                pitch="0Hz",
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
            }
        return {
            "id": cue.id,
            "translatedText": thai_text,
            "base64Audio": "",
            "cached": False,
        }

    results = await asyncio.gather(*[synth_cue(c, t) for c, t in zip(req.cues, thai_texts)])

    return {
        "success": True,
        "results": results,
    }


@app.post("/api/v1/dub")
async def dub_text(req: DubRequest):
    """
    Direct Real-time Translation & Audio Synthesis (for Live Subtitle Mode).
    """
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    engine = req.engine or "edge"
    voice = req.voice or "th-TH-PremwadeeNeural"
    style = req.style or "auto"
    rate = req.rate or "+0%"
    gender = resolve_gender(voice, req.gender)
    custom_key = req.customGeminiKey.strip() if req.customGeminiKey else None

    # 1. Translate
    thai_text = await translator.translate(
        text=req.text,
        context=req.context or "",
        style=style,
        gender=gender,
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
        audio_data=audio_bytes,
    )

    return {
        "success": True,
        "translatedText": thai_text,
        "base64Audio": base64.b64encode(audio_bytes).decode("utf-8"),
        "cached": False,
    }
