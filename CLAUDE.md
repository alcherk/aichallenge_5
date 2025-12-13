# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A FastAPI-based ChatGPT proxy service with a web UI that runs in Docker on port 8333. The service forwards chat requests to the OpenAI API and provides both streaming (SSE) and non-streaming endpoints.

## Development Commands

### Local Development (without Docker)

```bash
# Setup virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt

# Set required environment variables
export OPENAI_API_KEY="your-api-key-here"
export OPENAI_MODEL="gpt-4o-mini"  # optional

# Run the development server
uvicorn app.app.main:app --host 0.0.0.0 --port 8333 --reload
```

### Docker Development

```bash
# Build the image
docker build -t chatgpt-proxy .

# Run the container
docker run -d \
  --name chatgpt-proxy \
  -e OPENAI_API_KEY="your-api-key-here" \
  -e OPENAI_MODEL="gpt-4o-mini" \
  -p 8333:8333 \
  chatgpt-proxy

# Or use docker-compose
export OPENAI_API_KEY="your-api-key-here"
docker compose up -d --build
```

## Architecture

### Request Flow

1. **Non-streaming**: `POST /api/chat` -> `call_chatgpt()` -> Returns complete `StructuredResponse`
2. **Streaming**: `POST /api/chat/stream` -> `stream_chatgpt()` -> Returns SSE events (chunk/done/error)

### Key Components

- **app/app/main.py**: FastAPI application with three main endpoints:
  - `GET /health`: Health check
  - `GET /`: Serves the web UI (chat.html)
  - `POST /api/chat`: Non-streaming chat completions (returns StructuredResponse)
  - `POST /api/chat/stream`: SSE streaming endpoint for incremental responses

- **app/app/services/chatgpt_client.py**: OpenAI API integration
  - `call_chatgpt()`: Non-streaming requests using httpx.AsyncClient
  - `stream_chatgpt()`: Streaming generator that yields JSON chunks from SSE stream
  - Both functions inject a Russian system prompt if none is present in the messages

- **app/app/config.py**: Environment-based configuration using a lightweight Settings class (not pydantic-settings)
  - Cached with `@lru_cache()` to avoid repeated parsing

- **app/app/schemas.py**: Pydantic models
  - `ChatMessage`, `ChatRequest`, `ChatResponse`, `ChatChoice`, `ChatUsage`
  - `StructuredResponse`: Consistent envelope for API responses with success/error handling

- **Frontend (app/app/static/ and app/app/templates/)**:
  - `chat.html`: Single-page UI with Jinja2 templating
  - `chat.js`: Vanilla JS for message handling, uses EventSource for SSE streaming
  - `styles.css`: Chat UI styling
  - Conversation history stored in browser localStorage

### System Prompt Injection

Both `call_chatgpt()` and `stream_chatgpt()` automatically inject a Russian-language system prompt if no system message is present in the request. The prompt instructs the assistant to understand tasks first, ask clarifying questions, and respond in Markdown format.

### Environment Variables

Required:
- `OPENAI_API_KEY`: Your OpenAI API key

Optional:
- `OPENAI_MODEL` (default: "gpt-4o-mini")
- `OPENAI_API_BASE` (default: "https://api.openai.com/v1")
- `REQUEST_TIMEOUT_SECONDS` (default: 60)
- `APP_HOST` (default: "0.0.0.0")
- `APP_PORT` (default: 8333)

### Error Handling

All endpoints return consistent structured responses via `StructuredResponse`:
- Success: `success=True`, `data=ChatResponse`, `metadata` includes processing time and token usage
- Failure: `success=False`, `error` dict with type and detail, HTTP status preserved

The streaming endpoint emits SSE events:
- `event: chunk` with `{"delta": "..."}` for incremental text
- `event: done` with full StructuredResponse-like payload
- `event: error` with error details

### CORS and Static Files

- CORS enabled for all origins (`allow_origins=["*"]`)
- Static files mounted at `/static` (serves from `app/app/static/`)
- Templates loaded from `app/app/templates/`
- Cache-busting via timestamp query parameter in template rendering

## Important Implementation Notes

### Adding Features

- Conversation history is currently client-side only (localStorage). To add server-side persistence, introduce a conversation_id and database storage in `/api/chat` endpoint.
- Authentication is not implemented. To add auth, wrap routes with FastAPI dependencies (OAuth2, JWT, or session-based).
- The UI only sends `messages` to the backend. To expose additional parameters (temperature, max_tokens), extend the form in chat.js.

### Modifying the System Prompt

System prompts are injected in two places:
- `app/app/services/chatgpt_client.py:30-43` (non-streaming)
- `app/app/services/chatgpt_client.py:103-117` (streaming)

If you modify the prompt, update both locations to maintain consistency.

### Working with Static Assets

Static files (chat.js, styles.css) are served from `app/app/static/`. The FastAPI app uses `StaticFiles` to mount this directory at `/static`, so updates to CSS/JS files require a server restart when running with `--reload` or a browser cache clear.

### Docker Deployment

The Dockerfile uses Python 3.11-slim and exposes port 8333. The CMD runs Uvicorn directly without `--reload`. For VPS deployment, use `--restart unless-stopped` to ensure the container restarts after crashes or reboots.
