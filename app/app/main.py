import httpx
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
import json

from .config import get_settings
from .schemas import ChatRequest, ChatResponse, StructuredResponse
from .services.chatgpt_client import call_chatgpt, stream_chatgpt


settings = get_settings()
app = FastAPI(title="ChatGPT Proxy Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/app/static"), name="static")
templates = Jinja2Templates(directory="app/app/templates")


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    # Add cache-busting timestamp to prevent CSS/JS caching
    import time
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

    def sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    async def event_generator():
        assistant_text_parts: list[str] = []
        upstream_id: str | None = None
        upstream_model: str | None = request.model or settings.openai_model
        upstream_finish_reason: str | None = None
        token_usage: dict | None = None

        try:
            async for chunk in stream_chatgpt(request):
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
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            error_detail = f"ChatGPT API returned status {status_code}"
            try:
                error_data = e.response.json()
                if "error" in error_data and "message" in error_data["error"]:
                    error_detail = error_data["error"]["message"]
            except Exception:
                pass

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
                    },
                    "metadata": {
                        "timestamp": time.time(),
                        "request_id": request_id,
                        "processing_time_ms": round((time.time() - start_time) * 1000, 2),
                    },
                },
            )
        except RuntimeError as e:
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
    
    try:
        chat_response = await call_chatgpt(request)
        
        # Assistant response is now plain text/markdown - no JSON formatting needed
        
        # Extract token usage information
        token_usage = None
        if chat_response.usage:
            token_usage = {
                "prompt_tokens": chat_response.usage.prompt_tokens,
                "completion_tokens": chat_response.usage.completion_tokens,
                "total_tokens": chat_response.usage.total_tokens,
            }
        
        return StructuredResponse(
            success=True,
            status_code=200,
            message="Chat completion successful",
            data=chat_response,
            error=None,
            metadata={
                "timestamp": time.time(),
                "request_id": request_id,
                "model": chat_response.model,
                "processing_time_ms": round((time.time() - start_time) * 1000, 2),
                "token_usage": token_usage,
            },
        )
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        # Try to extract detailed error message
        error_detail = f"ChatGPT API returned status {status_code}"
        try:
            error_data = e.response.json()
            if "error" in error_data and "message" in error_data["error"]:
                error_detail = error_data["error"]["message"]
        except Exception:
            pass
        
        return StructuredResponse(
            success=False,
            status_code=status_code,
            message="Upstream API error",
            data=None,
            error={
                "type": "HTTPStatusError",
                "detail": error_detail,
                "status_code": status_code,
            },
            metadata={
                "timestamp": time.time(),
                "request_id": request_id,
                "processing_time_ms": round((time.time() - start_time) * 1000, 2),
            },
        )
    except RuntimeError as e:
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
