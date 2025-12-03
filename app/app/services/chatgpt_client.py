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

    # Prepare messages with system prompt
    messages = [m.dict() for m in payload.messages]
    
    # Check if there's already a system message
    has_system_message = any(msg.get("role") == "system" for msg in messages)
    
    # Add system prompt if not present
    if not has_system_message:
        system_prompt = """Ты помощник-прокси между пользователем и системой.

Твоя задача — сначала ПОНЯТЬ задачу, а потом решать.

Формат ответа: обычный текст или Markdown.

Если информации недостаточно, задай уточняющие вопросы.

Если информации достаточно и можно решить задачу, предоставь подробное решение.

Правила:
- Не придумывай ответ на задачу, если нет данных — сперва задавай вопросы.
- Когда считаешь, что вопросов достаточно, предоставь итоговый ответ.
- Используй Markdown для форматирования (заголовки, списки, код и т.д.)."""
        
        messages.insert(0, {
            "role": "system",
            "content": system_prompt
        })
    
    body: Dict[str, Any] = {
        "model": payload.model or settings.openai_model,
        "messages": messages,
    }

    if payload.temperature is not None:
        body["temperature"] = payload.temperature
    if payload.max_tokens is not None:
        body["max_tokens"] = payload.max_tokens
    
    # No response_format - allow plain text/markdown output

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
