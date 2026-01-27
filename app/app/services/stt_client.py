from __future__ import annotations

import logging
from typing import Optional

import httpx

from ..config import get_settings

logger = logging.getLogger("app.stt")


class STTError(RuntimeError):
    pass


async def transcribe_audio_openai(
    *,
    audio_bytes: bytes,
    filename: str,
    content_type: str,
    language: Optional[str] = None,
) -> str:
    """
    Transcribe audio using OpenAI's speech-to-text endpoint.

    Returns plain transcript text.
    """
    settings = get_settings()

    if not settings.openai_api_key:
        raise STTError("OPENAI_API_KEY is not configured")

    model = getattr(settings, "stt_model", "") or "gpt-4o-mini-transcribe"
    base = str(settings.openai_api_base).rstrip("/")
    url = f"{base}/audio/transcriptions"

    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    data = {"model": model}
    if language:
        data["language"] = language

    # OpenAI expects multipart/form-data with a file field named `file`.
    files = {
        "file": (filename, audio_bytes, content_type or "application/octet-stream"),
    }

    timeout = getattr(settings, "request_timeout_seconds", 60)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, headers=headers, data=data, files=files)
        resp.raise_for_status()
        payload = resp.json()

    if isinstance(payload, dict):
        text = payload.get("text")
        if isinstance(text, str):
            return text

    raise STTError("Unexpected transcription response shape")

