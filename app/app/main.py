import asyncio
import httpx
import time
import uuid
from pathlib import Path
from typing import Optional
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
import json

from .config import get_settings
from .schemas import ChatRequest, ChatResponse, ChatChoice, ChatMessage, ChatUsage, StructuredResponse, CancelRequest, CancelResponse
from .services.chatgpt_client import call_chatgpt, stream_chatgpt
from .services.provider_router import get_provider_router, ProviderResponse, StreamChunk
from .mcp.manager import init_mcp_manager
from .mcp.manager import ensure_mcp_manager, get_mcp_manager


settings = get_settings()
_level = getattr(logging, str(getattr(settings, "log_level", "INFO")).upper(), logging.INFO)

# Track active streaming generations for cancellation support
active_generations: dict[str, asyncio.Task] = {}

# Configure logging to ensure output to console even under uvicorn
logging.basicConfig(
    level=_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    force=True,  # Override any existing configuration
)

# Explicitly set level for our app loggers to ensure they output
for logger_name in ["app", "app.tasks", "app.rag", "app.mcp"]:
    logging.getLogger(logger_name).setLevel(_level)

logger = logging.getLogger("app")
app = FastAPI(title="ChatGPT Proxy Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Check if frontend build exists
frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
use_react_frontend = frontend_dist.exists() and frontend_dist.is_dir()

if use_react_frontend:
    # Serve React frontend in production
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")
else:
    # Serve legacy frontend in development
    app.mount("/static", StaticFiles(directory="app/app/static"), name="static")
    templates = Jinja2Templates(directory="app/app/templates")


@app.on_event("startup")
async def startup() -> None:
    """
    Optional MCP initialization.

    When MCP is disabled (default), this is a no-op.
    """
    try:
        mgr = init_mcp_manager(
            mcp_config_path=settings.mcp_config_path or None,
            workspace_root=Path(settings.workspace_root),
        )
        if mgr is not None:
            await mgr.connect()
            logger.info("[MCP] connected")
    except Exception as e:
        # Non-fatal: app should still function as a plain OpenAI proxy.
        logger.warning("[MCP] disabled due to startup error: %s", e)


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}


@app.get("/api/ollama/health")
async def ollama_health():
    """Check Ollama availability and list models."""
    from .services.ollama_client import get_ollama_client

    client = get_ollama_client()
    status = await client.health_check()

    return {
        "available": status.available,
        "models": status.models,
        "default_model": settings.ollama_default_model,
        "default_loaded": settings.ollama_default_model in status.models,
        "error": status.error
    }


@app.get("/api/ollama/models")
async def ollama_models():
    """List available Ollama models with details."""
    from .services.ollama_client import get_ollama_client

    client = get_ollama_client()

    try:
        models = await client.list_models()
        return {
            "models": [
                {
                    "name": m.name,
                    "size": m.size,
                    "modified_at": m.modified_at,
                }
                for m in models
            ]
        }
    except Exception as e:
        logger.warning("Failed to list Ollama models: %s", e)
        return {
            "models": [],
            "error": str(e)
        }


@app.get("/api/ollama/model/{model_name}")
async def ollama_model_info(model_name: str):
    """
    Get detailed model information including context limits.

    Returns model info for optimization parameters UI.
    """
    from .services.ollama_client import get_ollama_client
    from .schemas import ModelInfo

    client = get_ollama_client()

    try:
        info = await client.get_model_info(model_name)
        return ModelInfo(
            name=info["name"],
            context_length=info["context_length"],
            default_num_ctx=info["default_num_ctx"],
            size_bytes=info.get("size"),
            modified_at=info.get("modified_at"),
            parameters=info.get("details"),
        )
    except Exception as e:
        logger.warning("Failed to get model info for %s: %s", model_name, e)
        # Return defaults on error
        return ModelInfo(
            name=model_name,
            context_length=4096,
            default_num_ctx=4096,
        )


@app.get("/api/prompt-templates")
async def get_prompt_templates():
    """
    Get prompt templates and category defaults for optimization.

    Returns templates, category defaults, and category info for the UI.
    """
    from .services.prompt_templates import (
        DEFAULT_TEMPLATES,
        CATEGORY_DEFAULTS,
        CATEGORY_INFO,
    )

    return {
        "templates": DEFAULT_TEMPLATES,
        "defaults": CATEGORY_DEFAULTS,
        "categories": CATEGORY_INFO,
    }


@app.get("/api/mcp/status")
async def mcp_status(
    enabled: Optional[bool] = None,
    mcp_config_path: Optional[str] = None,
    workspace_root: Optional[str] = None,
) -> dict:
    """
    Return MCP status + discovered tools for the UI.

    If MCP isn't initialized yet, optional query params can trigger initialization.
    """
    try:
        if get_mcp_manager() is None:
            mcp_enabled = bool(enabled) if enabled is not None else bool(
                mcp_config_path or settings.mcp_config_path
            )
            await ensure_mcp_manager(
                mcp_config_path=(
                    (mcp_config_path or settings.mcp_config_path or None) if mcp_enabled else None
                ),
                workspace_root=Path(workspace_root or settings.workspace_root),
            )
        mgr = get_mcp_manager()
        if mgr is None:
            return {"enabled": False, "servers": [], "tools": []}
        return mgr.status()
    except Exception as e:
        return {
            "enabled": False,
            "servers": [],
            "tools": [],
            "error": {"type": type(e).__name__, "detail": str(e)},
        }


@app.post("/api/chat/cancel", response_model=CancelResponse)
async def cancel_generation(request: CancelRequest) -> CancelResponse:
    """
    Cancel an in-progress streaming generation.

    This endpoint allows clients to abort a streaming chat request that is
    still in progress. The request_id must match the one returned in the
    streaming response metadata.
    """
    request_id = request.request_id
    logger.debug("cancel request received request_id=%s", request_id)

    if request_id in active_generations:
        task = active_generations[request_id]
        task.cancel()
        # Remove from tracking dict
        del active_generations[request_id]
        logger.info("generation cancelled request_id=%s", request_id)
        return CancelResponse(success=True, message="Generation cancelled")

    logger.debug("cancel request not found request_id=%s", request_id)
    return CancelResponse(success=False, message="No active generation found")


if use_react_frontend:
    @app.get("/{full_path:path}", response_class=HTMLResponse)
    async def serve_react_app(full_path: str):
        """Serve React app for all non-API routes"""
        # Serve index.html for all routes (React Router handles routing)
        index_file = frontend_dist / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return HTMLResponse(content="<h1>Frontend not found</h1>", status_code=404)
else:
    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        # Add cache-busting timestamp to prevent CSS/JS caching
        cache_bust = int(time.time())
        return templates.TemplateResponse("chat.html", {"request": request, "cache_bust": cache_bust})


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest, http_request: Request) -> StreamingResponse:
    """
    Streams assistant text as Server-Sent Events (SSE) so the UI can render
    tokens incrementally. Events:
    - event: start, data: {"request_id": "..."} (for cancellation support)
    - event: chunk, data: {"delta": "..."}
    - event: done, data: StructuredResponse-like JSON
    - event: error, data: StructuredResponse-like JSON
    """
    start_time = time.time()
    # Generate a unique request_id for this stream (for cancellation support)
    request_id = getattr(http_request.state, "request_id", None) or str(uuid.uuid4())
    logger.debug(
        "stream request received request_id=%s model=%s messages=%d",
        request_id,
        request.model or settings.openai_model,
        len(request.messages or []),
    )

    def sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    def _extract_upstream_error(response: httpx.Response) -> dict:
        """
        Extract as much upstream error detail as possible for copy/paste debugging.
        This intentionally avoids including request headers (which may include secrets).
        """
        raw_text: str = ""
        try:
            raw_text = (response.text or "").strip()
        except Exception:
            raw_text = ""

        raw_json = None
        try:
            raw_json = response.json()
        except Exception:
            raw_json = None

        # Prefer the standard OpenAI error message if present, else fall back to raw text.
        error_message = None
        if isinstance(raw_json, dict):
            err = raw_json.get("error")
            if isinstance(err, dict):
                error_message = err.get("message") or error_message
        error_message = error_message or raw_text or f"Upstream returned HTTP {response.status_code}"

        # Include a small, safe subset of headers (useful for proxies/CDNs).
        safe_headers = {}
        for k in ("content-type", "x-request-id", "cf-ray", "x-amzn-requestid"):
            v = response.headers.get(k)
            if v:
                safe_headers[k] = v

        return {
            "status_code": response.status_code,
            "message": error_message,
            "headers": safe_headers,
            "body_json": raw_json,
            "body_text": raw_text,
        }

    async def event_generator():
        # Emit start event with request_id for cancellation support
        yield sse("start", {"request_id": request_id})

        assistant_text_parts: list[str] = []
        upstream_id: Optional[str] = None
        upstream_model: Optional[str] = request.model or settings.openai_model
        upstream_finish_reason: Optional[str] = None
        token_usage: Optional[dict] = None
        chunk_count = 0

        # === LOCAL PROVIDER PATH ===
        if request.provider == "local":
            try:
                router = get_provider_router()
                # Convert ChatRequest messages to dict format for router
                messages_dict = [
                    {"role": m.role, "content": m.content}
                    for m in request.messages
                ]

                logger.debug(
                    "stream local begin request_id=%s model=%s messages=%d",
                    request_id,
                    request.model,
                    len(messages_dict),
                )

                async for stream_chunk in router.stream_chat(
                    messages=messages_dict,
                    provider="local",
                    model=request.model,
                    temperature=request.temperature or 0.7,
                    max_tokens=request.max_tokens,
                    top_p=request.top_p,
                ):
                    chunk_count += 1
                    upstream_model = stream_chunk.model or upstream_model

                    if stream_chunk.done:
                        upstream_finish_reason = "stop"
                        continue

                    if stream_chunk.delta:
                        assistant_text_parts.append(stream_chunk.delta)
                        yield sse("chunk", {"delta": stream_chunk.delta})
                        if chunk_count == 1 or chunk_count % 25 == 0:
                            logger.debug(
                                "stream local chunk request_id=%s chunk_count=%d delta_len=%d",
                                request_id,
                                chunk_count,
                                len(stream_chunk.delta),
                            )

                full_text = "".join(assistant_text_parts)
                chat_response = {
                    "id": f"local-{request_id or 'stream'}",
                    "model": upstream_model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": full_text},
                            "finish_reason": upstream_finish_reason,
                        }
                    ],
                    "usage": None,  # Local provider doesn't track token usage in streaming
                    "provider": "local",
                }

                structured = {
                    "success": True,
                    "status_code": 200,
                    "message": "Chat completion successful",
                    "data": chat_response,
                    "error": None,
                    "metadata": {
                        "timestamp": time.time(),
                        "request_id": request_id,
                        "model": upstream_model,
                        "provider": "local",
                        "processing_time_ms": round((time.time() - start_time) * 1000, 2),
                        "token_usage": None,
                    },
                }
                yield sse("done", structured)
                logger.info(
                    "stream local done request_id=%s model=%s chunks=%d time_ms=%.2f",
                    request_id,
                    upstream_model,
                    chunk_count,
                    (time.time() - start_time) * 1000.0,
                )
                return  # Exit generator after local path completes

            except Exception as e:
                logger.exception("stream local error request_id=%s", request_id)
                yield sse(
                    "error",
                    {
                        "success": False,
                        "status_code": 500,
                        "message": "Local provider error",
                        "data": None,
                        "error": {"type": type(e).__name__, "detail": str(e)},
                        "metadata": {
                            "timestamp": time.time(),
                            "request_id": request_id,
                            "provider": "local",
                            "processing_time_ms": round((time.time() - start_time) * 1000, 2),
                        },
                    },
                )
                return  # Exit generator after error

        # === CLOUD PROVIDER PATH (existing code, unchanged) ===
        try:
            logger.debug(
                "stream upstream begin request_id=%s api_base=%s model=%s",
                request_id,
                settings.openai_api_base,
                upstream_model,
            )
            async for chunk in stream_chatgpt(request):
                chunk_count += 1
                upstream_id = upstream_id or chunk.get("id")
                upstream_model = chunk.get("model") or upstream_model

                choices = chunk.get("choices") or []
                if choices:
                    choice0 = choices[0] or {}
                    delta = (choice0.get("delta") or {}).get("content")
                    upstream_finish_reason = choice0.get("finish_reason") or upstream_finish_reason
                    if delta:
                        assistant_text_parts.append(delta)
                        yield sse("chunk", {"delta": delta})
                        if chunk_count == 1 or chunk_count % 25 == 0:
                            logger.debug(
                                "stream chunk request_id=%s chunk_count=%d delta_len=%d",
                                request_id,
                                chunk_count,
                                len(delta),
                            )

                usage = chunk.get("usage")
                if usage:
                    token_usage = usage

            full_text = "".join(assistant_text_parts)
            chat_response = {
                "id": upstream_id or "stream",
                "model": upstream_model or (request.model or settings.openai_model),
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": full_text},
                        "finish_reason": upstream_finish_reason,
                    }
                ],
                "usage": token_usage,
                "provider": "cloud",
            }

            structured = {
                "success": True,
                "status_code": 200,
                "message": "Chat completion successful",
                "data": chat_response,
                "error": None,
                "metadata": {
                    "timestamp": time.time(),
                    "request_id": request_id,
                    "model": chat_response["model"],
                    "provider": "cloud",
                    "processing_time_ms": round((time.time() - start_time) * 1000, 2),
                    "token_usage": token_usage,
                },
            }
            yield sse("done", structured)
            logger.info(
                "stream done request_id=%s model=%s chunks=%d time_ms=%.2f",
                request_id,
                upstream_model,
                chunk_count,
                (time.time() - start_time) * 1000.0,
            )
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            upstream = _extract_upstream_error(e.response)
            error_detail = upstream.get("message") or f"ChatGPT API returned status {status_code}"
            logger.error(
                "stream upstream error request_id=%s status=%s message=%s upstream=%s",
                request_id,
                status_code,
                error_detail,
                upstream,
            )

            yield sse(
                "error",
                {
                    "success": False,
                    "status_code": status_code,
                    "message": "Upstream API error",
                    "data": None,
                    "error": {
                        "type": "HTTPStatusError",
                        "detail": error_detail,
                        "status_code": status_code,
                        "upstream": upstream,
                    },
                    "metadata": {
                        "timestamp": time.time(),
                        "request_id": request_id,
                        "processing_time_ms": round((time.time() - start_time) * 1000, 2),
                    },
                },
            )
        except RuntimeError as e:
            logger.error("stream runtime error request_id=%s error=%s", request_id, e)
            yield sse(
                "error",
                {
                    "success": False,
                    "status_code": 500,
                    "message": "Configuration error",
                    "data": None,
                    "error": {"type": "RuntimeError", "detail": str(e)},
                    "metadata": {
                        "timestamp": time.time(),
                        "request_id": request_id,
                        "processing_time_ms": round((time.time() - start_time) * 1000, 2),
                    },
                },
            )
        except Exception as e:
            logger.exception("stream unexpected error request_id=%s", request_id)
            yield sse(
                "error",
                {
                    "success": False,
                    "status_code": 500,
                    "message": "Unexpected server error",
                    "data": None,
                    "error": {"type": type(e).__name__, "detail": str(e)},
                    "metadata": {
                        "timestamp": time.time(),
                        "request_id": request_id,
                        "processing_time_ms": round((time.time() - start_time) * 1000, 2),
                    },
                },
            )

    async def tracked_event_generator():
        """
        Wrapper generator that tracks the streaming task in active_generations
        for cancellation support, and ensures proper cleanup.
        """
        # Register this generation as active
        # Note: We create a placeholder task entry. The actual task is managed by
        # the ASGI server, but we use this dict to signal cancellation intent.
        # When cancelled, asyncio.CancelledError will be raised in the generator.
        active_generations[request_id] = asyncio.current_task()
        logger.debug("registered active generation request_id=%s", request_id)

        try:
            async for event in event_generator():
                yield event
        except asyncio.CancelledError:
            # Generation was cancelled via /api/chat/cancel
            logger.info("generation cancelled by client request_id=%s", request_id)
            yield sse("cancelled", {
                "success": True,
                "message": "Generation cancelled by client",
                "request_id": request_id,
            })
            raise  # Re-raise to properly clean up the async generator
        finally:
            # Always clean up from active_generations
            active_generations.pop(request_id, None)
            logger.debug("cleaned up active generation request_id=%s", request_id)

    return StreamingResponse(
        tracked_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post(
    "/api/chat",
    response_model=StructuredResponse,
)
async def chat(request: ChatRequest, http_request: Request) -> StructuredResponse:
    """
    Chat endpoint that always returns a structured response for tool chaining.
    
    Request body can include:
    - messages: List of chat messages
    - model: Optional model name (defaults to configured model)
    - temperature: Optional temperature (default: 0.7)
    - max_tokens: Optional max tokens
    - json_schema: Optional JSON schema for structured output
    
    When json_schema is provided, the LLM will return responses conforming to that schema.
    
    Response format:
    {
        "success": bool,
        "status_code": int,
        "message": str,
        "data": ChatResponse | null,
        "error": { "type": str, "detail": str } | null,
        "metadata": { "timestamp": float, "model": str } | null
    }
    """
    start_time = time.time()
    request_id = getattr(http_request.state, "request_id", None)
    logger.debug(
        "chat request received request_id=%s model=%s messages=%d provider=%s",
        request_id,
        request.model or settings.openai_model,
        len(request.messages or []),
        request.provider,
    )

    # === LOCAL PROVIDER PATH ===
    if request.provider == "local":
        try:
            router = get_provider_router()
            # Convert ChatRequest messages to dict format for router
            messages_dict = [
                {"role": m.role, "content": m.content}
                for m in request.messages
            ]

            logger.debug(
                "chat local begin request_id=%s model=%s messages=%d",
                request_id,
                request.model,
                len(messages_dict),
            )

            provider_response: ProviderResponse = await router.chat(
                messages=messages_dict,
                provider="local",
                model=request.model,
                temperature=request.temperature or 0.7,
                max_tokens=request.max_tokens,
                top_p=request.top_p,
            )

            # Convert ProviderResponse to ChatResponse format
            chat_response = ChatResponse(
                id=f"local-{request_id or 'chat'}",
                model=provider_response.model,
                choices=[
                    ChatChoice(
                        index=0,
                        message=ChatMessage(role="assistant", content=provider_response.content),
                        finish_reason="stop",
                    )
                ],
                usage=ChatUsage(
                    prompt_tokens=0,  # Not tracked by Ollama in non-streaming
                    completion_tokens=provider_response.tokens_used or 0,
                    total_tokens=provider_response.tokens_used or 0,
                ) if provider_response.tokens_used else None,
                provider="local",
            )

            # Build metadata dict
            metadata_dict = {
                "timestamp": time.time(),
                "request_id": request_id,
                "model": provider_response.model,
                "provider": "local",
                "processing_time_ms": round((time.time() - start_time) * 1000, 2),
                "inference_time_ms": provider_response.inference_time_ms,
                "token_usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": provider_response.tokens_used or 0,
                    "total_tokens": provider_response.tokens_used or 0,
                } if provider_response.tokens_used else None,
            }

            logger.info(
                "chat local done request_id=%s model=%s tokens=%s time_ms=%.2f",
                request_id,
                provider_response.model,
                provider_response.tokens_used,
                (time.time() - start_time) * 1000.0,
            )

            return StructuredResponse(
                success=True,
                status_code=200,
                message="Chat completion successful",
                data=chat_response,
                error=None,
                metadata=metadata_dict,
            )

        except Exception as e:
            logger.exception("chat local error request_id=%s", request_id)
            return StructuredResponse(
                success=False,
                status_code=500,
                message="Local provider error",
                data=None,
                error={
                    "type": type(e).__name__,
                    "detail": str(e),
                },
                metadata={
                    "timestamp": time.time(),
                    "request_id": request_id,
                    "provider": "local",
                    "processing_time_ms": round((time.time() - start_time) * 1000, 2),
                },
            )

    # === CLOUD PROVIDER PATH (existing code, unchanged) ===
    try:
        chat_response, rag_metadata = await call_chatgpt(request)

        # Set provider on response
        chat_response.provider = "cloud"

        # Assistant response is now plain text/markdown - no JSON formatting needed

        # Extract token usage information
        token_usage = None
        if chat_response.usage:
            token_usage = {
                "prompt_tokens": chat_response.usage.prompt_tokens,
                "completion_tokens": chat_response.usage.completion_tokens,
                "total_tokens": chat_response.usage.total_tokens,
            }

        # Build metadata dict
        metadata_dict = {
            "timestamp": time.time(),
            "request_id": request_id,
            "model": chat_response.model,
            "provider": "cloud",
            "processing_time_ms": round((time.time() - start_time) * 1000, 2),
            "token_usage": token_usage,
        }

        # Add RAG metadata if available
        if rag_metadata:
            metadata_dict["rag"] = rag_metadata

        return StructuredResponse(
            success=True,
            status_code=200,
            message="Chat completion successful",
            data=chat_response,
            error=None,
            metadata=metadata_dict,
        )
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        upstream = {
            "status_code": status_code,
            "headers": {},
            "body_json": None,
            "body_text": "",
        }
        # Reuse the stream helper logic here (kept inline to avoid extra imports).
        try:
            raw_text = (e.response.text or "").strip()
        except Exception:
            raw_text = ""
        try:
            raw_json = e.response.json()
        except Exception:
            raw_json = None
        safe_headers = {}
        for k in ("content-type", "x-request-id", "cf-ray", "x-amzn-requestid"):
            v = e.response.headers.get(k)
            if v:
                safe_headers[k] = v
        upstream = {
            "status_code": status_code,
            "headers": safe_headers,
            "body_json": raw_json,
            "body_text": raw_text,
        }
        error_detail = None
        if isinstance(raw_json, dict):
            err = raw_json.get("error")
            if isinstance(err, dict):
                error_detail = err.get("message") or error_detail
        error_detail = error_detail or raw_text or f"ChatGPT API returned status {status_code}"
        logger.error(
            "chat upstream error request_id=%s status=%s message=%s upstream=%s",
            request_id,
            status_code,
            error_detail,
            upstream,
        )
        
        return StructuredResponse(
            success=False,
            status_code=status_code,
            message="Upstream API error",
            data=None,
            error={
                "type": "HTTPStatusError",
                "detail": error_detail,
                "status_code": status_code,
                "upstream": upstream,
            },
            metadata={
                "timestamp": time.time(),
                "request_id": request_id,
                "processing_time_ms": round((time.time() - start_time) * 1000, 2),
            },
        )
    except RuntimeError as e:
        logger.error("chat runtime error request_id=%s error=%s", request_id, e)
        return StructuredResponse(
            success=False,
            status_code=500,
            message="Configuration error",
            data=None,
            error={
                "type": "RuntimeError",
                "detail": str(e),
            },
            metadata={
                "timestamp": time.time(),
                "request_id": request_id,
                "processing_time_ms": round((time.time() - start_time) * 1000, 2),
            },
        )
    except Exception as e:
        logger.exception("chat unexpected error request_id=%s", request_id)
        return StructuredResponse(
            success=False,
            status_code=500,
            message="Unexpected server error",
            data=None,
            error={
                "type": type(e).__name__,
                "detail": str(e),
            },
            metadata={
                "timestamp": time.time(),
                "request_id": request_id,
                "processing_time_ms": round((time.time() - start_time) * 1000, 2),
            },
        )
