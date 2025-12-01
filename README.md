## ChatGPT Proxy Service (FastAPI + Docker)

A lightweight FastAPI-based proxy in Python that exposes a simple web chat UI and forwards requests to the ChatGPT API. The service is designed to run inside Docker and listen on port **8333**, suitable for deployment to a VPS.

### Features
- **FastAPI backend** with:
  - `GET /health` – basic health check.
  - `GET /` – serves a single-page chat UI.
  - `POST /api/chat` – JSON API proxy to the ChatGPT `/chat/completions` endpoint.
- **Single-page web UI** (no auth, no persistence yet):
  - Clean, modern chat interface.
  - Client-side-only conversation history.
- **Dockerized deployment**:
  - Container listens on port `8333`.
  - Ready for VPS deployment or use behind a reverse proxy.

---

### Configuration

Set the following environment variables when running the container:

- **Required**
  - `OPENAI_API_KEY` – your ChatGPT/OpenAI API key.

- **Optional**
  - `OPENAI_MODEL` – model name (default: `gpt-4.1-mini`).
  - `OPENAI_API_BASE` – base URL for the API (default: `https://api.openai.com/v1`).
  - `REQUEST_TIMEOUT_SECONDS` – request timeout to upstream API (default: `60`).
  - `APP_HOST` – host to bind inside container (default: `0.0.0.0`).
  - `APP_PORT` – port to bind inside container (default: `8333`).

---

### Project structure (relevant parts)

- `app/app/main.py` – FastAPI app, routes, UI + API wiring.
- `app/app/config.py` – configuration via Pydantic `Settings`.
- `app/app/schemas.py` – Pydantic models for requests/responses.
- `app/app/services/chatgpt_client.py` – ChatGPT API client using `httpx`.
- `app/app/templates/chat.html` – main chat page.
- `app/app/static/styles.css` – styles for the chat UI.
- `app/app/static/chat.js` – front-end logic for sending/receiving messages.
- `requirements.txt` – Python dependencies.
- `Dockerfile` – container image definition.
- `docker-compose.yml` – optional local/dev runner.
- `CONTEXT.md` – architectural notes and extension ideas.

---

### Running locally without Docker

You can run the app directly with Uvicorn if you have Python available.

1. **Install dependencies**

   ```bash
   cd /Users/lex/Projects/ai/AI_Challenge_5/week1_day1
   python -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

2. **Set environment variables** (at least `OPENAI_API_KEY`):

   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   export OPENAI_MODEL="gpt-4.1-mini"  # optional
   ```

3. **Run the server**

   ```bash
   uvicorn app.app.main:app --host 0.0.0.0 --port 8333
   ```

4. **Open the UI**

   Visit `http://localhost:8333/` in your browser.

---

### Running with Docker (local)

1. **Build the image**

   ```bash
   cd /Users/lex/Projects/ai/AI_Challenge_5/week1_day1
   docker build -t chatgpt-proxy .
   ```

2. **Run the container**

   ```bash
   docker run -d \
     --name chatgpt-proxy \
     -e OPENAI_API_KEY="your-api-key-here" \
     -e OPENAI_MODEL="gpt-4.1-mini" \
     -p 8333:8333 \
     chatgpt-proxy
   ```

3. **Access the service**

   - Browser UI: `http://localhost:8333/`
   - Health check: `http://localhost:8333/health`
   - API endpoint: `POST http://localhost:8333/api/chat`

---

### Running with Docker Compose

If you prefer `docker-compose`, a basic file is included.

1. **Export your API key** (and optionally model):

   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   export OPENAI_MODEL="gpt-4.1-mini"  # optional
   ```

2. **Start the stack**

   ```bash
   cd /Users/lex/Projects/ai/AI_Challenge_5/week1_day1
   docker compose up -d --build
   ```

3. **Access as usual** at `http://localhost:8333/`.

---

### Deploying to a VPS with Docker

Assuming your VPS already has Docker (and optionally Docker Compose) installed:

1. **Copy the project to the VPS** (e.g., via `git clone` or `scp`).
2. **On the VPS**, build the image:

   ```bash
   cd /path/to/week1_day1
   docker build -t chatgpt-proxy .
   ```

3. **Set your API key** securely on the VPS and run the container:

   ```bash
   docker run -d \
     --name chatgpt-proxy \
     -e OPENAI_API_KEY="your-api-key-here" \
     -e OPENAI_MODEL="gpt-4.1-mini" \
     -p 8333:8333 \
     --restart unless-stopped \
     chatgpt-proxy
   ```

4. **Verify** the service from the VPS:

   ```bash
   curl http://localhost:8333/health
   ```

5. **Expose publicly**:
   - Either open port `8333` in your VPS firewall and hit `http://your-vps-ip:8333/`.
   - Or put a reverse proxy (nginx/Caddy/Traefik) in front, routing a domain to `127.0.0.1:8333`.

---

### Future extensions

Some ideas already accounted for in the design:

- Add server-side conversation history (database-backed) instead of browser-only.
- Introduce authentication and per-user sessions.
- Expose additional model parameters (temperature, max_tokens) in the UI.
- Implement streaming responses using SSE or websockets.
