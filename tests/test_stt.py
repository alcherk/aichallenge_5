import pytest
import httpx
from unittest.mock import AsyncMock, patch

from app.app.main import app, settings


@pytest.mark.asyncio
async def test_stt_transcribe_disabled_returns_404():
    settings.stt_enabled = False
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("a.webm", b"123", "audio/webm")}
        resp = await client.post("/api/stt/transcribe", files=files)
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stt_transcribe_rejects_non_audio_content_type():
    settings.stt_enabled = True
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("a.txt", b"hello", "text/plain")}
        resp = await client.post("/api/stt/transcribe", files=files)
        assert resp.status_code == 415


@pytest.mark.asyncio
async def test_stt_transcribe_enforces_max_bytes():
    settings.stt_enabled = True
    settings.stt_max_bytes = 2
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("a.webm", b"123", "audio/webm")}
        resp = await client.post("/api/stt/transcribe", files=files)
        assert resp.status_code == 413


@pytest.mark.asyncio
async def test_stt_transcribe_success_returns_text():
    settings.stt_enabled = True
    settings.stt_provider = "openai"
    settings.stt_max_bytes = 25_000_000

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        with patch(
            "app.app.services.stt_client.transcribe_audio_openai",
            new=AsyncMock(return_value="hello world"),
        ):
            files = {"file": ("a.webm", b"123", "audio/webm")}
            resp = await client.post("/api/stt/transcribe", files=files)
            assert resp.status_code == 200
            assert resp.json() == {"text": "hello world"}

