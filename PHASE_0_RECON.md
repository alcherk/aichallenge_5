# PHASE 0 — RECON SUMMARY

## Chat Service Flow

### Main Entrypoints
- **FastAPI app**: `app/app/main.py`
- **Chat endpoints**:
  - `POST /api/chat` → `chat()` → `call_chatgpt()` (non-streaming)
  - `POST /api/chat/stream` → `chat_stream()` → `stream_chatgpt()` (SSE streaming)

### Chat Endpoint Flow
1. Request arrives at `/api/chat` or `/api/chat/stream`
2. `ChatRequest` validated via Pydantic (`schemas.py`)
3. Messages prepared in `_prepare_messages()` (`chatgpt_client.py:130-164`)
   - Adds Russian system prompt if no system message exists
   - Returns list of message dicts
4. LLM request built in `call_chatgpt()` or `stream_chatgpt()`
   - Converts messages to Responses API format
   - Handles MCP tools (optional)
   - Makes HTTP request to OpenAI API
5. Response processed and returned as `StructuredResponse` or SSE events

### Where LLM Request is Built
- **Non-streaming**: `app/app/services/chatgpt_client.py:194-347`
  - `call_chatgpt()` function
  - Builds request body with model, input (messages), tools, temperature, max_tokens
  - Uses `_prepare_messages()` to get message list
- **Streaming**: `app/app/services/chatgpt_client.py:350-469`
  - `stream_chatgpt()` function
  - Similar structure but with `stream: True`
  - Yields chunks as they arrive

### How Streaming Works
- SSE (Server-Sent Events) via `StreamingResponse`
- `stream_chatgpt()` yields dicts with `{"choices": [{"delta": {"content": "..."}}]}`
- Frontend uses `EventSource` to consume SSE stream
- Events: `chunk` (delta text), `done` (final response), `error` (errors)

### Where Prompts/Messages are Assembled
- **Function**: `_prepare_messages()` in `chatgpt_client.py:130-164`
- **Location**: Called by both `call_chatgpt()` and `stream_chatgpt()`
- **Behavior**: 
  - Takes `ChatRequest.messages` (list of `ChatMessage`)
  - Checks if system message exists
  - If not, inserts Russian system prompt at index 0
  - Returns list of dicts: `[{"role": "system", "content": "..."}, ...]`

---

## Chunkenizer Capabilities

### Document Ingestion
- **Endpoint**: `POST /documents` (multipart/form-data)
- **Process**:
  1. Upload file (`.md`, `.txt`, `.json`)
  2. Extract text based on content type
  3. Chunk using `TokenChunker` (tiktoken, configurable size/overlap)
  4. Generate embeddings via `SentenceTransformer` (all-MiniLM-L6-v2, 384 dims)
  5. Store in Qdrant vector DB + SQLite metadata DB
- **Returns**: `document_id`, `chunk_count`, `total_tokens`, `sha256`

### Embeddings Generation
- **Model**: `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions)
- **Location**: `app/ingest/processor.py:DocumentProcessor`
- **Method**: `embedding_model.encode(text)` → numpy array → list
- **Storage**: Qdrant vector database (persistent)

### Retrieval
- **Endpoint**: `POST /search` (JSON)
- **Request**: `{"query": "string", "top_k": 5, "filters": {...}}`
- **Process**:
  1. Generate query embedding using same model
  2. Search Qdrant with cosine similarity
  3. Return top_k results sorted by score
- **Response Format**:
  ```json
  {
    "query": "...",
    "results": [
      {
        "score": 0.85,
        "document_id": "uuid",
        "document_name": "doc.txt",
        "chunk_index": 3,
        "chunk_text": "...",
        "token_count": 450,
        "metadata": {}
      }
    ],
    "total_results": 1
  }
  ```

### Public Functions/Classes
- **API Endpoints** (`app/api/routes.py`):
  - `POST /search` → `search_documents()` → uses `DocumentProcessor` + `QdrantStore`
- **Classes**:
  - `DocumentProcessor` (`app/ingest/processor.py`): `process_document()`, `embedding_model`
  - `QdrantStore` (`app/vectorstore/qdrant_client.py`): `search()`, `add_vectors()`, `delete_by_doc_id()`
  - `TokenChunker` (`app/ingest/chunker.py`): `chunk_text()`, `count_tokens()`

### Storage/Index Format
- **SQLite** (`data/chunkenizer.db`): Document metadata only
  - Table: `documents` (id, name, sha256, chunk_count, total_tokens, metadata_json, ...)
- **Qdrant** (vector DB): Embeddings + chunk payloads
  - Collection: `documents` (default)
  - Vector size: 384 (all-MiniLM-L6-v2)
  - Distance: COSINE
  - Payload: `doc_id`, `name`, `chunk_index`, `chunk_text`, `token_count`, `metadata_json`, ...

### Configuration
- **Base URL**: `http://localhost:8000` (default, configurable)
- **No authentication** (currently)
- **Environment variables**: `QDRANT_HOST`, `QDRANT_PORT`, `EMBEDDING_MODEL`, etc.

---

## Integration Points

### Where to Add RAG
1. **Retrieval trigger**: Before `_prepare_messages()` or after message prep but before LLM call
2. **Best location**: In `call_chatgpt()` and `stream_chatgpt()` functions
   - After `messages = _prepare_messages(payload)` (line 205, 366)
   - Before building the OpenAI request body
3. **Query source**: Extract from latest user message (last message with `role="user"`)

### How to Call Chunkenizer
- **HTTP client**: Use `httpx.AsyncClient` (already used in codebase)
- **Endpoint**: `POST http://localhost:8000/search` (or configurable base URL)
- **Request**: `{"query": "user question", "top_k": 5}`
- **Response**: Parse `results` array, extract `chunk_text`, `document_id`, `chunk_index`

### Prompt Injection Strategy
- **Location**: Modify `_prepare_messages()` or inject context after message prep
- **Format**: Add system message or prepend context to user message
- **Citation format**: `[doc_id:chunk_id]` as specified
- **Instruction**: "Answer ONLY using the provided context. If not present, say you don't know. Cite sources as [doc_id:chunk_id]."

### Token/Context Limits
- **Current**: No explicit limits in chat service
- **Strategy**: 
  - Limit retrieved chunks by `top_k` (default 5)
  - Limit total context chars via `RAG_MAX_CONTEXT_CHARS` (default 8000)
  - Truncate chunk text if needed before injection

### Toggle RAG On/Off
- **Method**: Environment variable `RAG_ENABLED` (default: `true`)
- **Location**: Add to `Settings` class in `app/app/config.py`
- **Usage**: Check flag before calling Chunkenizer API

---

## Questions

1. **Chunkenizer base URL**: Should it be configurable via env var (e.g., `CHUNKENIZER_API_URL`), or hardcoded to `http://localhost:8000`?
   - **Decision needed**: Configurable is better for flexibility

2. **Error handling**: If Chunkenizer is unavailable, should RAG fail silently (skip retrieval) or return an error?
   - **Decision needed**: Fail silently with warning log (graceful degradation)

3. **Citation format**: Should `chunk_id` be the `chunk_index` from Chunkenizer, or a unique point ID?
   - **Decision needed**: Use `chunk_index` (simpler, matches Chunkenizer response)

---

## Next Steps

Proceed to **PHASE 1 — DESIGN** to create the detailed implementation plan.

