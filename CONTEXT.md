## Architecture and Design Context

### High-level architecture
- **Service**: FastAPI web service exposing:
  - `GET /health` for health checks.
  - `GET /` serving a single-page web UI for chat.
  - `POST /api/chat` as a proxy endpoint to the ChatGPT API.
- **UI**: Lightweight single-page chat client implemented with vanilla HTML/CSS/JS.
  - Renders the conversation in the browser.
  - Maintains message history client-side only (no server persistence yet).
- **Proxy**: Backend wrapper around the ChatGPT API using `httpx`.
  - Reads API key and model from environment variables.
  - Sends `messages[]` to the `/chat/completions` endpoint.

### Key modules
- `app/config.py`
  - `Settings` (Pydantic `BaseSettings`) for configuration.
  - Reads from environment: `OPENAI_API_KEY`, `OPENAI_API_BASE`, `OPENAI_MODEL`, `REQUEST_TIMEOUT_SECONDS`, `APP_HOST`, `APP_PORT`.
  - `get_settings()` is cached with `lru_cache` to avoid repeated parsing.
- `app/schemas.py`
  - `ChatMessage`, `ChatRequest`, `ChatChoice`, `ChatUsage`, `ChatResponse`, `ErrorResponse`.
  - Models mirror the typical ChatGPT `/chat/completions` response shape.
- `app/services/chatgpt_client.py`
  - `call_chatgpt(ChatRequest) -> ChatResponse`.
  - Builds JSON body from the request + defaults from `Settings`.
  - Uses `httpx.AsyncClient` with configured timeout.
  - Raises if API key is missing, propagates HTTP errors for the route to map.
- `app/main.py`
  - Creates FastAPI app, configures CORS, static files, and templates.
  - `GET /` renders `templates/chat.html`.
  - `POST /api/chat` validates with `ChatRequest`, delegates to `call_chatgpt`, and returns `ChatResponse` or an error.

### Configuration and environment
- **Required for production**:
  - `OPENAI_API_KEY` – your ChatGPT/OpenAI API key.
- **Optional**:
  - `OPENAI_MODEL` (default: `gpt-4.1-mini`).
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
  - Currently, all history is in the browser only (`chat.js` maintains `conversation`).
  - To add persistence, you can:
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
  - Current implementation is non-streaming (simple JSON response).
  - For streaming, you can:
    - Use OpenAI/ChatGPT streaming APIs.
    - Expose SSE (Server-Sent Events) or websockets from FastAPI.
    - Update the UI to incrementally render tokens.

### Deployment assumptions
- Target: a VPS with Docker installed.
- You control:
  - Environment variables for the container.
  - Port mappings (host `8333` -> container `8333`).
- TLS/HTTPS can be terminated either on the VPS (reverse proxy) or upstream.
