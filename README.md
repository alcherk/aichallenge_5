# ChatGPT Proxy Service

Modern FastAPI-based proxy service with React + TypeScript frontend. Forwards requests to the ChatGPT API with a feature-rich web interface.

## Features

### Backend (FastAPI)
- ✅ `GET /health` - Health check endpoint
- ✅ `GET /` - Serves React SPA or legacy UI
- ✅ `POST /api/chat` - JSON API proxy with structured responses
- ✅ `POST /api/chat/stream` - Server-Sent Events (SSE) streaming
- ✅ CORS enabled for development
- ✅ Multi-stage Docker build

### Frontend (React + TypeScript)
- ✅ Real-time chat with SSE streaming
- ✅ Markdown rendering for assistant messages
- ✅ JSON detection and syntax highlighting
- ✅ **Settings Panel:**
  - Model selection (GPT-4o, GPT-4 Turbo, GPT-4o Mini, GPT-3.5 Turbo)
  - Temperature control (0.0 - 2.0)
  - System prompt customization
  - Conversation compression threshold
- ✅ **Metrics Panel:**
  - Token usage tracking (input/output/total)
  - Cost calculation per request
  - Context window usage visualization
  - Session totals and statistics
  - Response time monitoring
- ✅ Message history persistence (localStorage)
- ✅ Auto-scroll and responsive design
- ✅ "New Chat" functionality

## Quick Start

### Development (Dual Server)

**Terminal 1 - Backend:**
```bash
source .venv/bin/activate
export OPENAI_API_KEY="your-key-here"
uvicorn app.app.main:app --reload --port 8333
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:5173
```

### Production (Docker)

```bash
# Build image (includes React build)
docker build -t chatgpt-proxy .

# Run container
docker run -d \
  --name chatgpt-proxy \
  -e OPENAI_API_KEY="your-key" \
  -e OPENAI_MODEL="gpt-4o-mini" \
  -p 8333:8333 \
  --restart unless-stopped \
  chatgpt-proxy

# Access at http://localhost:8333
```

### Docker Compose

```bash
export OPENAI_API_KEY="your-key"
docker compose up -d --build
```

## Configuration

### Required
- `OPENAI_API_KEY` - Your OpenAI API key

### Optional
- `OPENAI_MODEL` - Default: `gpt-4o-mini`
- `OPENAI_API_BASE` - Default: `https://api.openai.com/v1`
- `REQUEST_TIMEOUT_SECONDS` - Default: `60`
- `APP_HOST` - Default: `0.0.0.0`
- `APP_PORT` - Default: `8333`

## Project Structure

```
.
├── app/
│   └── app/
│       ├── main.py           # FastAPI application
│       ├── config.py         # Environment configuration
│       ├── schemas.py        # Pydantic models
│       ├── services/
│       │   └── chatgpt_client.py  # OpenAI API client
│       ├── static/           # Legacy frontend (fallback)
│       └── templates/        # Legacy templates
├── frontend/                 # React + TypeScript SPA
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── store/           # Zustand state management
│   │   ├── services/        # API and storage services
│   │   ├── types/           # TypeScript definitions
│   │   └── utils/           # Utilities
│   ├── dist/                # Production build (gitignored)
│   └── package.json
├── requirements.txt         # Python dependencies
├── Dockerfile              # Multi-stage build
├── docker-compose.yml
├── CLAUDE.md              # Development guide for Claude Code
├── DEPLOYMENT.md          # Complete deployment guide
└── WEB_UI_ARCHITECTURE.md # Frontend architecture details
```

## Technology Stack

### Backend
- Python 3.11
- FastAPI
- Uvicorn
- httpx (async HTTP client)
- Pydantic (data validation)

### Frontend
- React 18
- TypeScript
- Vite (build tool)
- Tailwind CSS v4
- Zustand (state management)
- React Markdown
- SSE streaming

## Development

### Backend Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="your-key"
uvicorn app.app.main:app --reload --port 8333
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev  # Development server
npm run build  # Production build
npm run preview  # Preview production build
```

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete deployment instructions including:
- Docker deployment
- VPS deployment
- Reverse proxy configuration (nginx)
- SSL/TLS setup
- Monitoring and troubleshooting

## Architecture

The application uses a dual-frontend architecture:

**Development:**
- Backend runs on port 8333
- Vite dev server on port 5173 (proxies API requests to backend)
- Hot module replacement for instant feedback

**Production:**
- Single Docker container
- Backend serves React build from `frontend/dist/`
- All requests handled by FastAPI
- SSE streaming for real-time responses

## API Endpoints

### Health Check
```bash
GET /health
Response: {"status": "ok"}
```

### Chat (Non-streaming)
```bash
POST /api/chat
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "Hello"}
  ],
  "model": "gpt-4o-mini",
  "temperature": 0.7
}

Response: StructuredResponse with data, metadata, error fields
```

### Chat (Streaming)
```bash
POST /api/chat/stream
Content-Type: application/json
Accept: text/event-stream

Events:
- event: chunk - {"delta": "..."}
- event: done - Complete structured response
- event: error - Error details
```

## Features in Detail

### SSE Streaming
Real-time token-by-token responses using Server-Sent Events. The frontend displays text as it arrives from the API.

### Metrics Tracking
- Automatic cost calculation based on OpenAI pricing
- Token usage monitoring
- Context window usage with visual indicators
- Session totals persisted in localStorage

### Settings Management
- Multiple model support (GPT-4o, GPT-4 Turbo, GPT-4, GPT-4o Mini, GPT-3.5 Turbo)
- Temperature control with visual slider
- Custom system prompts
- Automatic conversation compression

### Data Persistence
All user data stored in browser localStorage:
- Conversation history
- User settings
- Metrics and statistics

## Documentation

- [CLAUDE.md](CLAUDE.md) - Development guide for Claude Code
- [WEB_UI_ARCHITECTURE.md](WEB_UI_ARCHITECTURE.md) - Frontend architecture proposal
- [DEPLOYMENT.md](DEPLOYMENT.md) - Complete deployment guide
- [CONTEXT.md](CONTEXT.md) - Architectural notes
- [frontend/README.md](frontend/README.md) - Frontend-specific documentation

## Security

- Never commit API keys
- Use environment variables for sensitive data
- Enable HTTPS in production
- Restrict CORS origins in production
- Input validation via Pydantic schemas

## Support

For issues:
1. Check logs: `docker logs chatgpt-proxy`
2. Verify environment variables
3. Test health endpoint: `curl http://localhost:8333/health`
4. Review [DEPLOYMENT.md](DEPLOYMENT.md) troubleshooting section

## License

See LICENSE file for details.
