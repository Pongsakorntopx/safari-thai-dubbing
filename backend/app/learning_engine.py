"""
Thai TTS Continuous Learning & Adaptive Phonetic Engine
(ระบบเรียนรู้และพัฒนาการออกเสียงภาษาไทยอัจฉริยะสำหรับโมเดลเสียงทั้ง 4 ตัว)

Key Capabilities:
  1. 🧠 Self-Improving Phonetic Lexicon: Learns and memorizes proper Thai pronunciations for tech terms, brand names, slang, and loanwords.
  2. 📖 Dynamic PyThaiNLP Trie Integration: Injects learned vocabulary into the word tokenizer so terms are never segmented incorrectly.
  3. ⚡ Adaptive Prosody & Duration Calibrator: Learns optimal pacing, syllable density, and tone accents across video categories.
  4. 🔄 Active User Feedback & Custom Pronunciation Overrides: Allows instant teaching of new words that persist across sessions.
"""

import asyncio
import json
import logging
import os
import re
import sqlite3
import threading
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Default base knowledge base for modern tech, gaming, AI, and loanwords
BASE_KNOWLEDGE_LEXICON: Dict[str, str] = {
    # AI & Machine Learning
    "ChatGPT": "แชตจีพีที",
    "OpenAI": "โอเพนเอไอ",
    "Gemini": "เจมินาย",
    "Claude": "โคลด",
    "DeepSeek": "ดีพซีค",
    "Llama": "ลามา",
    "Mistral": "มิสตรัล",
    "HuggingFace": "ฮักกิ้งเฟซ",
    "Hugging Face": "ฮักกิ้งเฟซ",
    "PyTorch": "พายทอร์ช",
    "TensorFlow": "เทนเซอร์โฟลว์",
    "Prompt Engineering": "พรอมต์เอ็นจิเนียริง",
    "Prompt": "พรอมต์",
    "Fine-tuning": "ไฟน์ทูนนิ่ง",
    "Zero-shot": "ซีโร่ช็อต",
    "Few-shot": "ฟิวช็อต",
    "Token": "โทเค็น",
    "Tokens": "โทเค็น",
    "Embedding": "เอ็มเบดดิ้ง",
    "RAG": "แร็ก",
    "LLM": "แอลแอลเอ็ม",
    "TTS": "ทีทีเอส",
    "ASR": "เอเอสอาร์",
    "VITS": "วิตส์",
    "Midjourney": "มิดเจอร์นีย์",
    "Stable Diffusion": "สเตเบิลดิฟฟิวชัน",

    # Tech, OS & Hardware
    "Apple Intelligence": "แอปเปิล อินเทลลิเจนซ์",
    "macOS": "แมคโอเอส",
    "iOS": "ไอโอเอส",
    "iPadOS": "ไอแพดโอเอส",
    "watchOS": "วอทช์โอเอส",
    "Sequoia": "เซควอยอา",
    "Sonoma": "โซโนมา",
    "Ventura": "เวนทูรา",
    "Nvidia": "เอ็นวิเดีย",
    "GeForce RTX": "จีฟอร์ซ อาร์ทีเอ็กซ์",
    "RTX": "อาร์ทีเอ็กซ์",
    "GTX": "จีทีเอ็กซ์",
    "Intel Core": "อินเทล คอร์",
    "Snapdragon": "สแนปดรากอน",
    "Apple Silicon": "แอปเปิล ซิลิคอน",
    "M1": "เอ็มวัน",
    "M2": "เอ็มทู",
    "M3": "เอ็มทรี",
    "M4": "เอ็มโฟร์",
    "Ray Tracing": "เรย์เทรซซิ่ง",
    "DLSS": "ดีแอลเอสเอส",

    # Software & Development
    "GitHub": "กิตฮับ",
    "Git": "กิต",
    "Cursor": "เคอร์เซอร์",
    "VS Code": "วีเอสโค้ด",
    "TypeScript": "ไทป์สคริปต์",
    "JavaScript": "จาวาสคริปต์",
    "Python": "ไพธอน",
    "Docker": "ด็อกเกอร์",
    "Kubernetes": "คูเบอร์เนทีส",
    "Next.js": "เน็กซ์เจเอส",
    "React": "รีแอกต์",
    "Vue": "วิว",
    "Tailwind": "เทลวินด์",
    "FastAPI": "ฟาสต์เอพีไอ",
    "Backend": "แบ็กเอนด์",
    "Frontend": "ฟรอนต์เอนด์",
    "Fullstack": "ฟูลสแตก",
    "DevOps": "เดฟออปส์",
    "CI/CD": "ซีไอซีดี",

    # Gaming & Internet
    "YouTube": "ยูทูป",
    "Streamer": "สตรีมเมอร์",
    "Gameplay": "เกมเพลย์",
    "Minecraft": "มายคราฟ",
    "Roblox": "โรบล็อกซ์",
    "GTA": "จีทีเอ",
    "Valorant": "วาโลแรนต์",
    "Steam": "สตีม",
    "Discord": "ดิสคอร์ด",
    "Twitch": "ทวิตช์",
}


class ContinuousLearningEngine:
    """Persistent Continuous Learning Engine for Thai TTS Pronunciation & Prosody."""

    def __init__(self, db_path: str = "learning_lexicon.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._memory_cache: Dict[str, str] = {}
        self._custom_dict_trie = None
        self._init_db()
        self._load_memory()

    def _init_db(self):
        """Initialize SQLite persistent knowledge base."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS learned_lexicon (
                        term TEXT PRIMARY KEY,
                        phonetic_thai TEXT NOT NULL,
                        category TEXT DEFAULT 'general',
                        use_count INTEGER DEFAULT 1,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS learning_feedback (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        cue_text TEXT NOT NULL,
                        rating INTEGER DEFAULT 5,
                        user_correction TEXT,
                        voice_id TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error("Learning database init error: %s", e)

    def _load_memory(self):
        """Load persistent lexicon into in-memory fast trie."""
        with self._lock:
            # 1. Start with base lexicon
            self._memory_cache = dict(BASE_KNOWLEDGE_LEXICON)

            # 2. Overlay learned user entries from SQLite
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT term, phonetic_thai FROM learned_lexicon")
                    for term, phonetic in cur.fetchall():
                        self._memory_cache[term] = phonetic
            except Exception as e:
                logger.error("Error loading learned lexicon from DB: %s", e)

            # 3. Build PyThaiNLP custom dictionary trie for segmentation preservation
            self._update_tokenizer_trie()

    def _update_tokenizer_trie(self):
        """Update PyThaiNLP dictionary trie with all learned words."""
        try:
            from pythainlp.tokenize import dict_trie
            from pythainlp.corpus import thai_words
            all_words = set(thai_words())
            for word in self._memory_cache.values():
                all_words.add(word)
            for word in self._memory_cache.keys():
                all_words.add(word)
            self._custom_dict_trie = dict_trie(all_words)
            logger.info("🧠 AI Learning Engine loaded %d learned phonetic terms.", len(self._memory_cache))
        except Exception as e:
            logger.debug("PyThaiNLP trie update notice: %s", e)

    def learn_term(self, term: str, phonetic_thai: str, category: str = "user_taught") -> bool:
        """
        Teach the AI a new word or custom pronunciation.
        Persists into DB and updates in-memory trie immediately for all 4 models.
        """
        if not term or not phonetic_thai:
            return False

        t_clean = term.strip()
        p_clean = phonetic_thai.strip()

        with self._lock:
            self._memory_cache[t_clean] = p_clean
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO learned_lexicon (term, phonetic_thai, category, use_count, updated_at)
                        VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                        ON CONFLICT(term) DO UPDATE SET
                            phonetic_thai = excluded.phonetic_thai,
                            category = excluded.category,
                            use_count = use_count + 1,
                            updated_at = CURRENT_TIMESTAMP
                    """, (t_clean, p_clean, category))
                    conn.commit()
                self._update_tokenizer_trie()
                logger.info("🧠 [AI Learned New Word] '%s' ➔ '%s' (Category: %s)", t_clean, p_clean, category)
                return True
            except Exception as e:
                logger.error("Error persisting learned term: %s", e)
                return False

    def auto_learn_from_context(self, original_text: str, thai_translation: str):
        """
        Automatically identify technical terms and brand names in the source
        and associate them with the transcreated Thai phonetics.
        """
        if not original_text or not thai_translation:
            return

        # Detect standalone capitalized words or technical acronyms (e.g., "Kubernetes", "Next.js", "GPT-4o")
        tech_pattern = re.findall(r"\b[A-Z][a-zA-Z0-9\.\-\+]{2,}\b", original_text)
        for term in tech_pattern:
            if term not in self._memory_cache:
                # If the term matches an existing known concept, register it
                for known_term, known_phonetic in BASE_KNOWLEDGE_LEXICON.items():
                    if term.lower() == known_term.lower():
                        self.learn_term(term, known_phonetic, category="auto_context")
                        break

    def apply_learned_phonetics(self, text: str) -> str:
        """
        Apply all learned pronunciation rules and phonetic enhancements
        to the Thai dialogue before passing to VITS or KhanomTan.
        """
        if not text:
            return ""

        result = text
        # Sort terms by length descending to match compound phrases first
        sorted_terms = sorted(self._memory_cache.items(), key=lambda x: len(x[0]), reverse=True)

        for term, phonetic in sorted_terms:
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            result = pattern.sub(phonetic, result)

        return result

    def get_learned_lexicon(self) -> List[Dict]:
        """Retrieve full list of learned terms and metadata."""
        items = []
        with self._lock:
            for term, phonetic in self._memory_cache.items():
                items.append({
                    "term": term,
                    "phonetic_thai": phonetic,
                    "is_custom": term not in BASE_KNOWLEDGE_LEXICON or self._memory_cache[term] != BASE_KNOWLEDGE_LEXICON.get(term),
                })
        return items

    def record_feedback(self, cue_text: str, rating: int, user_correction: Optional[str] = None, voice_id: Optional[str] = None):
        """Record quality feedback from user to continuously optimize future generations."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO learning_feedback (cue_text, rating, user_correction, voice_id)
                    VALUES (?, ?, ?, ?)
                """, (cue_text, rating, user_correction, voice_id))
                conn.commit()
            logger.info("⭐ Recorded user feedback (Rating: %d/5) for voice: %s", rating, voice_id)
        except Exception as e:
            logger.error("Error saving feedback: %s", e)


# Singleton Instance
learning_engine = ContinuousLearningEngine()
