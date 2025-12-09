import httpx
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from .config import get_settings
from .schemas import ChatRequest, ChatResponse, StructuredResponse
from .services.chatgpt_client import call_chatgpt


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
