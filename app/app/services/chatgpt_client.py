from __future__ import annotations

from typing import Any, Dict

import httpx

from ..config import get_settings
from ..schemas import ChatRequest, ChatResponse


async def call_chatgpt(payload: ChatRequest) -> ChatResponse:
    settings = get_settings()

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }

    body: Dict[str, Any] = {
        "model": payload.model or settings.openai_model,
        "messages": [m.dict() for m in payload.messages],
    }

    if payload.temperature is not None:
        body["temperature"] = payload.temperature
    if payload.max_tokens is not None:
        body["max_tokens"] = payload.max_tokens

    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        response = await client.post(
            f"{settings.openai_api_base}/chat/completions", json=body, headers=headers
        )
        response.raise_for_status()
        data = response.json()

    return ChatResponse(**data)
