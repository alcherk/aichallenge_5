from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging
import os

import httpx

from ..config import get_settings
from ..schemas import ChatRequest, ChatResponse
from ..mcp.manager import ensure_mcp_manager
from ..rag.chunkenizer_adapter import retrieve_chunks
from ..rag.context_builder import build_context_block
from ..rag.prompt_injector import inject_rag_context

logger = logging.getLogger("app.openai")


def _truthy_env(name: str) -> bool:
    v = (os.getenv(name, "") or "").strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


def _json_preview(value: Any, *, limit: int = 8000) -> tuple[str, bool]:
    try:
        s = json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        s = str(value)
    if len(s) > limit:
        return (s[:limit] + "…", True)
    return (s, False)

def _tools_to_responses_api(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert Chat Completions-style tools into Responses API tool definitions.

    Chat Completions tool:
      {"type":"function","function":{"name": "...", "description": "...", "parameters": {...}}}

    Responses API tool:
      {"type":"function","name":"...","description":"...","parameters": {...}}
    """
    out: List[Dict[str, Any]] = []
    for t in tools or []:
        if not isinstance(t, dict):
            continue
        t_type = t.get("type")
        if t_type != "function":
            # Pass through unknown tool types if present (future-proof).
            out.append(t)
            continue

        # Already in Responses format?
        if isinstance(t.get("name"), str) and t.get("name"):
            out.append(t)
            continue

        fn = t.get("function") or {}
        if not isinstance(fn, dict):
            fn = {}
        name = fn.get("name")
        if not isinstance(name, str) or not name:
            # Skip invalid tools; upstream will error otherwise.
            continue

        out.append(
            {
                "type": "function",
                "name": name,
                "description": fn.get("description"),
                "parameters": fn.get("parameters"),
            }
        )
    return out


def _messages_to_responses_input(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert Chat Completions-style messages -> Responses API `input`.
    Minimal shape used here:
      [{"role": "...", "content": "..."}]
    """
    out: List[Dict[str, Any]] = []
    for m in messages:
        role = m.get("role")
        content = m.get("content")
        if role and content is not None:
            out.append({"role": role, "content": content})
    return out


def _extract_text_from_responses(response_json: Dict[str, Any]) -> str:
    """
    Extract assistant text from a Responses API response object.
    """
    output = response_json.get("output") or []
    parts: List[str] = []
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "message":
                continue
            if item.get("role") != "assistant":
                continue
            content = item.get("content") or []
            if isinstance(content, list):
                for c in content:
                    if not isinstance(c, dict):
                        continue
                    # Most common: {"type":"output_text","text":"..."}
                    if c.get("type") in ("output_text", "text") and isinstance(c.get("text"), str):
                        parts.append(c["text"])
            elif isinstance(content, str):
                parts.append(content)
    return "".join(parts)


def _responses_usage_to_chat_usage(response_json: Dict[str, Any]) -> Optional[Dict[str, int]]:
    usage = response_json.get("usage")
    if not isinstance(usage, dict):
        return None
    prompt = usage.get("input_tokens")
    completion = usage.get("output_tokens")
    total = usage.get("total_tokens")
    if isinstance(prompt, int) and isinstance(completion, int) and isinstance(total, int):
        return {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": total}
    return None


def _prepare_messages(payload: ChatRequest) -> List[Dict[str, Any]]:
    """
    Prepare OpenAI messages from the inbound request (includes system prompt if missing).

    Note: we intentionally return raw dicts (not pydantic models) because
    OpenAI tool messages use additional roles/fields not present in our schemas.
    """
    messages = [m.dict() for m in payload.messages]

    has_system_message = any(msg.get("role") == "system" for msg in messages)
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

        messages.insert(
            0,
            {
                "role": "system",
                "content": system_prompt,
            },
        )

    return messages


def _normalize_tool_calls(tool_calls: Any) -> List[Dict[str, Any]]:
    """
    Ensure tool_calls are in the OpenAI-required shape:
    [{id, type:"function", function:{name, arguments}}...]
    """
    out: List[Dict[str, Any]] = []
    if not isinstance(tool_calls, list):
        return out
    for tc in tool_calls:
        if not isinstance(tc, dict):
            continue
        fn = tc.get("function") or {}
        if not isinstance(fn, dict):
            fn = {}
        out.append(
            {
                "id": tc.get("id"),
                "type": tc.get("type") or "function",
                "function": {
                    "name": fn.get("name"),
                    "arguments": fn.get("arguments") or "",
                },
            }
        )
    return out


async def call_chatgpt(payload: ChatRequest) -> ChatResponse:
    settings = get_settings()

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }

    messages = _prepare_messages(payload)
    
    # RAG retrieval (if enabled)
    if settings.rag_enabled:
        # Extract latest user message for retrieval query
        user_messages = [m for m in messages if m.get("role") == "user"]
        if user_messages:
            query = user_messages[-1].get("content", "")
            if query and query.strip():
                logger.debug(
                    "RAG retrieval starting query_len=%d top_k=%d",
                    len(query),
                    settings.rag_top_k,
                )
                chunks = await retrieve_chunks(
                    query=query,
                    top_k=settings.rag_top_k,
                    base_url=settings.chunkenizer_api_url,
                )
                if chunks:
                    context = build_context_block(chunks, settings.rag_max_context_chars)
                    if context:
                        messages = inject_rag_context(messages, context)
                        logger.info(
                            "RAG context injected chunks=%d context_size=%d",
                            len(chunks),
                            len(context),
                        )
                    else:
                        logger.debug("RAG context block empty after formatting")
                else:
                    logger.debug("RAG retrieval returned no chunks")
            else:
                logger.debug("RAG skipped: empty user query")
        else:
            logger.debug("RAG skipped: no user messages found")
    else:
        logger.debug("RAG disabled")
    
    base_input = _messages_to_responses_input(messages)
    
    mcp_enabled = bool(payload.mcp_enabled) if payload.mcp_enabled is not None else bool(
        payload.mcp_config_path or settings.mcp_config_path
    )
    mgr = await ensure_mcp_manager(
        mcp_config_path=(
            (payload.mcp_config_path or settings.mcp_config_path or None) if mcp_enabled else None
        ),
        workspace_root=Path(payload.workspace_root or settings.workspace_root),
    )
    tools = mgr.openai_tools() if mgr is not None else []
    resp_tools = _tools_to_responses_api(tools) if tools else []

    # Tool loop (server-side): assistant -> tool_calls -> tool results -> assistant
    # This is bounded to prevent infinite loops.
    tool_messages: List[Dict[str, Any]] = list(messages)
    max_rounds = 8

    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        previous_response_id: Optional[str] = None
        for _ in range(max_rounds):
            body: Dict[str, Any] = {
                "model": payload.model or settings.openai_model,
                "input": base_input,
            }
            if previous_response_id:
                body["previous_response_id"] = previous_response_id

            if resp_tools:
                body["tools"] = resp_tools
                body["tool_choice"] = "auto"

            if payload.temperature is not None:
                body["temperature"] = payload.temperature
            if payload.max_tokens is not None:
                body["max_tokens"] = payload.max_tokens

            base = str(settings.openai_api_base).rstrip("/")
            path = str(getattr(settings, "openai_chat_path", "chat/responses")).lstrip("/")
            url = f"{base}/{path}"
            logger.debug(
                "call_chatgpt upstream request url=%s model=%s input_items=%d tools=%d temperature=%s max_tokens=%s previous_response_id=%s",
                url,
                body.get("model"),
                len(base_input),
                len(resp_tools) if resp_tools else 0,
                body.get("temperature"),
                body.get("max_tokens"),
                previous_response_id,
            )
            if _truthy_env("HTTP_LOG_POST_PAYLOADS"):
                preview, truncated = _json_preview(body)
                logger.info(
                    json.dumps(
                        {
                            "event": "http_post_payload",
                            "target": "openai",
                            "url": url,
                            "truncated": truncated,
                            "payload": preview,
                        },
                        ensure_ascii=False,
                    )
                )
            response = await client.post(
                url, json=body, headers=headers
            )
            # Let callers surface full upstream error bodies (JSON/text) for debugging.
            response.raise_for_status()

            data = response.json()

            # Responses API tool calls appear as output items with type "function_call".
            output = data.get("output") or []
            function_calls: List[Dict[str, Any]] = []
            if isinstance(output, list):
                for item in output:
                    if isinstance(item, dict) and item.get("type") == "function_call":
                        function_calls.append(item)

            if function_calls:
                if mgr is None:
                    raise RuntimeError("Model requested tool calls but MCP is not enabled")
                response_id = data.get("id")
                if not isinstance(response_id, str) or not response_id:
                    raise RuntimeError("Upstream returned tool calls but no response id was provided")

                tool_outputs: List[Dict[str, Any]] = []
                for fc in function_calls:
                    call_id = fc.get("call_id") or fc.get("id")
                    name = fc.get("name")
                    args_raw = fc.get("arguments") or "{}"
                    if not isinstance(call_id, str) or not call_id:
                        continue
                    try:
                        args = json.loads(args_raw) if isinstance(args_raw, str) else {}
                    except Exception:
                        args = {}
                    try:
                        result = await mgr.call_openai_tool(str(name), args)
                        tool_outputs.append(
                            {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": json.dumps(result, ensure_ascii=False),
                            }
                        )
                    except Exception as e:
                        tool_outputs.append(
                            {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": json.dumps(
                                    {"error": {"type": type(e).__name__, "detail": str(e)}},
                                    ensure_ascii=False,
                                ),
                            }
                        )

                # Continue the conversation using previous_response_id and only tool outputs as new input.
                previous_response_id = response_id
                base_input = tool_outputs
                continue

            # Final text response -> adapt to ChatResponse shape for the UI.
            full_text = _extract_text_from_responses(data)
            usage_obj = _responses_usage_to_chat_usage(data)
            return ChatResponse(
                id=str(data.get("id") or "resp"),
                model=str(data.get("model") or (payload.model or settings.openai_model)),
                choices=[
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": full_text},
                        "finish_reason": "stop",
                    }
                ],
                usage=usage_obj,
            )

    raise RuntimeError("Tool loop exceeded maximum rounds")


async def stream_chatgpt(payload: ChatRequest):
    """
    Yields decoded streaming chunks from OpenAI chat.completions.
    Each yielded item is a dict like the non-streaming response chunks:
    - {"choices":[{"delta":{"content":"..."}, ...}], ...}
    """
    settings = get_settings()

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }

    base_messages = _prepare_messages(payload)
    
    # RAG retrieval (if enabled)
    if settings.rag_enabled:
        # Extract latest user message for retrieval query
        user_messages = [m for m in base_messages if m.get("role") == "user"]
        if user_messages:
            query = user_messages[-1].get("content", "")
            if query and query.strip():
                logger.debug(
                    "RAG retrieval starting (stream) query_len=%d top_k=%d",
                    len(query),
                    settings.rag_top_k,
                )
                chunks = await retrieve_chunks(
                    query=query,
                    top_k=settings.rag_top_k,
                    base_url=settings.chunkenizer_api_url,
                )
                if chunks:
                    context = build_context_block(chunks, settings.rag_max_context_chars)
                    if context:
                        base_messages = inject_rag_context(base_messages, context)
                        logger.info(
                            "RAG context injected (stream) chunks=%d context_size=%d",
                            len(chunks),
                            len(context),
                        )
                    else:
                        logger.debug("RAG context block empty after formatting (stream)")
                else:
                    logger.debug("RAG retrieval returned no chunks (stream)")
            else:
                logger.debug("RAG skipped: empty user query (stream)")
        else:
            logger.debug("RAG skipped: no user messages found (stream)")
    else:
        logger.debug("RAG disabled (stream)")
    
    base_input = _messages_to_responses_input(base_messages)
    mcp_enabled = bool(payload.mcp_enabled) if payload.mcp_enabled is not None else bool(
        payload.mcp_config_path or settings.mcp_config_path
    )
    mgr = await ensure_mcp_manager(
        mcp_config_path=(
            (payload.mcp_config_path or settings.mcp_config_path or None) if mcp_enabled else None
        ),
        workspace_root=Path(payload.workspace_root or settings.workspace_root),
    )
    tools = mgr.openai_tools() if mgr is not None else []
    resp_tools = _tools_to_responses_api(tools) if tools else []

    # Streaming mode uses the Responses API event stream and currently does not
    # support the server-side tool loop used by the old chat.completions stream.
    # We keep max_rounds for parity but will exit after one stream.
    max_rounds = 8

    async with httpx.AsyncClient(timeout=None) as client:
        for _ in range(max_rounds):
            body: Dict[str, Any] = {
                "model": payload.model or settings.openai_model,
                "input": base_input,
                "stream": True,
            }
            # NOTE: We intentionally do NOT send `stream_options`.
            # Many OpenAI-compatible backends (and some proxies/gateways) reject
            # unknown fields with HTTP 400.
            if resp_tools:
                body["tools"] = resp_tools
                body["tool_choice"] = "auto"
            if payload.temperature is not None:
                body["temperature"] = payload.temperature
            if payload.max_tokens is not None:
                body["max_tokens"] = payload.max_tokens

            finish_reason: Optional[str] = None

            base = str(settings.openai_api_base).rstrip("/")
            path = str(getattr(settings, "openai_chat_path", "chat/responses")).lstrip("/")
            url = f"{base}/{path}"
            logger.debug(
                "stream_chatgpt upstream request url=%s model=%s input_items=%d tools=%d temperature=%s max_tokens=%s",
                url,
                body.get("model"),
                len(base_input),
                len(resp_tools) if resp_tools else 0,
                body.get("temperature"),
                body.get("max_tokens"),
            )
            async with client.stream(
                "POST",
                url,
                json=body,
                headers=headers,
            ) as response:
                # IMPORTANT: For streaming requests, httpx raises on status *before* the body is read.
                # Many upstreams return a useful JSON error body (e.g. invalid model/param),
                # so we must consume it first to make it available in the HTTPStatusError handler.
                if response.status_code >= 400:
                    await response.aread()
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if not line.startswith("data:"):
                        continue

                    data = line[len("data:") :].strip()
                    if data == "[DONE]":
                        break

                    event = json.loads(data)

                    # Responses API emits different event shapes; we normalize deltas
                    # into Chat Completions-like chunks for the rest of the app.
                    # Common delta event:
                    #   {"type":"response.output_text.delta","delta":"..."}
                    if isinstance(event, dict):
                        et = event.get("type")
                        if et == "response.created":
                            resp = event.get("response") or {}
                            if isinstance(resp, dict):
                                yield {"id": resp.get("id"), "model": resp.get("model")}
                            continue
                        if et == "response.output_text.delta" and isinstance(event.get("delta"), str):
                            delta_text = event["delta"]
                            yield {"choices": [{"delta": {"content": delta_text}}]}
                            continue
                        if et == "response.completed":
                            # If usage is present on completed, pass it through for token stats.
                            resp = event.get("response") or {}
                            if isinstance(resp, dict):
                                usage_obj = _responses_usage_to_chat_usage(resp)
                                if usage_obj:
                                    yield {"usage": usage_obj}
                            finish_reason = "stop"
                            continue

            if finish_reason != "tool_calls":
                return
            raise RuntimeError("Tool calls are not supported in streaming mode for /v1/responses yet")
