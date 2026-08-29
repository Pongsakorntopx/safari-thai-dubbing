"""Unit tests for FastAPI endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from app.main import app


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "voices" in data
        assert "khanomtan-v1.1-female" in data["voices"]
        assert "khanomtan-v1.1-male" in data["voices"]
        assert "vits-thai-female" in data["voices"]
        assert "vits-thai-male" in data["voices"]


@pytest.mark.asyncio
async def test_list_voices():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/api/v1/voices")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "khanomtan-v1.1-female" in data["voices"]
        assert "khanomtan-v1.1-male" in data["voices"]
        assert "vits-thai-female" in data["voices"]
        assert "vits-thai-male" in data["voices"]


@pytest.mark.asyncio
async def test_dub_endpoint_cached():
    with patch("app.cache.cache.get_audio_dub", new_callable=AsyncMock) as mock_get_dub:
        mock_get_dub.return_value = ("สวัสดีค่ะ", b"test_audio_bytes")

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            payload = {
                "text": "Hello world",
                "voice": "khanomtan-v1.1-female",
                "rate": "+0%",
            }
            response = await ac.post("/api/v1/dub", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["translatedText"] == "สวัสดีค่ะ"
            assert data["cached"] is True
            assert len(data["base64Audio"]) > 0
