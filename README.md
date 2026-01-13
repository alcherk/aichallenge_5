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

**Terminal 1 - Chunkenizer (for RAG):**
```bash
cd ../Chunkenizer
docker-compose up -d
# Verify it's running:
curl http://localhost:8000/api/health
# Should return: {"status":"ok"}
```

**Terminal 2 - Backend:**
```bash
source .venv/bin/activate
export OPENAI_API_KEY="your-key-here"
uvicorn app.app.main:app --reload --port 8333
# Verify it's running:
curl http://localhost:8333/health
# Should return: {"status":"ok"}
```

**Terminal 3 - Frontend (optional, for dev with hot reload):**
```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:5173
```

**Note:** If Chunkenizer is not running, RAG will be disabled. Make sure Chunkenizer is running on port 8000 before testing chat with RAG features.

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
- `GIT_MCP_MAX_DIFF_SIZE` - Maximum size for git diff responses in Git MCP server (default: `50K`). Supports suffixes: `K` (KB), `M` (MB). Examples: `100K`, `500K`, `1M`. Maximum: 10MB. Use this to handle larger diffs in `/review` command.
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

**Chunkenizer is required for RAG functionality.** Make sure it's running before testing chat.

1. **Start Chunkenizer** (if not already running):
   ```bash
   cd ../Chunkenizer
   docker-compose up -d
   # Or run locally: python -m app.main
   ```

2. **Check if Chunkenizer is running**:
   ```bash
   # Quick check script (Python)
   python scripts/check_chunkenizer.py
   
   # Or bash script
   ./scripts/check_chunkenizer.sh
   
   # Or manually:
   curl http://localhost:8000/api/health
   # Should return: {"status":"ok"}
   ```

3. **Upload Documents** (for project documentation):
   ```bash
   # Via API
   curl -X POST http://localhost:8000/documents \
     -F "file=@document.txt" \
     -F "metadata_json={\"source\": \"docs\"}"
   
   # Or use the web UI at http://localhost:8000
   
   # Or use the project docs ingestion script:
   python scripts/ingest_project_docs.py
   ```

4. **Verify Chunkenizer is accessible**:
   ```bash
   curl http://localhost:8000/api/health
   ```

**Note:** If Chunkenizer is not running, the chat service will still work but RAG features will be disabled. Check the backend logs to see if RAG retrieval is failing.

### RAG Configuration

- `RAG_ENABLED`: Enable/disable RAG (default: `true`)
- `RAG_TOP_K`: Number of chunks to retrieve per query (default: `5`)
- `RAG_MAX_CONTEXT_CHARS`: Maximum context size before truncation (default: `8000`)
- `CHUNKENIZER_API_URL`: Chunkenizer API base URL (default: `http://localhost:8000`)

### Developer Assistant Mode

The service includes a developer assistant mode that automatically uses RAG with project documentation and Git context for questions about the project.

**Features:**
- Automatic detection of project-related questions
- `/help` command for explicit developer assistance
- Git context integration (current branch, modified files)
- Project documentation retrieval via RAG

**Configuration:**
- `DEV_ASSISTANT_MODE`: Enable/disable developer assistant mode (default: `true`)
- `RAG_PROJECT_DOCS_COLLECTION`: Chunkenizer collection name for project docs (default: `documents`)

**Usage:**

1. **Ingest project documentation (manual):**
   ```bash
   python scripts/ingest_project_docs.py --chunkenizer-url http://localhost:8000
   ```

2. **Auto-index project code and documentation:**
   ```bash
   # First run - full scan of all files
   python scripts/auto_index_project.py --full-scan --repo-path .
   
   # Incremental scan - only changed files
   python scripts/auto_index_project.py --repo-path .
   
   # Daemon mode - continuous monitoring (every 5 minutes)
   python scripts/auto_index_project.py --daemon --interval 300
   
   # Cron job (every 15 minutes)
   # Add to crontab: */15 * * * * cd /path/to/project && python scripts/auto_index_project.py
   ```

3. **Ask questions about the project:**
   - Use `/help <question>` for explicit developer assistance
   - Or ask naturally: "How does RAG work in this project?", "What is the API structure?"
   - The assistant will automatically use project documentation and Git context

**Example:**
```
User: /help How do I configure RAG?
Assistant: [Uses project docs + Git context to answer]
```

The assistant will:
- Retrieve relevant documentation chunks
- Include current Git branch and modified files
- Provide code examples and citations

### Developer Commands

The service provides two special commands for developer assistance: `/help` and `/review`.

#### `/help` Command

The `/help` command provides developer assistance by searching project documentation and code using RAG.

**Usage:**
```
/help <your question>
```

**Examples:**
```
/help how is chat implemented
/help what classes handle RAG
/help where is the API endpoint defined
/help how to configure MCP servers
```

**Features:**
- Searches project documentation and code using RAG
- Finds specific classes, functions, models, and files
- Provides exact file paths and code examples
- Uses higher `top_k` for RAG retrieval (doubled compared to regular queries)
- Includes Git context (current branch, modified files)
- Focuses on code search and implementation details

**How it works:**
1. Extracts your question from the `/help` command
2. Searches RAG for relevant code and documentation
3. Retrieves Git context (branch, modified files)
4. Provides detailed answer with file paths, class/function names, and code examples
5. Includes citations in format `[doc_name:doc_id:chunk_index]`

**Example Response:**
```
The chat implementation is in `app/app/services/chatgpt_client.py`:

- `call_chatgpt()` function handles non-streaming requests
- `stream_chatgpt()` function handles streaming requests
- RAG integration happens in `call_chatgpt()` at line 491

[app/app/services/chatgpt_client.py:491-520]
```

#### `/review` Command

The `/review` command acts as a Staff Engineer, reviewing uncommitted changes or specific commits in the Git repository.

**Usage:**
```
/review                    # Review uncommitted changes
/review commit            # Review the last commit (HEAD)
/review HEAD              # Review the last commit
/review HEAD~1            # Review the previous commit
/review <commit-hash>     # Review a specific commit
```

**Features:**
- Comprehensive code review covering:
  - **Architecture**: Design patterns, module structure, SOLID/DRY/KISS principles
  - **Code Style**: Conventions, naming, comments, documentation
  - **Bugs**: Error handling, edge cases, race conditions, null handling
  - **Performance**: Algorithm optimization, N+1 queries, inefficient operations
  - **Security**: SQL injection, XSS, input validation, secrets in code
- Uses RAG to check against project documentation and style guides
- Includes Git context (branch, commit info)
- Shows changed files and full diff
- **Only reports real issues** - categories without problems are omitted
- Provides specific code locations with file paths and line numbers
- Shows problematic code fragments from diff
- Suggests fixes with code examples

**Review Format:**
For each issue found, the review includes:
```
📁 file.py:123
```diff
- old_code
+ new_code
```
❌ Проблема: [description]
✅ Исправление: [suggestion]
```

**Configuration:**
- `GIT_MCP_MAX_DIFF_SIZE`: Control maximum diff size (default: `50K`). For larger diffs:
  ```bash
  export GIT_MCP_MAX_DIFF_SIZE=500K  # 500KB
  export GIT_MCP_MAX_DIFF_SIZE=1M    # 1MB
  ```

**Example:**
```
User: /review

Assistant: 
## Code Review

### 🐛 БАГИ

📁 app/app/mcp/servers/git_server.py:441
```diff
- sys.stdout.write(response_json + "\n")
+ sys.stdout.buffer.write(response_bytes)
```
❌ Проблема: Прямая запись в stdout может вызвать проблемы с кодировкой для больших ответов
✅ Исправление: Использовать sys.stdout.buffer.write() для бинарных данных

### ⚠️ БЕЗОПАСНОСТЬ

📁 app/app/services/chatgpt_client.py:234
```diff
- api_key = os.getenv("OPENAI_API_KEY")
+ api_key = settings.openai_api_key
```
❌ Проблема: Прямой доступ к переменным окружения вместо настроек
✅ Исправление: Использовать централизованные настройки из Settings
```

**Requirements:**
- Git repository must be initialized
- Chunkenizer must be running (for RAG-based review)
- Project documentation should be indexed (see [Auto-Indexing Project Code](#auto-indexing-project-code))

**Note:** If there are no issues found, the review will simply state that the code looks good.

### Auto-Indexing Project Code

The project includes an automatic indexing script that monitors your repository and indexes code and documentation files into Chunkenizer for RAG.

**Features:**
- Automatic detection of changed files via Git
- Full scan mode for initial indexing
- Incremental updates (only changed files)
- Daemon mode for continuous monitoring
- State management (tracks indexed files and changes)

**File Types Indexed:**
- Code: `.py`, `.ts`, `.tsx`, `.js`, `.jsx`, `.json`, `.yaml`, `.yml`
- Documentation: `.md`, `.txt`, `.rst`

**Configuration:**
- Automatically respects `.gitignore`
- Excludes: `node_modules`, `__pycache__`, `dist`, `build`, etc.
- Maximum file size: 1MB

**Usage Examples:**

```bash
# First time - index all files
python scripts/auto_index_project.py --full-scan

# Regular run - only index changed files
python scripts/auto_index_project.py

# Continuous monitoring (daemon mode)
python scripts/auto_index_project.py --daemon --interval 300

# Custom repository path
python scripts/auto_index_project.py --repo-path /path/to/repo --chunkenizer-url http://localhost:8000
```

**State File:**
The script creates `.rag_index_state.json` in the repository root to track:
- Last processed commit hash
- Indexed files and their hashes
- Last index time

This file is automatically added to `.gitignore`.

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
