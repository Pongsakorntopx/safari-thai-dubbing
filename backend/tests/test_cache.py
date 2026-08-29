"""Unit tests for backend caching layer."""

import os
import pytest
import pytest_asyncio
from app.cache import DubbingCache, _generate_cache_key


@pytest.mark.asyncio
async def test_cache_key_generation():
    key1 = _generate_cache_key("Hello world", "th-TH-PremwadeeNeural", "+5%")
    key2 = _generate_cache_key("hello world", "th-TH-PremwadeeNeural", "+5%")
    assert key1 == key2  # Case-insensitive source text matching


@pytest.mark.asyncio
async def test_cache_sqlite_operations(tmp_path):
    test_db = str(tmp_path / "test_cache.db")
    test_cache = DubbingCache(db_path=test_db)
    await test_cache.init_db()

    # 1. Test translation caching
    source = "This is a great tutorial."
    context = "Programming video"
    translated = "นี่คือบทเรียนที่ยอดเยี่ยมมากครับ"

    assert await test_cache.get_translation(source, context) is None
    await test_cache.set_translation(source, context, translated)
    assert await test_cache.get_translation(source, context) == translated

    # 2. Test audio dubbing caching
    voice = "th-TH-PremwadeeNeural"
    rate = "+5%"
    pitch = "+0Hz"
    dummy_audio = b"\xff\xfb\x90\x44" * 10

    assert await test_cache.get_audio_dub(source, voice, rate, pitch, context) is None
    await test_cache.set_audio_dub(
        source, voice, rate, pitch, context, translated, dummy_audio
    )
    result = await test_cache.get_audio_dub(source, voice, rate, pitch, context)
    assert result is not None
    assert result[0] == translated
    assert result[1] == dummy_audio
