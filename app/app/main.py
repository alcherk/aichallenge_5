import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from .config import get_settings
from .schemas import ChatRequest, ChatResponse, ErrorResponse
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
    response_model=ChatResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        return await call_chatgpt(request)
    except httpx.HTTPStatusError as e:
        # Avoid leaking full upstream error details
        raise HTTPException(status_code=e.response.status_code, detail="Upstream API error")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected server error")
