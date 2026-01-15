# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A FastAPI-based ChatGPT proxy service with RAG (Retrieval-Augmented Generation), MCP (Model Context Protocol) tools, and a React + TypeScript frontend. Runs in Docker on port 8333.

## Development Commands

### Backend Development

```bash
# Setup and run
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="your-key"
uvicorn app.app.main:app --reload --port 8333
```

### Frontend Development

```bash
cd frontend
npm install
npm run dev      # Dev server on port 5173 (proxies to backend)
npm run build    # Production build to frontend/dist/
npm run lint     # ESLint
```

### Docker

```bash
docker build -t chatgpt-proxy .
docker compose up -d --build
```

### RAG Setup (Optional)

```bash
# Start Chunkenizer (required for RAG)
cd ../Chunkenizer && docker-compose up -d

# Index project files for /help and /review commands
python scripts/auto_index_project.py --full-scan
```

## Architecture

### Dual Frontend Architecture

The app serves different frontends based on build availability:
- **Production**: React SPA from `frontend/dist/` (built into Docker image)
- **Legacy fallback**: Jinja2 templates from `app/app/templates/` (when `frontend/dist/` doesn't exist)

Detection in `main.py:37-46`:
```python
frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
use_react_frontend = frontend_dist.exists()
```

### Request Flow

```
POST /api/chat → call_chatgpt() → [RAG retrieval] → [MCP tools] → OpenAI Responses API → StructuredResponse
POST /api/chat/stream → stream_chatgpt() → [RAG retrieval] → SSE events (chunk/done/error)
```

### Key Backend Components

| File | Purpose |
|------|---------|
| `app/app/main.py` | FastAPI app, endpoints, SSE streaming |
| `app/app/services/chatgpt_client.py` | `call_chatgpt()`, `stream_chatgpt()`, OpenAI API integration |
| `app/app/config.py` | Settings class with `@lru_cache()` |
| `app/app/schemas.py` | Pydantic models: `ChatRequest`, `StructuredResponse` |
| `app/app/rag/` | RAG subsystem (chunkenizer adapter, context builder, prompt injection) |
| `app/app/mcp/` | MCP subsystem (manager, transports, builtin servers) |

### RAG Subsystem (`app/app/rag/`)

- **chunkenizer_adapter.py**: `retrieve_chunks()` calls Chunkenizer's `/search` endpoint
- **context_builder.py**: `build_context_block()` formats chunks with citations like `[doc_name:doc_id:chunk_index]`
- **prompt_injector.py**: `inject_rag_context()` and `inject_rag_context_strict()` (for Assistant Mode)
- **filter.py**: `filter_by_similarity()` applies threshold filtering with fallback
- **project_detector.py**: Detects `/help` and `/review` commands, project-related questions
- **git_context.py**: `get_git_context()`, `get_review_diff()` for code review

### MCP Subsystem (`app/app/mcp/`)

Three builtin servers are always available (no config needed):
1. **builtin_filesystem**: Read/write files within workspace
2. **builtin_fetch**: HTTP fetch with content extraction
3. **builtin_git**: Git operations (diff, status, log)

Additional servers can be added via `MCP_CONFIG_PATH`.

Tool naming: `mcp_{server_name}__{tool_name}` (e.g., `mcp_builtin_git__git_diff`)

### Frontend Architecture (React + TypeScript)

| Directory | Purpose |
|-----------|---------|
| `src/store/` | Zustand stores: `chatStore`, `settingsStore`, `metricsStore` |
| `src/services/` | API client (`api.ts`), SSE streaming (`streaming.ts`), localStorage (`storage.ts`) |
| `src/components/` | React components organized by feature |
| `src/types/` | TypeScript interfaces |

State management uses Zustand with localStorage persistence.

## Developer Commands

### `/help <question>`

Searches project docs/code via RAG:
```
/help how is RAG implemented
/help where is ChatRequest defined
```

Uses doubled `top_k` for broader search. Responds with file paths, class names, code examples.

### `/review [commit]`

Code review as Staff Engineer:
```
/review              # Review uncommitted changes
/review commit       # Review HEAD
/review HEAD~1       # Review previous commit
/review abc123       # Review specific commit
```

Categories checked: Architecture, Code Style, Bugs, Performance, Security

## Environment Variables

### Required
- `OPENAI_API_KEY`

### API Configuration
- `OPENAI_MODEL` (default: `gpt-4o-mini`)
- `OPENAI_API_BASE` (default: `https://api.openai.com/v1`)
- `OPENAI_CHAT_PATH` (default: `responses`) - path appended to base

### RAG Configuration
- `RAG_ENABLED` (default: `true`)
- `RAG_TOP_K` (default: `5`)
- `RAG_MAX_CONTEXT_CHARS` (default: `8000`)
- `CHUNKENIZER_API_URL` (default: `http://localhost:8000`)
- `RAG_MIN_SIMILARITY` (default: `0.0`) - filter threshold
- `RAG_RERANKER_ENABLED` (default: `false`)

### MCP Configuration
- `MCP_CONFIG_PATH` - path to JSON config for additional MCP servers
- `WORKSPACE_ROOT` (default: repo root) - constrains filesystem tools

## Implementation Notes

### System Prompt Injection

Both `call_chatgpt()` and `stream_chatgpt()` inject a Russian system prompt if none is present. When modifying:
- Non-streaming: `chatgpt_client.py:149-162` (`_prepare_messages`)
- Streaming: Same function, shared logic

Special prompts for `/review` (Staff Engineer), `/help` (code search), and Assistant Mode (strict RAG-only) are injected separately in the main functions.

### Responses API Usage

The service uses OpenAI's newer Responses API (`/v1/responses`) instead of Chat Completions:
- Set via `OPENAI_CHAT_PATH=responses` (default)
- Handles tool calls via `previous_response_id` continuation
- Helper functions: `_tools_to_responses_api()`, `_extract_text_from_responses()`

### Error Handling

All endpoints return `StructuredResponse`:
```python
{
    "success": bool,
    "status_code": int,
    "message": str,
    "data": ChatResponse | None,
    "error": {"type": str, "detail": str} | None,
    "metadata": {"timestamp": float, "rag": dict, ...}
}
```

### SSE Streaming Format

```
event: chunk
data: {"delta": "partial text..."}

event: done
data: {StructuredResponse}

event: error
data: {StructuredResponse with success=false}
```

## Testing

```bash
pytest                           # Run all tests
pytest tests/test_api.py -v      # Specific test file
pytest -k "test_chat"            # Pattern match
```
