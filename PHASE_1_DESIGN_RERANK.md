# PHASE 1 — DESIGN: Second-Stage RAG Filter/Reranker

## Updated RAG Flow Diagram

### Current Flow
```
User Query
    ↓
retrieve_chunks(query, top_k) → [chunk1, chunk2, ..., chunkN]
    ↓
build_context_block(chunks) → formatted context string
    ↓
inject_rag_context(messages, context) → modified messages
    ↓
LLM call
```

### Enhanced Flow (with Filter + Reranker)
```
User Query
    ↓
retrieve_chunks(query, top_k) → [chunk1, chunk2, ..., chunkN] (with scores)
    ↓
[IF RAG_COMPARE_MODE]
    baseline_chunks = chunks.copy()
[END IF]
    ↓
filter_by_similarity(chunks, threshold, min_chunks) → filtered_chunks
    ↓
[IF reranker_enabled]
    rerank_chunks(query, filtered_chunks) → reranked_chunks
[ELSE]
    reranked_chunks = filtered_chunks
[END IF]
    ↓
[IF RAG_COMPARE_MODE]
    baseline_context = build_context_block(baseline_chunks)
    enhanced_context = build_context_block(reranked_chunks)
    → Generate TWO answers (baseline + enhanced)
[ELSE]
    context = build_context_block(reranked_chunks)
    → Generate ONE answer
[END IF]
    ↓
inject_rag_context(messages, context) → modified messages
    ↓
LLM call(s)
```

## MODE A — Threshold Filter (Required)

### Design
- **Function**: `filter_by_similarity(chunks, threshold, min_chunks)`
- **Location**: `app/app/rag/filter.py`
- **Behavior**:
  1. Filter chunks where `score >= threshold`
  2. If filtered result has fewer than `min_chunks`:
     - Fallback: return top `min_chunks` chunks (by original score)
     - Log fallback event
  3. Preserve original scores and metadata

### Configuration
- `RAG_MIN_SIMILARITY` (float, default: `0.0`)
  - Reasonable default: `0.0` (pass all chunks, backward compatible)
  - Typical range: `0.3-0.7` for cosine similarity
- `RAG_MIN_CHUNKS` (int, default: `2`)
  - Minimum chunks to keep after filtering
  - Fallback threshold

### Implementation Details
```python
def filter_by_similarity(
    chunks: List[Dict[str, Any]],
    threshold: float,
    min_chunks: int
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Filter chunks by similarity score threshold.
    
    Returns:
        (filtered_chunks, metadata)
        metadata includes: original_count, filtered_count, fallback_triggered, scores
    """
```

## MODE B — Reranker (Optional / Pluggable)

### Design
- **Interface**: `Reranker` abstract base class
- **Location**: `app/app/rag/reranker.py`
- **Default implementation**: `NoOpReranker` (passthrough)
- **Future implementations**:
  - `CrossEncoderReranker` (sentence-transformers cross-encoder)
  - `LLMReranker` (LLM-based relevance scoring)

### Architecture
```python
class Reranker(ABC):
    @abstractmethod
    async def rerank(
        self,
        query: str,
        chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Rerank chunks by relevance to query.
        
        Returns:
            Reordered chunks (may include new rerank_score field)
        """
        pass

class NoOpReranker(Reranker):
    """Default: no reranking, preserve original order."""
    async def rerank(self, query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return chunks
```

### Configuration
- `RAG_RERANKER_ENABLED` (bool, default: `False`)
- `RAG_RERANKER_TYPE` (str, default: `"noop"`)
  - Options: `"noop"`, `"cross_encoder"`, `"llm"` (future)

## Order of Operations

### Final Pipeline
1. **Retrieve** → `retrieve_chunks()` → chunks with scores
2. **Filter** → `filter_by_similarity()` → filtered chunks (score >= threshold)
3. **Rerank** → `rerank_chunks()` → reordered chunks (optional)
4. **Truncate** → `build_context_block()` → formatted context (respects max_chars)
5. **Inject** → `inject_rag_context()` → modified messages
6. **Generate** → LLM call

### Metadata Preservation
- **Original score**: Preserved in `chunk["score"]`
- **Rerank score**: Added as `chunk["rerank_score"]` if reranker provides it
- **Original rank**: Preserved in chunk order (before reranking)
- **Filter metadata**: Logged but not stored in chunks

## Token Budget Safety

### Strategy
- **Filter happens BEFORE truncation**: Reduces chunks early
- **Rerank preserves chunk count**: No new chunks added
- **Truncation still applies**: `build_context_block()` respects `max_chars`
- **No token budget increase**: Filtering actually reduces tokens

## Comparison Mode (RAG_COMPARE_MODE)

### Design
- **Flag**: `RAG_COMPARE_MODE` (bool, default: `False`)
- **Behavior when enabled**:
  1. Store baseline chunks (before filter/rerank)
  2. Process enhanced chunks (with filter/rerank)
  3. Generate TWO separate LLM calls:
     - Baseline: using original chunks
     - Enhanced: using filtered/reranked chunks
  4. Return both answers in response

### Response Format
```json
{
  "success": true,
  "data": {
    "baseline": {
      "choices": [...],
      "chunks_used": 5,
      "chunks_scores": [0.85, 0.82, 0.78, 0.75, 0.72]
    },
    "enhanced": {
      "choices": [...],
      "chunks_used": 3,
      "chunks_scores": [0.85, 0.82, 0.78],
      "filter_threshold": 0.75,
      "reranker_enabled": false
    }
  }
}
```

### Alternative (if API compatibility must be preserved)
- Add separate endpoint: `POST /api/chat/compare`
- Or add query param: `?compare=true`
- Store comparison results in logs/JSON file

## Observability / Logging

### Log Events
1. **Initial retrieval**:
   - `initial_top_k`, `chunks_retrieved`, `scores_range` (min/max)

2. **After filtering**:
   - `chunks_after_filter`, `threshold_used`, `fallback_triggered`, `filtered_scores`

3. **After reranking**:
   - `chunks_after_rerank`, `reranker_type`, `rerank_scores` (if available)

4. **Final context**:
   - `final_chunks_count`, `context_size_chars`

### Log Format
```python
logger.info(
    "RAG pipeline request_id=%s initial_k=%d filtered_k=%d final_k=%d "
    "threshold=%.3f fallback=%s reranker=%s scores_range=[%.3f,%.3f]",
    request_id, initial_k, filtered_k, final_k,
    threshold, fallback_triggered, reranker_type, min_score, max_score
)
```

## Definition of Done Checklist

### Phase 2 — Implementation
- [ ] Create `app/app/rag/filter.py` with `filter_by_similarity()`
- [ ] Create `app/app/rag/reranker.py` with `Reranker` interface and `NoOpReranker`
- [ ] Add config vars: `rag_min_similarity`, `rag_min_chunks`, `rag_reranker_enabled`, `rag_compare_mode`
- [ ] Integrate filter into `call_chatgpt()` (non-streaming)
- [ ] Integrate filter into `stream_chatgpt()` (streaming)
- [ ] Add structured logging for filter/rerank steps
- [ ] Test fallback behavior (threshold too high)
- [ ] Test default behavior (threshold=0.0, backward compatible)

### Phase 3 — Comparison Mode
- [ ] Implement comparison mode in `call_chatgpt()`
- [ ] Generate two answers (baseline + enhanced)
- [ ] Return both in response (or separate endpoint)
- [ ] Include metadata (chunk counts, scores, thresholds)

### Phase 4 — Tests
- [ ] Test filtering removes low-similarity chunks
- [ ] Test threshold changes affect chunk count
- [ ] Test fallback triggers when threshold too high
- [ ] Test comparison mode produces two answers
- [ ] Test default config preserves existing behavior

### Phase 5 — Documentation
- [ ] Update README with filter/reranker explanation
- [ ] Document `RAG_MIN_SIMILARITY` tuning guide
- [ ] Document comparison mode usage
- [ ] Add recommended workflow for threshold tuning

## Default Configuration (Backward Compatible)

```python
RAG_MIN_SIMILARITY = 0.0  # Pass all chunks (no filtering)
RAG_MIN_CHUNKS = 2        # Safety fallback
RAG_RERANKER_ENABLED = False  # No reranking
RAG_COMPARE_MODE = False  # Single answer mode
```

With these defaults, behavior is **identical** to current implementation.

## Next Steps

Proceed to **PHASE 2 — IMPLEMENTATION**.

