import httpx
import time
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
from .schemas import ChatRequest, ChatResponse, StructuredResponse
from .services.chatgpt_client import call_chatgpt, stream_chatgpt
from .mcp.manager import init_mcp_manager
from .mcp.manager import ensure_mcp_manager, get_mcp_manager


settings = get_settings()
_level = getattr(logging, str(getattr(settings, "log_level", "INFO")).upper(), logging.INFO)
logging.basicConfig(level=_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
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
    - event: chunk, data: {"delta": "..."}
    - event: done, data: StructuredResponse-like JSON
    - event: error, data: StructuredResponse-like JSON
    """
    start_time = time.time()
    request_id = getattr(http_request.state, "request_id", None)
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
        assistant_text_parts: list[str] = []
        upstream_id: Optional[str] = None
        upstream_model: Optional[str] = request.model or settings.openai_model
        upstream_finish_reason: Optional[str] = None
        token_usage: Optional[dict] = None
        chunk_count = 0

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

    return StreamingResponse(
        event_generator(),
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
        "chat request received request_id=%s model=%s messages=%d",
        request_id,
        request.model or settings.openai_model,
        len(request.messages or []),
    )
    
    try:
        chat_response, rag_metadata = await call_chatgpt(request)
        
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
