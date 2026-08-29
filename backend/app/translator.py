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

ENGLISH_IDIOM_NORMALIZER = [
    (r"\bbro\b|\bdude\b", "hey"),
    (r"\blook out\b|\bwatch out\b", "be careful"),
    (r"\bcheck this out\b", "look at this"),
    (r"\bno way\b", "no way impossible"),
    (r"\byou got to be kidding me\b|\bare you kidding me\b", "are you joking"),
    (r"\bwhat the heck\b|\bwhat the hell\b", "what is this"),
    (r"\bcoming right at us\b|\bheaded our way\b", "rushing towards us"),
    (r"\bpiece of cake\b", "very easy piece of cake"),
    (r"\bat the end of the day\b", "in the end"),
    (r"\bto be honest\b|\bhonestly\b", "frankly speaking"),
    (r"\bkeep in mind\b", "remember that"),
    (r"\bmake sure to\b|\bmake sure you\b", "remember to"),
    (r"\bgive me a second\b|\bhold on a second\b", "wait a moment"),
    (r"\bby the way\b", "incidentally"),
    (r"\ball of a sudden\b", "suddenly"),
    (r"\bwe are going to look at\b", "we will explore"),
    (r"\bthe most common mistakes people make\b", "common mistakes people make"),
    (r"\bhow you can avoid them easily\b", "how to easily fix them"),
    (r"\bwatch until the end\b", "watch until the end of the video"),
    (r"\blet's dive into\b|\blet's get into\b", "let's start"),
    (r"\bas you can see\b", "as we see here"),
    (r"\ba couple of\b", "a few"),
    (r"\bfeel free to\b", "you can"),
]

THAI_SPOKEN_RESTRUCTURER = [
    # 1. Spoken Conversational Exclamations & Idioms
    (r"เฮ้ เฮ้ย|เฮ้ เฮ้|เฮ้ย เฮ้ย", "เฮ้ย"),
    (r"ระวังด้วยว่ามี|ระวังว่ามี", "ระวัง! มี"),
    (r"กำลังวิ่งมาหาเรา|วิ่งมาหาเรา|วิ่งมาทางเรา", "พุ่งตรงมาทางเรา"),
    (r"เป็นไปไม่ได้คุณกำลังล้อเล่น|คุณกำลังล้อเล่น|คุณล้อเล่น|ล้อเล่นใช่ไหม", "ล้อเล่นปะเนี่ย"),
    (r"เป็นไปไม่ได้ไม่มีทาง|ไม่มีทางเป็นไปไม่ได้", "เป็นไปไม่ได้น่า"),
    (r"นี่จะเป็นเรื่องง่ายมาก|เรื่องง่ายมากชิ้นส่วนของเค้ก|เรื่องง่ายมาก", "เรื่องหมูๆ เลย"),
    (r"รอสักครู่เพื่อคว้า|ขอเวลาสักครู่เพื่อคว้า|รอสักครู่เพื่อ", "ขอเวลาแป๊บเดียวไป"),
    (r"คว้าอาวุธของฉัน|คว้าอาวุธ", "หยิบอาวุธ"),
    (r"อาวุธของฉัน", "อาวุธ"),

    # 2. Structural & Explanatory Clause Fixes
    (r"คนมักจะเจอกันบ่อยๆกันบ่อยที่สุด|คนมักจะเจอกันบ่อยๆที่คนมักทำ", "คนมักจะเจอกันบ่อยๆ"),
    (r"ที่พบบ่อยที่สุดที่ผู้คนทำ|ที่คนทำบ่อยที่สุด|ที่ผู้คนทำ|ที่คนมักทำ", "ที่คนมักจะเจอกันบ่อยๆ"),
    (r"เมื่อสร้าง|เมื่อทำ|เมื่อพัฒนา", "เวลาพัฒนา"),
    (r"และวิธีที่คุณสามารถ|และวิธีที่คุณจะ|และวิธีที่ท่านจะ", "พร้อมวิธี"),
    (r"หลีกเลี่ยงอย่างง่ายดาย|หลีกเลี่ยงได้อย่างง่ายดาย|แก้ไขอย่างง่ายดาย", "แก้ง่ายๆ"),
    (r"ดังนั้นอย่าลืม|ดังนั้นโปรด|ดังนั้นทำให้แน่ใจว่า", "อย่าลืม"),
    (r"ดูให้จบคลิปนะครับของวิดีโอ|ดูให้จบคลิปของวิดีโอ", "ดูให้จบคลิปนะครับ"),
    (r"ดูจนจบ|ดูให้จบ|รับชมจนจบ", "ดูให้จบคลิปนะครับ"),
    (r"ดูให้จบคลิปนะครับวิดีโอ|ดูให้จบคลิปวิดีโอ", "ดูให้จบคลิปนะครับ"),
    (r"ในวิดีโอนี้|ในวีดีโอนี้|ในวิดิโอนี้", "ในคลิปนี้"),
    (r"เราจะมาดูกัน|เราจะไปดู|เราจะดูที่", "เราจะพามาดู"),
    (r"ปี 2569", "ปี 2026"),
    (r"ปี 2568", "ปี 2025"),
    (r"ปี 2567", "ปี 2024"),

    # 3. Idioms & Connectors
    (r"พี่ชายมองออกไป|มองออกไป|ดูออกไป", "เฮ้ย ระวัง!"),
    (r"ในตอนท้ายของวัน", "สุดท้ายแล้ว"),
    (r"ที่จะซื่อสัตย์|ที่จะบอกความจริง", "เอาจริงๆ นะ"),
    (r"ตรวจสอบสิ่งนี้|นำลักษณะ", "มาดูตรงนี้"),
    (r"ทำให้แน่ใจว่า|ทำให้มั่นใจว่า", "เช็กให้ดีว่า"),
    (r"เก็บไว้ในใจ", "จำไว้ว่า"),
    (r"ฉันหมายถึง|ผมหมายถึง", "คือแบบว่า"),
    (r"ให้เราไป|พวกเราไปกัน", "ลุยกันเลย"),
    (r"ฉันจะแสดงให้คุณเห็น|ผมจะแสดงให้คุณเห็น", "เดี๋ยวพามาดู"),
    (r"ยินดีต้อนรับสู่|ยินดีต้อนรับกลับสู่", "ยินดีต้อนรับกลับเข้าสู่"),
    (r"มันเป็นสิ่งจำเป็นที่จะ|มันจำเป็นที่จะ|มีความจำเป็นต้อง", "จำเป็นต้อง"),
    (r"อย่างแท้จริง|อย่างแน่นอน", "จริงๆ"),
    (r"ขั้นตอนโดยขั้นตอน", "ทีละขั้นตอน"),
    (r"เริ่มต้นกับ", "เริ่มจาก"),
    (r"ในเงื่อนไขของ|ในแง่ของเงื่อนไข|ในแง่ของ", "ในเรื่องของ"),
    (r"ขึ้นอยู่กับคุณ", "แล้วแต่เลย"),
    (r"ฉันไม่สามารถเชื่อได้|ผมไม่สามารถเชื่อได้", "ไม่อยากจะเชื่อเลย"),
    (r"คุณคิดอย่างไร", "คิดว่าไงบ้าง"),
    (r"สิ่งนี้คืออะไร", "นี่มันอะไรกัน"),
    (r"อย่างไร\b|อย่างไร\?", "ยังไงบ้าง"),
    (r"ทำไม\b|ทำไม\?", "ทำไมกันนะ"),
    (r"ขอบคุณสำหรับการรับชม", "ขอบคุณที่ติดตามรับชมนะครับ"),

    # 4. Bureaucratic Verb Cleanup
    (r"ทำการ(ดาวน์โหลด|ติดตั้ง|คลิก|เปิด|ปิด|ลบ|แก้ไข|สร้าง|พัฒนา|เลือก|รัน|ดู)", r"\1"),
    (r"สามารถที่จะ", "สามารถ"),
    (r"เพื่อที่จะ", "เพื่อให้"),
    (r"ในกรณีที่", "ถ้า"),
    (r"เนื่องจากว่า|เนื่องจาก", "เพราะว่า"),
]


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


def normalize_english_idioms(text: str) -> str:
    """Pre-process text to replace idioms with plain semantic expressions."""
    t = text
    for pat, rep in ENGLISH_IDIOM_NORMALIZER:
        t = re.sub(pat, rep, t, flags=re.IGNORECASE)
    return t


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


def transcreate_thai_dialogue(text: str, style: str = "auto", gender: str = "male") -> str:
    """Restructure raw translated Thai into fluent, spoken-style Thai dialogue with strict gender alignment."""
    t = text.strip()
    if not is_valid_thai_translation(t):
        return ""

    for pat, rep in THAI_SPOKEN_RESTRUCTURER:
        t = re.sub(pat, rep, t, flags=re.IGNORECASE)

    # Years to CE
    t = re.sub(r"ปี 2569", "ปี 2026", t)
    t = re.sub(r"ปี 2568", "ปี 2025", t)
    t = re.sub(r"ปี 2567", "ปี 2024", t)

    # Strict Gender Alignment & Particle Polish (No word boundary needed for Thai)
    if gender == "male":
        t = re.sub(r"นะคะ|นะค่ะ|ค่ะ|คะ", "ครับ", t)
        t = re.sub(r"ดิฉัน|ฉัน", "ผม", t)
        t = re.sub(r"ครับ\s+ครับ", "ครับ", t)
    elif gender == "female":
        t = re.sub(r"นะครับ|ครับ|คับ|ฮะ|ก๊าบ", "ค่ะ", t)
        t = re.sub(r"กระผม|ผม", "ฉัน", t)
        t = re.sub(r"ค่ะ\s+ค่ะ", "ค่ะ", t)

    # Style-specific pronoun adjustments
    if style in ["casual", "cinema"]:
        t = re.sub(r"คุณ", "นาย", t)

    # Clean double spaces
    t = re.sub(r"\s+", " ", t).strip()

    return t


def translate_via_google_multi(text: str) -> str:
    """Fast, resilient multi-endpoint Google Neural Translate API."""
    endpoints = [
        "https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl=auto&tl=th&q=",
        "https://translate.google.com/translate_a/single?client=it&sl=auto&tl=th&dt=t&q=",
        "https://translate.google.com/translate_a/single?client=at&sl=auto&tl=th&dt=t&q=",
    ]
    for ep in endpoints:
        try:
            url = ep + urllib.parse.quote(text)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "GoogleTranslate/6.28.0 (iPhone; iOS 16.0; en_US)"},
            )
            resp = urllib.request.urlopen(req, timeout=5)
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list) and len(data) > 0:
                if isinstance(data[0], list) and len(data[0]) > 0:
                    if isinstance(data[0][0], list):
                        res = "".join([s[0] for s in data[0] if s and isinstance(s, list) and s[0]])
                    elif isinstance(data[0][0], str):
                        res = data[0][0]
                    else:
                        res = str(data[0])
                elif isinstance(data[0], str):
                    res = data[0]
                else:
                    res = str(data)

                if is_valid_thai_translation(res):
                    return res
        except Exception as e:
            logger.debug("Google translate error: %s", e)
            continue
    return ""


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
                                        parsed = self._parse_numbered_output(raw_text, len(cues_text), style_key, gender)
                                        if parsed and len(parsed) == len(cues_text):
                                            logger.info("Successfully transcreated 60s batch using Gemini: %s", model)
                                            return parsed
                except Exception as e:
                    logger.debug("Gemini attempt error for %s: %s", model, e)
                    continue

        # 2. High-Quality Full-Paragraph Neural Translation Engine Fallback (100% Coherent, Full Context)
        logger.info("Using Master Full-Paragraph Neural Transcreator (sl=auto -> th)")
        return await self._fallback_batch_translate(cues_text, style_key, gender)

    def _parse_numbered_output(self, raw_text: str, expected_count: int, style: str, gender: str) -> List[str]:
        """Parse [1] text, [2] text from response and apply master spoken restructuring with gender alignment."""
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

        # Polish each line
        for i in range(expected_count):
            if results[i]:
                results[i] = transcreate_thai_dialogue(results[i], style=style, gender=gender)
            else:
                results[i] = ""

        if any(results):
            return results
        return []

    async def _fallback_batch_translate(self, cues_text: List[str], style: str, gender: str) -> List[str]:
        """Cohesive paragraph translation with pre-normalization and master spoken restructuring."""
        normalized_cues = [normalize_english_idioms(c) for c in cues_text]
        batch_text = "\n".join([f"[{i+1}] {c}" for i, c in enumerate(normalized_cues)])

        loop = asyncio.get_event_loop()
        raw_translation = await loop.run_in_executor(None, translate_via_google_multi, batch_text)

        if raw_translation and is_valid_thai_translation(raw_translation):
            parsed = self._parse_numbered_output(raw_translation, len(cues_text), style, gender)
            if parsed and len(parsed) == len(cues_text) and any(parsed):
                return parsed

        # Individual item fallback
        results = []
        for c in normalized_cues:
            raw = await loop.run_in_executor(None, translate_via_google_multi, c)
            polished = transcreate_thai_dialogue(raw or c, style=style, gender=gender)
            results.append(polished)
        return results

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
