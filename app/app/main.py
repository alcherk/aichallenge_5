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
    return templates.TemplateResponse("chat.html", {"request": request})


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
        
        # Format the assistant's response content as JSON
        # Since we use response_format with json_schema, OpenAI returns JSON in content
        import json
        if chat_response.choices and len(chat_response.choices) > 0:
            assistant_content = chat_response.choices[0].message.content
            
            # Parse the JSON response from OpenAI (it should match our schema)
            try:
                parsed_content = json.loads(assistant_content)
                # Format as pretty JSON string
                formatted_content = json.dumps(parsed_content, indent=2, ensure_ascii=False)
            except (json.JSONDecodeError, ValueError):
                # If parsing fails, wrap it in a JSON structure
                formatted_content = json.dumps({
                    "role": "assistant",
                    "content": assistant_content,
                    "metadata": {}
                }, indent=2, ensure_ascii=False)
            
            # Update the content with formatted JSON
            chat_response.choices[0].message.content = formatted_content
        
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
