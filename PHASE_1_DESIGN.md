# PHASE 1 — DESIGN

## Minimal RAG Design

### Overview
Add RAG capability to the existing chat service by:
1. Retrieving relevant document chunks from Chunkenizer before LLM call
2. Injecting retrieved context into the prompt
3. Instructing the model to cite sources
4. Preserving existing behavior when RAG is disabled

---

## Architecture

### Request Flow (with RAG enabled)

```
User Request
    ↓
POST /api/chat or /api/chat/stream
    ↓
Extract latest user message
    ↓
[IF RAG_ENABLED]
    ↓
Call Chunkenizer API: POST /search
    ↓
Retrieve top_k chunks
    ↓
Format context block with citations
    ↓
[END IF]
    ↓
_prepare_messages() (existing)
    ↓
Inject context into system/user message
    ↓
call_chatgpt() or stream_chatgpt() (existing)
    ↓
Return response
```

### Key Design Decisions

1. **Retrieval happens BEFORE streaming starts**
   - Ensures context is available before first token
   - No changes to streaming logic needed

2. **Context injection point**
   - Modify `_prepare_messages()` to accept optional context
   - OR: Inject context after message prep, before LLM call
   - **Decision**: Inject after `_prepare_messages()` to avoid modifying core function signature

3. **Citation format**
   - Format: `[doc_id:chunk_index]`
   - Example: `[550e8400-e29b-41d4-a716-446655440000:3]`
   - Added inline in context block

4. **Token/context limits**
   - `RAG_MAX_CONTEXT_CHARS`: Truncate total context if exceeds limit
   - `RAG_TOP_K`: Limit number of chunks retrieved (default: 5)
   - Truncate individual chunks if needed (preserve citations)

5. **Toggle mechanism**
   - Environment variable: `RAG_ENABLED` (default: `true`)
   - Per-request override: Add `rag_enabled: bool` to `ChatRequest` (optional, for future)

---

## File-Level Plan

### Files to Create

1. **`app/app/rag/__init__.py`**
   - Empty init file

2. **`app/app/rag/chunkenizer_adapter.py`**
   - Thin adapter for Chunkenizer HTTP API
   - Functions:
     - `async def retrieve_chunks(query: str, top_k: int = 5, base_url: str = None) -> List[Dict]`
     - Returns: `[{"chunk_text": "...", "document_id": "...", "chunk_index": 0, "score": 0.85, "metadata": {...}}, ...]`
   - Error handling: Returns empty list on failure (with warning log)

3. **`app/app/rag/context_builder.py`**
   - Builds context block from retrieved chunks
   - Functions:
     - `def build_context_block(chunks: List[Dict], max_chars: int = 8000) -> str`
     - Formats: "CONTEXT:\n[chunk_text] [doc_id:chunk_index]\n\n[chunk_text] [doc_id:chunk_index]\n..."
   - Handles truncation if total exceeds `max_chars`

4. **`app/app/rag/prompt_injector.py`**
   - Injects context into messages
   - Functions:
     - `def inject_rag_context(messages: List[Dict], context: str) -> List[Dict]`
   - Strategy:
     - If system message exists: Append context instruction to system message
     - If no system message: Create system message with context instruction
     - Add context block as separate user message before the actual user question
     - OR: Prepend context to the last user message
   - **Decision**: Prepend context to last user message (simpler, preserves existing system prompt logic)

### Files to Modify

1. **`app/app/config.py`**
   - Add to `Settings` class:
     - `rag_enabled: bool = os.getenv("RAG_ENABLED", "true").lower() in {"1", "true", "yes", "y", "on"}`
     - `rag_top_k: int = int(os.getenv("RAG_TOP_K", "5"))`
     - `rag_max_context_chars: int = int(os.getenv("RAG_MAX_CONTEXT_CHARS", "8000"))`
     - `chunkenizer_api_url: str = os.getenv("CHUNKENIZER_API_URL", "http://localhost:8000")`

2. **`app/app/services/chatgpt_client.py`**
   - Modify `call_chatgpt()`:
     - After line 205 (`messages = _prepare_messages(payload)`)
     - Extract latest user message
     - If RAG enabled: Call `retrieve_chunks()`, build context, inject into messages
     - Continue with existing logic
   - Modify `stream_chatgpt()`:
     - After line 366 (`base_messages = _prepare_messages(payload)`)
     - Same RAG logic as non-streaming
     - Continue with existing streaming logic

3. **`app/app/schemas.py`**
   - Optional: Add `rag_enabled: Optional[bool] = None` to `ChatRequest` (for future per-request override)
   - **Decision**: Skip for now (keep minimal), add later if needed

### Files NOT to Modify
- `app/app/main.py` (endpoints remain unchanged)
- Frontend files (no changes needed)
- Existing streaming logic (no changes to SSE handling)

---

## Implementation Details

### Chunkenizer Adapter

```python
# app/app/rag/chunkenizer_adapter.py
async def retrieve_chunks(query: str, top_k: int = 5, base_url: str = None) -> List[Dict]:
    """
    Retrieve chunks from Chunkenizer API.
    
    Returns:
        List of dicts with keys: chunk_text, document_id, chunk_index, score, metadata
    """
    # HTTP POST to {base_url}/search
    # Handle errors gracefully (return empty list)
    # Log retrieval time
```

### Context Builder

```python
# app/app/rag/context_builder.py
def build_context_block(chunks: List[Dict], max_chars: int = 8000) -> str:
    """
    Build formatted context block with citations.
    
    Format:
    CONTEXT:
    
    [chunk_text] [doc_id:chunk_index]
    
    [chunk_text] [doc_id:chunk_index]
    ...
    """
    # Format each chunk with citation
    # Truncate if total exceeds max_chars
    # Return formatted string
```

### Prompt Injector

```python
# app/app/rag/prompt_injector.py
def inject_rag_context(messages: List[Dict], context: str) -> List[Dict]:
    """
    Inject RAG context into messages.
    
    Strategy:
    - Find last user message
    - Prepend context block + instruction
    - Return modified messages list
    """
    # Find last user message
    # Prepend: "Answer ONLY using the provided context. If not present, say you don't know. Cite sources as [doc_id:chunk_index].\n\nCONTEXT:\n{context}\n\nQuestion: {original_user_message}"
    # Return modified messages
```

### Integration in chatgpt_client.py

```python
# In call_chatgpt() and stream_chatgpt():
messages = _prepare_messages(payload)

# RAG retrieval (if enabled)
if settings.rag_enabled:
    # Extract latest user message
    user_messages = [m for m in messages if m.get("role") == "user"]
    if user_messages:
        query = user_messages[-1].get("content", "")
        if query:
            chunks = await retrieve_chunks(
                query=query,
                top_k=settings.rag_top_k,
                base_url=settings.chunkenizer_api_url
            )
            if chunks:
                context = build_context_block(chunks, settings.rag_max_context_chars)
                messages = inject_rag_context(messages, context)
```

---

## Definition of Done Checklist

### Phase 2 — Implementation
- [ ] Create `app/app/rag/` directory structure
- [ ] Implement `chunkenizer_adapter.py` with error handling
- [ ] Implement `context_builder.py` with truncation logic
- [ ] Implement `prompt_injector.py` with citation formatting
- [ ] Add RAG config to `Settings` class
- [ ] Integrate RAG into `call_chatgpt()`
- [ ] Integrate RAG into `stream_chatgpt()`
- [ ] Add logging: request_id, rag_enabled, retrieval_time_ms, top_k, context_size
- [ ] Test with RAG enabled
- [ ] Test with RAG disabled (existing behavior preserved)

### Phase 3 — Tests
- [ ] Unit test: `retrieve_chunks()` returns expected format
- [ ] Unit test: `build_context_block()` formats citations correctly
- [ ] Unit test: `inject_rag_context()` modifies messages correctly
- [ ] Integration test: Chat endpoint with RAG enabled returns response
- [ ] Integration test: Chat endpoint with RAG disabled works as before
- [ ] Test error handling: Chunkenizer unavailable → graceful degradation

### Phase 4 — Documentation
- [ ] Update README.md:
  - Add RAG section explaining how it works
  - Document environment variables
  - Add example curl request with RAG
  - Link to Chunkenizer setup instructions
- [ ] Document citation format
- [ ] Document how to ingest documents via Chunkenizer

---

## Error Handling

1. **Chunkenizer API unavailable**
   - Log warning: "Chunkenizer API unavailable, skipping RAG"
   - Continue without context (graceful degradation)

2. **Chunkenizer returns empty results**
   - Log info: "No chunks found for query"
   - Continue without context

3. **Invalid response from Chunkenizer**
   - Log error with details
   - Continue without context

4. **Context exceeds max_chars**
   - Truncate chunks (oldest first) until under limit
   - Log warning if truncation occurred

---

## Logging

Add structured logging:
```python
logger.info(
    "RAG retrieval request_id=%s rag_enabled=%s top_k=%d retrieval_time_ms=%.2f context_size=%d chunks=%d",
    request_id, settings.rag_enabled, settings.rag_top_k, retrieval_time_ms, context_size, len(chunks)
)
```

---

## Next Steps

Proceed to **PHASE 2 — IMPLEMENTATION**.

