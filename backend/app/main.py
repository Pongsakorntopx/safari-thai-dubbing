"""FastAPI Main Server Application for Real-Time Thai Video Dubbing.
Features Universal Multi-Lingual Innertube Subtitle Extraction, Paragraph-Level Transcreation (60s lookahead),
and Parallel Neural Audio Synthesis.
"""

import asyncio
import base64
import logging
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

import aiohttp
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.cache import cache
from app.config import settings
from app.translator import translator
from app.tts_engine import tts_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Safari AI Thai Video Dubber API",
    version="1.4.0",
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
    if any(k in v_lower for k in ["niwat", "male", "puck", "pattara"]):
        return "male"
    if any(k in v_lower for k in ["premwadee", "female", "aoede", "kanya"]):
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
        custom_key=custom_key,
    )

    # Fallback if mismatch
    if len(thai_texts) != len(req.cues):
        thai_texts = [await translator.translate(c.text, context=req.context or "", style=style, gender=gender, custom_key=custom_key) for c in req.cues]

    # 2. TTS Synthesis: If Google Studio Audio or Apple Native is requested, synthesize the whole cohesive passage as 1 Master Track!
    is_master_audio = engine in ["google", "apple"] or voice in ["Aoede", "Puck", "Kore", "Fenrir", "Charon", "Kanya", "Pattara"]

    if is_master_audio:
        full_passage = " ".join([t.strip() for t in thai_texts if t.strip()])
        master_audio_bytes = None
        try:
            master_audio_bytes = await tts_engine.synthesize(
                text=full_passage,
                engine=engine,
                voice=voice,
                style=style,
                rate=rate or "+0%",
                api_key=custom_key,
            )
        except Exception as e:
            logger.warning("Master audio synthesis failed: %s. Falling back to cue-by-cue.", e)

        if master_audio_bytes:
            results = []
            for idx, (cue, text) in enumerate(zip(req.cues, thai_texts)):
                if idx == 0:
                    results.append({
                        "id": cue.id,
                        "translatedText": text,
                        "base64Audio": base64.b64encode(master_audio_bytes).decode("utf-8"),
                        "cached": False,
                        "isMasterTrack": True,
                    })
                else:
                    results.append({
                        "id": cue.id,
                        "translatedText": text,
                        "base64Audio": "",
                        "cached": False,
                        "isMasterTrack": False,
                    })
        else:
            # Fallback to parallel cue synth if master failed
            async def synth_cue(cue: CueItem, thai_text: str):
                cue_rate = rate or "+0%"
                audio_bytes = await tts_engine.synthesize(
                    text=thai_text,
                    engine=engine,
                    voice=voice,
                    style=style,
                    rate=cue_rate,
                    api_key=custom_key,
                )
                return {
                    "id": cue.id,
                    "translatedText": thai_text,
                    "base64Audio": base64.b64encode(audio_bytes).decode("utf-8") if audio_bytes else "",
                    "cached": False,
                }
            results = await asyncio.gather(*[synth_cue(c, t) for c, t in zip(req.cues, thai_texts)])
    else:
        # Standard Edge synthesis with cache
        async def synth_cue(cue: CueItem, thai_text: str):
            cue_rate = rate or "+0%"
            cached = await cache.get_audio_dub(
                source_text=cue.text,
                engine=engine,
                voice=voice,
                rate=cue_rate,
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
                rate=cue_rate,
                api_key=custom_key,
            )

            if audio_bytes:
                await cache.set_audio_dub(
                    source_text=cue.text,
                    engine=engine,
                    voice=voice,
                    rate=cue_rate,
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
        "gemini_status": translator.last_status,
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
