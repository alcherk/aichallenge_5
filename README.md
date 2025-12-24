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
- `MCP_CONFIG_PATH` - Path to MCP server config JSON (optional; disabled by default)
- `WORKSPACE_ROOT` - Workspace root for filesystem-like MCP tools (default: repo root)
- `RAG_ENABLED` - Enable RAG (Retrieval-Augmented Generation) - Default: `true`
- `RAG_TOP_K` - Number of document chunks to retrieve - Default: `5`
- `RAG_MAX_CONTEXT_CHARS` - Maximum context size in characters - Default: `8000`
- `CHUNKENIZER_API_URL` - Chunkenizer API base URL - Default: `http://localhost:8000`
- `RAG_MIN_SIMILARITY` - Minimum similarity score threshold (0.0-1.0) - Default: `0.0`
- `RAG_MIN_CHUNKS` - Minimum chunks to keep after filtering - Default: `2`
- `RAG_RERANKER_ENABLED` - Enable reranking - Default: `false`
- `RAG_RERANKER_TYPE` - Reranker type (`noop`, etc.) - Default: `noop`
- `RAG_COMPARE_MODE` - Enable comparison mode (baseline vs enhanced) - Default: `false`
- `RAG_MIN_SIMILARITY` - Minimum similarity score threshold (0.0-1.0) - Default: `0.0`
- `RAG_MIN_CHUNKS` - Minimum chunks to keep after filtering - Default: `2`
- `RAG_RERANKER_ENABLED` - Enable reranking - Default: `false`
- `RAG_RERANKER_TYPE` - Reranker type (`noop`, etc.) - Default: `noop`
- `RAG_COMPARE_MODE` - Enable comparison mode (baseline vs enhanced) - Default: `false`

## RAG (Retrieval-Augmented Generation) (Optional)

This project supports **RAG** to enhance chat responses with retrieved document context from Chunkenizer.

- RAG is **enabled by default** (set `RAG_ENABLED=false` to disable)
- When enabled, the chat service retrieves relevant document chunks from Chunkenizer before generating responses
- Responses include citations in the format `[doc_name:doc_id:chunk_index]`

### How RAG Works

1. **Document Ingestion**: Upload documents to Chunkenizer (see [Chunkenizer Setup](#chunkenizer-setup))
2. **Query Processing**: When a user sends a message, the service:
   - Extracts the user's question
   - Calls Chunkenizer's `/search` endpoint to retrieve top-k relevant chunks
   - Formats the chunks with citations
   - Injects the context into the prompt with instructions to cite sources
3. **Response Generation**: The LLM generates a response using the provided context and includes citations

### Chunkenizer Setup

1. **Start Chunkenizer** (if not already running):
   ```bash
   cd ../Chunkenizer
   docker-compose up -d
   # Or run locally: python -m app.main
   ```

2. **Upload Documents**:
   ```bash
   # Via API
   curl -X POST http://localhost:8000/documents \
     -F "file=@document.txt" \
     -F "metadata_json={\"source\": \"docs\"}"
   
   # Or use the web UI at http://localhost:8000
   ```

3. **Verify Chunkenizer is accessible**:
   ```bash
   curl http://localhost:8000/api/health
   ```

### RAG Configuration

- `RAG_ENABLED`: Enable/disable RAG (default: `true`)
- `RAG_TOP_K`: Number of chunks to retrieve per query (default: `5`)
- `RAG_MAX_CONTEXT_CHARS`: Maximum context size before truncation (default: `8000`)
- `CHUNKENIZER_API_URL`: Chunkenizer API base URL (default: `http://localhost:8000`)

#### Second-Stage Filtering and Reranking

- `RAG_MIN_SIMILARITY`: Minimum similarity score threshold (default: `0.0`)
  - Filters out chunks with similarity score below this threshold
  - Range: 0.0-1.0 (cosine similarity, higher = more similar)
  - Default `0.0` passes all chunks (backward compatible)
  - Recommended: `0.3-0.7` depending on your use case
  
- `RAG_MIN_CHUNKS`: Minimum chunks to keep after filtering (default: `2`)
  - Fallback: if filtering removes too many chunks, keeps top N by score
  - Prevents empty context when threshold is too high

- `RAG_RERANKER_ENABLED`: Enable reranking (default: `false`)
  - Currently supports `NoOpReranker` (passthrough)
  - Future: cross-encoder and LLM-based rerankers

- `RAG_RERANKER_TYPE`: Type of reranker to use (default: `"noop"`)
  - Options: `"noop"` (no reranking, preserves original order)

- `RAG_COMPARE_MODE`: Enable comparison mode (default: `false`)
  - When enabled, generates two answers:
    1. Baseline: using original chunks (no filter/rerank)
    2. Enhanced: using filtered/reranked chunks
  - Both answers included in response for quality comparison

### Example Request with RAG

```bash
curl -X POST http://localhost:8333/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What is machine learning?"}
    ],
    "model": "gpt-4o-mini"
  }'
```

The response will include information from retrieved document chunks, with citations like `[document.txt:doc-123:0]` when referencing specific chunks. The citation format includes the document name, document ID, and chunk index.

### Disabling RAG

To disable RAG and use the chat service without document retrieval:

```bash
export RAG_ENABLED=false
```

Or set it in your environment/docker-compose configuration.

## MCP (Model Context Protocol) Tools (Optional)

This project can optionally expose **external MCP servers** as tool calls to the assistant at runtime (OpenAI tool-calling).

- MCP is **disabled by default**
- When enabled, the backend connects to configured MCP servers at startup, fetches their available tools, and makes them callable by the model
- Filesystem-like tools are restricted to `WORKSPACE_ROOT` (no auth layer is added)

### Enable MCP

1) Create a config file (start from [`mcp_servers.example.json`](mcp_servers.example.json)).

2) Set env vars:

```bash
export MCP_CONFIG_PATH="/absolute/path/to/mcp_servers.json"
export WORKSPACE_ROOT="/absolute/path/to/your/workspace"
```

3) Start the backend as usual.

### Configure MCP servers

The config file is JSON with a `servers` array. Each server supports:

- `name`: display name
- `transport`: `"stdio"` or `"http"`
- `command`: for stdio servers (array of strings)
- `url`: for HTTP servers
- `kind`: `"filesystem"` or `"fetch"` (enables extra validation/safety; optional)

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
│       ├── rag/              # RAG (Retrieval-Augmented Generation)
│       │   ├── chunkenizer_adapter.py  # Chunkenizer API adapter
│       │   ├── context_builder.py      # Context formatting
│       │   └── prompt_injector.py      # Prompt injection
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

**Note**: If RAG is enabled, the service will automatically retrieve relevant document chunks from Chunkenizer and include them in the context. Responses will include citations in the format `[doc_name:doc_id:chunk_index]`.

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
