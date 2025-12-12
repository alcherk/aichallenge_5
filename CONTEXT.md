## Architecture and Design Context

### High-level architecture
- **Service**: FastAPI web service exposing:
  - `GET /health` for health checks.
  - `GET /` serving a single-page web UI for chat.
  - `POST /api/chat` as a proxy endpoint to the ChatGPT API.
  - `POST /api/chat/stream` as an SSE streaming proxy endpoint for incremental UI updates.
- **UI**: Lightweight single-page chat client implemented with vanilla HTML/CSS/JS.
  - Renders the conversation in the browser.
  - Maintains message history client-side and persists it between page reloads using `localStorage`.
  - Includes a “New Chat” button to clear local session chat history.
- **Proxy**: Backend wrapper around the ChatGPT API using `httpx`.
  - Reads API key and model from environment variables.
  - Sends `messages[]` to the `/chat/completions` endpoint.
  - Supports both non-streaming and streaming (token-by-token) responses.

### Key modules
- `app/app/config.py`
  - `Settings` for configuration (lightweight env-var reader).
  - Reads from environment: `OPENAI_API_KEY`, `OPENAI_API_BASE`, `OPENAI_MODEL`, `REQUEST_TIMEOUT_SECONDS`, `APP_HOST`, `APP_PORT`.
  - `get_settings()` is cached with `lru_cache` to avoid repeated parsing.
- `app/app/schemas.py`
  - `ChatMessage`, `ChatRequest`, `ChatChoice`, `ChatUsage`, `ChatResponse`, `ErrorResponse`.
  - Models mirror the typical Chat Completions response shape.
- `app/app/services/chatgpt_client.py`
  - `call_chatgpt(ChatRequest) -> ChatResponse` for non-streaming calls.
  - `stream_chatgpt(ChatRequest)` yields streaming chunk dicts from upstream.
  - Builds JSON body from the request + defaults from `Settings`.
  - Uses `httpx.AsyncClient` with configured timeout.
  - Raises if API key is missing, propagates HTTP errors for the route to map.
- `app/app/main.py`
  - Creates FastAPI app, configures CORS, static files, and templates.
  - `GET /` renders `templates/chat.html`.
  - `POST /api/chat` returns a structured JSON envelope (`StructuredResponse`).
  - `POST /api/chat/stream` streams SSE events:
    - `chunk`: `{"delta": "..."}` (incremental assistant text)
    - `done`: final structured payload including token usage (when available)
    - `error`: structured error payload

### Configuration and environment
- **Required for production**:
  - `OPENAI_API_KEY` – your ChatGPT/OpenAI API key.
- **Optional**:
  - `OPENAI_MODEL` (default: `gpt-4o-mini` in `app/app/config.py`).
  - `OPENAI_API_BASE` (default: `https://api.openai.com/v1`).
  - `REQUEST_TIMEOUT_SECONDS` (default: `60`).
  - `APP_HOST` (default: `0.0.0.0`).
  - `APP_PORT` (default: `8333`).

### Port and networking
- Internally, the service is configured to listen on port **8333** via Uvicorn.
- Docker exposes and maps this port so the VPS can serve traffic at `:8333`.
- You can use a reverse proxy (nginx, Caddy, Traefik) in front if needed later.

### Extensibility notes
- **Server-side conversation history**
  - Currently, history is persisted in the browser via `localStorage` (no server-side storage).
  - To add server-side persistence, you can:
    - Introduce an identifier for a conversation (e.g., `conversation_id`).
    - Store messages in a database (e.g., Postgres, SQLite) keyed by user/session.
    - Modify `/api/chat` to load and store past messages.
- **User accounts / auth**
  - The UI and API are currently open and unauthenticated.
  - To add auth later:
    - Wrap the FastAPI app with auth dependencies (e.g., OAuth2, JWT, session cookies).
    - Restrict `/api/chat` and `/` to authenticated users.
- **Advanced model options**
  - `ChatRequest` already supports `model`, `temperature`, and `max_tokens`.
  - The UI currently only sends `messages`; you can extend `chat.js` to expose
    sliders or inputs for these fields and include them in the JSON body.
- **Streaming responses**
  - Implemented via SSE at `POST /api/chat/stream`.
  - The UI reads the response stream and updates the assistant bubble continuously as chunks arrive.

### Deployment assumptions
- Target: a VPS with Docker installed.
- You control:
  - Environment variables for the container.
  - Port mappings (host `8333` -> container `8333`).
- TLS/HTTPS can be terminated either on the VPS (reverse proxy) or upstream.
