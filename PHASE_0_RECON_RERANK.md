# PHASE 0 — RECON: Second-Stage RAG Filter/Reranker

## Current RAG Pipeline Flow

### 1. Retrieval Implementation
- **Location**: `app/app/rag/chunkenizer_adapter.py`
- **Function**: `retrieve_chunks(query, top_k, base_url, timeout)`
- **Returns**: List of dicts with keys:
  - `chunk_text`, `document_id`, `document_name`, `chunk_index`, `score`, `metadata`
- **Score availability**: ✅ **YES** - `score` is already extracted from Chunkenizer API response (line 64)

### 2. Top-K Selection
- **Location**: Chunkenizer API (`POST /search`)
- **Selection happens**: In Chunkenizer (Qdrant vector search)
- **Similarity metric**: **COSINE** (from Qdrant configuration)
- **Score range**: Typically 0.0 to 1.0 for cosine similarity (higher = more similar)
- **Order**: Results are already sorted by score (descending) from Chunkenizer

### 3. Context Assembly
- **Location**: `app/app/rag/context_builder.py`
- **Function**: `build_context_block(chunks, max_chars)`
- **Input**: List of chunk dicts (already includes `score` field)
- **Process**: Formats chunks with citations, truncates if exceeds `max_chars`

### 4. Integration Points
- **Non-streaming**: `app/app/services/chatgpt_client.py:208-245`
  - Line 222: `chunks = await retrieve_chunks(...)`
  - Line 228: `context = build_context_block(chunks, ...)`
  - Line 230: `messages = inject_rag_context(messages, context)`
  
- **Streaming**: `app/app/services/chatgpt_client.py:407-445`
  - Similar flow (lines 407-445)

### 5. Configuration
- **Location**: `app/app/config.py`
- **Current RAG vars**:
  - `rag_enabled` (bool)
  - `rag_top_k` (int, default: 5)
  - `rag_max_context_chars` (int, default: 8000)
  - `chunkenizer_api_url` (str)

## Similarity Score Details

### Score Availability
✅ **Scores ARE available** in the chunk dicts returned by `retrieve_chunks()`
- Field name: `score`
- Type: `float`
- Source: Chunkenizer API response (`result.get("score", 0.0)`)
- Metric: Cosine similarity (from Qdrant)
- Range: Typically 0.0-1.0 (higher = more similar)

### Current Usage
- Scores are **extracted** but **NOT used** for filtering
- Scores are **NOT logged** currently
- Scores are **NOT passed** to `build_context_block()` (but chunks dicts contain them)

## Injection Point for Second-Stage Filter

### Optimal Location
**Between retrieval and context building**:
- **File**: `app/app/services/chatgpt_client.py`
- **Non-streaming**: After line 226 (`chunks = await retrieve_chunks(...)`)
- **Streaming**: After line 411 (similar location)

### Code Pattern
```python
# Current flow:
chunks = await retrieve_chunks(...)  # Line 222/411
context = build_context_block(chunks, ...)  # Line 228/415

# Proposed flow:
chunks = await retrieve_chunks(...)  # Line 222/411
chunks = filter_by_similarity(chunks, threshold, min_chunks)  # NEW
chunks = rerank_chunks(chunks, query)  # NEW (optional)
context = build_context_block(chunks, ...)  # Line 228/415
```

## Exact Code Locations to Modify

1. **`app/app/config.py`** (Settings class):
   - Add: `rag_min_similarity` (float, default: 0.0 or reasonable threshold)
   - Add: `rag_min_chunks` (int, default: 2)
   - Add: `rag_reranker_enabled` (bool, default: False)
   - Add: `rag_compare_mode` (bool, default: False)

2. **`app/app/rag/`** (new files):
   - Create: `filter.py` - similarity threshold filtering
   - Create: `reranker.py` - reranker interface and implementations

3. **`app/app/services/chatgpt_client.py`**:
   - **Non-streaming** (`call_chatgpt`): Lines 222-228
   - **Streaming** (`stream_chatgpt`): Lines 411-415
   - Add filter/rerank calls between retrieval and context building

4. **`app/app/rag/context_builder.py`**:
   - No changes needed (already accepts chunks list)
   - Scores are preserved in chunk dicts but not used

## Summary

✅ **Similarity scores ARE available** - no need to expose them, they're already in chunk dicts
✅ **Injection point is clear** - between `retrieve_chunks()` and `build_context_block()`
✅ **Minimal changes needed** - add filter/rerank step, keep existing flow intact
✅ **Default behavior preserved** - set default threshold to 0.0 to pass all chunks

## Next Steps

Proceed to **PHASE 1 — DESIGN** to plan the filter/reranker implementation.

