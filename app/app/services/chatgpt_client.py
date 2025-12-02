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
    
    # Always include response_format for structured JSON output
    # Using json_schema format as per OpenAI API specification
    body["response_format"] = {
        "type": "json_schema",
        "json_schema": {
            "name": "chat_message",
            "schema": {
                "type": "object",
                "properties": {
                    "role": {
                        "type": "string",
                        "enum": ["assistant"]
                    },
                    "content": {
                        "type": "string"
                    }
                },
                "required": ["role", "content"],
                "additionalProperties": False
            },
            "strict": True
        }
    }

    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        response = await client.post(
            f"{settings.openai_api_base}/chat/completions", json=body, headers=headers
        )
        
        if not response.is_success:
            # Try to get detailed error message from API
            try:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", f"API returned status {response.status_code}")
                raise RuntimeError(f"OpenAI API error: {error_msg}")
            except Exception:
                raise RuntimeError(f"OpenAI API error: HTTP {response.status_code}")
        
        data = response.json()

    return ChatResponse(**data)
