"""Dual-tier caching layer (In-Memory LRU + SQLite) for translation and multi-engine audio dubbing."""

import hashlib
import logging
from typing import Optional, Tuple
import aiosqlite
from cachetools import LRUCache

from app.config import settings

logger = logging.getLogger(__name__)

# In-Memory Caches
_translation_lru = LRUCache(maxsize=settings.in_memory_cache_size)
_audio_lru = LRUCache(maxsize=settings.in_memory_cache_size)


CACHE_VERSION = "v22"


def _generate_cache_key(source_text: str, *args: str) -> str:
    """Generate a consistent versioned SHA256 cache key from input parameters."""
    normalized = ":::".join([CACHE_VERSION, source_text.strip().lower()] + [str(a).strip() for a in args])
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class DubbingCache:
    """Cache manager for translations and synthesized audio."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.sqlite_cache_db

    async def init_db(self) -> None:
        """Initialize SQLite database tables for translations and audio dubs."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS translations (
                        cache_key TEXT PRIMARY KEY,
                        source_text TEXT NOT NULL,
                        context TEXT,
                        translated_text TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS audio_dubs (
                        cache_key TEXT PRIMARY KEY,
                        source_text TEXT NOT NULL,
                        translated_text TEXT NOT NULL,
                        engine TEXT NOT NULL,
                        voice TEXT NOT NULL,
                        rate TEXT NOT NULL,
                        pitch TEXT NOT NULL,
                        style TEXT NOT NULL,
                        audio_data BLOB NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                await db.commit()
            logger.info("Dubbing cache database initialized at %s", self.db_path)
        except Exception as e:
            logger.warning("Failed to initialize SQLite cache db at %s: %s, falling back to /tmp/dub_cache.db", self.db_path, e)
            self.db_path = "/tmp/dub_cache.db"
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute("""
                        CREATE TABLE IF NOT EXISTS translations (
                            cache_key TEXT PRIMARY KEY,
                            source_text TEXT NOT NULL,
                            context TEXT,
                            translated_text TEXT NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    await db.execute("""
                        CREATE TABLE IF NOT EXISTS audio_dubs (
                            cache_key TEXT PRIMARY KEY,
                            source_text TEXT NOT NULL,
                            translated_text TEXT NOT NULL,
                            engine TEXT NOT NULL,
                            voice TEXT NOT NULL,
                            rate TEXT NOT NULL,
                            pitch TEXT NOT NULL,
                            style TEXT NOT NULL,
                            audio_data BLOB NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    await db.commit()
            except Exception as e2:
                logger.warning("Secondary SQLite init error: %s", e2)

    async def get_translation(self, source_text: str, context: str = "") -> Optional[str]:
        """Fetch cached translation from memory or SQLite."""
        key = _generate_cache_key(source_text, context)

        # 1. In-memory LRU
        if key in _translation_lru:
            return _translation_lru[key]

        # 2. SQLite
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT translated_text FROM translations WHERE cache_key = ?",
                    (key,),
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        translated = row[0]
                        _translation_lru[key] = translated
                        return translated
        except Exception as e:
            logger.debug("SQLite get_translation error: %s", e)

        return None

    async def set_translation(
        self, source_text: str, context: str, translated_text: str
    ) -> None:
        """Store translation in memory and SQLite."""
        key = _generate_cache_key(source_text, context)
        _translation_lru[key] = translated_text

        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO translations
                    (cache_key, source_text, context, translated_text)
                    VALUES (?, ?, ?, ?)
                    """,
                    (key, source_text, context, translated_text),
                )
                await db.commit()
        except Exception as e:
            logger.debug("SQLite set_translation error: %s", e)

    async def get_audio_dub(
        self,
        source_text: str,
        engine: str,
        voice: str,
        rate: str,
        pitch: str,
        style: str = "",
        context: str = "",
    ) -> Optional[Tuple[str, bytes]]:
        """Fetch cached translated text and audio bytes."""
        key = _generate_cache_key(source_text, engine, voice, rate, pitch, style, context)

        # 1. In-memory LRU
        if key in _audio_lru:
            return _audio_lru[key]

        # 2. SQLite
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT translated_text, audio_data FROM audio_dubs WHERE cache_key = ?",
                    (key,),
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        translated_text, audio_data = row[0], row[1]
                        _audio_lru[key] = (translated_text, audio_data)
                        return translated_text, audio_data
        except Exception as e:
            logger.debug("SQLite get_audio_dub error: %s", e)

        return None

    async def set_audio_dub(
        self,
        source_text: str,
        engine: str,
        voice: str,
        rate: str,
        pitch: str,
        style: str,
        context: str,
        translated_text: str,
        audio_data: bytes,
    ) -> None:
        """Store translated text and audio bytes in cache."""
        key = _generate_cache_key(source_text, engine, voice, rate, pitch, style, context)
        _audio_lru[key] = (translated_text, audio_data)

        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO audio_dubs
                    (cache_key, source_text, translated_text, engine, voice, rate, pitch, style, audio_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (key, source_text, translated_text, engine, voice, rate, pitch, style, audio_data),
                )
                await db.commit()
        except Exception as e:
            logger.debug("SQLite set_audio_dub error: %s", e)


cache = DubbingCache()
