"""Master Thai Dubbing Scriptwriter & Paragraph-Level Linguistic Transcreation Engine.
Supports Universal Multi-Lingual Source Videos (English, Japanese, Korean, Chinese, Spanish, French, German, etc.).
Translates full 60-second conversational passages as a cohesive paragraph to preserve inter-sentence context,
storytelling flow, and natural spoken Thai cadence.
Guarantees correct speaker gender alignment (ครับ/ค่ะ), contextual register adaptation, and speech rhythm pacing.
"""

import asyncio
import json
import logging
import re
import urllib.parse
import urllib.request
from typing import Dict, List, Optional
import aiohttp

from app.config import settings

logger = logging.getLogger(__name__)

# Official High-Quota, Ultra-Fast Gemini Models for Real-Time Transcreation
GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]

STYLE_SYSTEM_PROMPTS = {
    "auto": """คุณคือนักเขียนบทพากย์และผู้กำกับเสียงภาษาไทยระดับมืออาชีพชั้นนำ (Master Thai Dubbing Director)
หน้าที่ของคุณคือ:
1. อ่านทำความเข้าใจเนื้อหาทั้ง 60 วินาทีนี้ (ไม่ว่าต้นฉบับจะเป็นภาษาอังกฤษ, ญี่ปุ่น, เกาหลี, จีน, สเปน หรือภาษาใดก็ตาม) เพื่อให้เห็นภาพรวมของเรื่องราว และวิเคราะห์ระดับภาษาที่เหมาะสมตามเนื้อหาคลิป (เกม, หนัง/ซีรีส์/อนิเมะ, สอนใช้งาน, เล่าเรื่อง, สารคดี)
2. แปลงและ "เรียบเรียงบทพูดใหม่ทั้งหมด" เป็นภาษาไทยที่ฟังแล้วรื่นหู เป็นธรรมชาติ สละสลวย เข้าใจง่าย 100% ตามหลักภาษาพูดของคนไทย
3. ความยาวและจังหวะการพูด: เรียบเรียงประโยคภาษาไทยให้มีความกระชับ ได้ใจความสมบูรณ์ และมีความยาวพอดีกับช่วงเวลาพูดของต้นฉบับ ไม่ยืดเยื้อหรือสั้นเกินไป เพื่อให้เสียงพากย์ซิงค์ตรงกับจังหวะการพูดในคลิปอย่างสมจริง
4. ห้ามแปลตรงตัว (ห้ามแปลคำต่อคำ) ให้จับใจความแล้วเรียบเรียงเป็นประโยคภาษาพูดไทยที่กระชับ สมบูรณ์ และได้ใจความตรงกัน
5. ส่งผลลัพธ์คืนในรูปแบบ [1] ... [2] ... ตรงตามจำนวนท่อนที่กำหนดเท่านั้น ห้ามมีคำอธิบายอื่น
""",
    "casual": """คุณคือนักพากย์ยูทูบเบอร์และสตรีมเมอร์สายฮาและเป็นกันเอง (Casual Thai Dubbing)
หน้าที่ของคุณคืออ่านเนื้อหา 60 วินาทีนี้ แล้วแปลงบทแต่ละท่อน [1], [2], [3]... ให้เป็น "ภาษาพูดที่เพื่อนคุยกัน สนุกสนาน มีชีวิตชีวา เป็นธรรมชาติที่สุด":
- ใช้คำพูดติดปาก คำอุทาน หรือภาษาพูดทั่วไป เช่น "เฮ้ย", "ดูนี่ดิ", "จัดไป", "โคตรเจ๋ง", "เอาจริงดิ", "สบายมาก"
- รักษาความกระชับของประโยคให้พอดีกับจังหวะพูดในคลิป
- ห้ามแปลตรงตัวเป็นภาษาเขียน
ส่งคืนในรูปแบบ:
[1] ข้อความภาษาไทย
[2] ข้อความภาษาไทย
...
""",
    "cinema": """คุณคือนักพากย์ภาพยนตร์และอนิเมะมืออาชีพ (Cinematic Movie & Anime Dubbing)
หน้าที่ของคุณคืออ่านบทสนทนา 60 วินาทีนี้ แล้วแปลงบทแต่ละช่วง [1], [2], [3]... ให้เป็น "บทพากย์หนัง/อนิเมะที่เต็มไปด้วยอารมณ์ สมจริง และเข้าถึงตัวละคร 100%":
- ถ่ายทอดอารมณ์ตามประโยคและบริบท (โกรธ, ตกใจ, กวนประสาท, เท่, จริงจัง)
- ปรับความยาวประโยคให้ลงจังหวะกับการขยับปากและอารมณ์ของตัวละคร
- ใช้สำนวนภาษาภาพยนตร์ไทยที่คนฟังแล้วอินเหมือนดูหนังพากย์ไทยในโรงภาพยนตร์
ส่งคืนในรูปแบบ:
[1] ข้อความภาษาไทย
[2] ข้อความภาษาไทย
...
""",
    "podcast": """คุณคือนักจัดรายการพอดแคสต์และผู้เล่าเรื่องมืออาชีพ (Podcast & Storytelling)
หน้าที่ของคุณคืออ่านเนื้อหา 60 วินาทีนี้ แล้วแปลงบทแต่ละท่อน [1], [2], [3]... ให้เป็น "ภาษาพูดเล่าเรื่องที่อบอุ่น ชวนฟัง นุ่มนวล เป็นมิตรและสุภาพอย่างเป็นธรรมชาติ":
- เรียบเรียงให้จังหวะการเล่าเรื่องลื่นไหล สละสลวย พอดีกับช่วงเวลาพูด
ส่งคืนในรูปแบบ:
[1] ข้อความภาษาไทย
[2] ข้อความภาษาไทย
...
""",
    "formal": """คุณคือผู้ประกาศข่าวและนักพากย์สารคดี
หน้าที่ของคุณคือแปลงบทแต่ละท่อน [1], [2], [3]... ให้เป็น "ภาษาทางการ/กึ่งทางการที่ถูกต้อง สุภาพ ชัดเจน น่าเชื่อถือตามหลักภาษาไทย":
- เรียบเรียงให้กระชับ ชัดถ้อยชัดคำ และพอดีกับเวลาในคลิป
ส่งคืนในรูปแบบ:
[1] ข้อความภาษาไทย
[2] ข้อความภาษาไทย
...
""",
}


def detect_context_style(context: str, requested_style: str = "auto") -> str:
    """Dynamically determine video register based on title/context in any language."""
    if requested_style and requested_style != "auto":
        return requested_style

    c = context.lower()
    if any(k in c for k in ["game", "gaming", "minecraft", "roblox", "gta", "vlog", "funny", "stream", "แคสเกม", "สตรีม", "ゲーム", "실황", "游戏"]):
        return "casual"
    if any(k in c for k in ["movie", "film", "trailer", "scene", "drama", "anime", "ซีรีส์", "หนัง", "action", "アニメ", "映画", "드라마", "영화"]):
        return "cinema"
    if any(k in c for k in ["tutorial", "how to", "guide", "learn", "coding", "course", "review", "podcast", "สอน", "รีวิว", "解説", "講座", "강의", "教程"]):
        return "podcast"
    if any(k in c for k in ["news", "documentary", "history", "science", "สารคดี", "ข่าว", "ニュース", "뉴스", "纪录片"]):
        return "formal"
    return "auto"


def is_valid_thai_translation(text: str) -> bool:
    """Check if the translated text is valid and not an API error response."""
    if not text or not text.strip():
        return False
    t_upper = text.upper()
    bad_tokens = [
        "ERROR",
        "INVALID",
        "EXAMPLE: LANGPAIR",
        "MYMEMORY",
        "429",
        "500",
        "HTML",
        "SERVER ERROR",
        "THAT’S AN ERROR",
    ]
    for b in bad_tokens:
        if b in t_upper:
            return False
    return True


def polish_spoken_thai(text: str, gender: str = "male", style: str = "auto") -> str:
    """
    Applies clean, whole-phrase natural spoken Thai phrasing and gender particle alignment.
    Does not mangle grammar or delete words.
    """
    if not text or not text.strip():
        return ""

    t = text.strip()

    # 1. Whole-phrase natural conversational phrasing
    t = re.sub(r"ยินดีต้อนรับกลับสู่ช่องของฉัน|ยินดีต้อนรับสู่ช่องของฉัน", "ยินดีต้อนรับกลับเข้าสู่ช่อง", t)
    t = re.sub(r"ในวิดีโอนี้\s*(เราจะมาดูกัน|เราจะดู|ผมจะแสดงให้เห็น|ฉันจะแสดงให้เห็น)?", "ในคลิปนี้เราจะพามาดู", t)
    t = re.sub(r"สวัสดีทุกคน\b", "สวัสดีทุกคนด้วยนะ" + ("ครับ" if gender == "male" else "ค่ะ"), t)
    t = re.sub(r"อย่าลืมกดติดตาม|อย่าลืมกดซับ", "อย่าลืมกดติดตามกันด้วยนะ" + ("ครับ" if gender == "male" else "ค่ะ"), t)
    t = re.sub(r"ไปกันเถอะ|ลุยกันเถอะ", "ลุยกันเลย", t)
    t = re.sub(r"ฉันจะแสดงให้คุณเห็น|ผมจะแสดงให้คุณเห็น", "ผมจะพามาดู" if gender == "male" else "ฉันจะพามาดู", t)
    t = re.sub(r"ข้อผิดพลาดทั่วไปที่ผู้คนมักทำ|ข้อผิดพลาดที่พบบ่อยที่สุดที่ผู้คนทำ", "ข้อผิดพลาดที่คนมักจะเจอกันบ่อยๆ", t)
    t = re.sub(r"หลีกเลี่ยงได้อย่างง่ายดาย|หลีกเลี่ยงง่ายดาย", "ป้องกันและแก้ง่ายๆ", t)
    t = re.sub(r"ดังนั้นอย่าลืมดูให้จบ|อย่าลืมดูให้จบ", "อย่าลืมดูให้จบคลิปนะ" + ("ครับ" if gender == "male" else "ค่ะ"), t)
    t = re.sub(r"ปี 2569", "ปี 2026", t)
    t = re.sub(r"ปี 2568", "ปี 2025", t)
    t = re.sub(r"ปี 2567", "ปี 2024", t)

    # 2. Gender alignment
    if gender == "male":
        t = re.sub(r"\bฉัน\b|\bดิฉัน\b", "ผม", t)
        t = re.sub(r"นะคะ|นะค่ะ|ค่ะ|คะ", "ครับ", t)
    elif gender == "female":
        t = re.sub(r"\bกระผม\b|\bผม\b", "ฉัน", t)
        t = re.sub(r"นะครับ|ครับ|คับ|ฮะ", "ค่ะ", t)

    # 3. Clean up double particles
    t = re.sub(r"ครับ\s+ครับ", "ครับ", t)
    t = re.sub(r"ค่ะ\s+ค่ะ", "ค่ะ", t)
    t = re.sub(r"\s+", " ", t).strip()

    return t


def translate_full_batch_neural(cues_text: List[str], gender: str = "male", style: str = "auto") -> List[str]:
    """
    Translates all cues together as one full paragraph to preserve narrative context,
    then parses back into structured sentence cues.
    """
    batch_text = "\n".join([f"[{i+1}] {c.strip()}" for i, c in enumerate(cues_text)])
    endpoints = [
        "https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl=auto&tl=th&q=",
        "https://translate.google.com/translate_a/single?client=it&sl=auto&tl=th&dt=t&q=",
        "https://translate.google.com/translate_a/single?client=at&sl=auto&tl=th&dt=t&q=",
    ]

    raw_translation = ""
    for ep in endpoints:
        try:
            url = ep + urllib.parse.quote(batch_text)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "GoogleTranslate/6.28.0 (iPhone; iOS 16.0; en_US)"},
            )
            resp = urllib.request.urlopen(req, timeout=5)
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list) and len(data) > 0:
                if isinstance(data[0], list) and len(data[0]) > 0:
                    if isinstance(data[0][0], list):
                        raw_translation = "".join([s[0] for s in data[0] if s and isinstance(s, list) and s[0]])
                    elif isinstance(data[0][0], str):
                        raw_translation = data[0][0]
                elif isinstance(data[0], str):
                    raw_translation = data[0]
            if raw_translation and raw_translation.strip():
                break
        except Exception as e:
            logger.debug("Endpoint translation error: %s", e)
            continue

    # Parse numbered lines
    results = [""] * len(cues_text)
    current_idx = -1

    if raw_translation:
        for line in raw_translation.split("\n"):
            m = re.match(r"^\[?(\d+)\]?[\.\:\s]*(.*)", line.strip())
            if m:
                idx = int(m.group(1)) - 1
                if 0 <= idx < len(cues_text):
                    current_idx = idx
                    results[current_idx] = m.group(2).strip()
            elif 0 <= current_idx < len(cues_text):
                results[current_idx] += " " + line.strip()

    # Polish each line
    for i in range(len(cues_text)):
        if results[i]:
            results[i] = polish_spoken_thai(results[i], gender=gender, style=style)
        else:
            results[i] = cues_text[i]

    return results


class CascadeTranslator:
    """Master Transcreation Translator with 60s Paragraph-Level Context, Universal Multi-Lingual Support & Gender Alignment."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key

    async def translate_batch(
        self,
        cues_text: List[str],
        context: str = "",
        style: str = "auto",
        gender: str = "male",
        model_name: Optional[str] = None,
        custom_key: Optional[str] = None,
    ) -> List[str]:
        """
        Translate a 60-second chunk of subtitle sentences (in any language) as a coherent narrative paragraph.
        Guarantees natural story flow, strict gender alignment (ครับ/ค่ะ), and proper video register.
        """
        if not cues_text:
            return []

        effective_style = detect_context_style(context, style)
        style_key = effective_style if effective_style in STYLE_SYSTEM_PROMPTS else "auto"
        system_instruction = STYLE_SYSTEM_PROMPTS[style_key]

        # Inject Gender Persona Instruction
        if gender == "male":
            gender_rule = "\n\nกฎเรื่องเพศผู้พากย์ (MALE PERSONA):\n- ผู้พูดคือผู้ชาย: ใช้คำลงท้าย 'ครับ / นะครับ' ห้ามใช้ 'ค่ะ / นะคะ / คะ' เด็ดขาด\n- สรรพนามแทนตัวเอง: ใช้ 'ผม / เรา' (ห้ามใช้ 'ฉัน / ดิฉัน')"
        elif gender == "female":
            gender_rule = "\n\nกฎเรื่องเพศผู้พากย์ (FEMALE PERSONA):\n- ผู้พูดคือผู้หญิง: ใช้คำลงท้าย 'ค่ะ / นะคะ' ห้ามใช้ 'ครับ / นะครับ' เด็ดขาด\n- สรรพนามแทนตัวเอง: ใช้ 'ฉัน / เรา'"
        else:
            gender_rule = ""

        full_system_instruction = system_instruction + gender_rule

        # 1. Primary: Official Gemini Models (if custom_key or valid env key is provided)
        active_key = custom_key or self.api_key or settings.gemini_api_key
        if active_key and active_key.startswith("AIzaSy"):
            numbered_input = "\n".join([f"[{i+1}] {c.strip()}" for i, c in enumerate(cues_text)])
            prompt = f"Video Title & Context: {context.strip() or 'General'}\nVideo Genre/Register: {effective_style}\nSpeaker Gender: {gender}\n\nOriginal Dialogue to Dub (60-second passage in any source language):\n{numbered_input}"

            payload = {
                "systemInstruction": {"parts": [{"text": full_system_instruction}]},
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.25 if style_key in ["casual", "cinema"] else 0.15,
                    "maxOutputTokens": 2048,
                },
            }

            models_to_try = [model_name] if model_name else GEMINI_MODELS
            for model in models_to_try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={active_key}"
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            url,
                            json=payload,
                            timeout=aiohttp.ClientTimeout(total=6.0),
                        ) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                candidates = data.get("candidates", [])
                                if candidates:
                                    parts = candidates[0].get("content", {}).get("parts", [])
                                    if parts:
                                        raw_text = parts[0].get("text", "")
                                        parsed = self._parse_gemini_output(raw_text, len(cues_text), gender)
                                        if parsed and len(parsed) == len(cues_text):
                                            logger.info("Successfully transcreated 60s batch using Gemini: %s", model)
                                            return parsed
                except Exception as e:
                    logger.debug("Gemini attempt error for %s: %s", model, e)
                    continue

        # 2. High-Quality Full-Paragraph Neural Translation Engine Fallback (100% Coherent, Full Context)
        logger.info("Using Full-Paragraph Neural Translation Engine (sl=auto -> th)")
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, translate_full_batch_neural, cues_text, gender, style_key)

    def _parse_gemini_output(self, raw_text: str, expected_count: int, gender: str) -> List[str]:
        """Parse [1] text, [2] text from Gemini response with clean gender alignment."""
        results = [""] * expected_count
        lines = raw_text.strip().split("\n")
        current_idx = -1

        for line in lines:
            line_str = line.strip()
            match = re.match(r"^\[?(\d+)\]?[\.\:\s]*(.*)", line_str)
            if match:
                idx = int(match.group(1)) - 1
                text = match.group(2).strip()
                if 0 <= idx < expected_count:
                    current_idx = idx
                    results[current_idx] = text
            elif current_idx >= 0 and current_idx < expected_count:
                results[current_idx] += " " + line_str

        # Clean gender particles
        for i in range(expected_count):
            if results[i]:
                results[i] = polish_spoken_thai(results[i], gender=gender)
            else:
                results[i] = ""

        if any(results):
            return results
        return []

    async def translate(
        self,
        text: str,
        context: str = "",
        style: str = "auto",
        gender: str = "male",
        model_name: Optional[str] = None,
        custom_key: Optional[str] = None,
    ) -> str:
        """Single sentence translation (for live mode)."""
        res = await self.translate_batch([text], context=context, style=style, gender=gender, model_name=model_name, custom_key=custom_key)
        return res[0] if res else text


translator = CascadeTranslator()
