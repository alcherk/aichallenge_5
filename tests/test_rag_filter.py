"""Tests for RAG filtering and reranking."""
import pytest
from app.app.rag.filter import filter_by_similarity
from app.app.rag.reranker import NoOpReranker, get_reranker


def test_filter_by_similarity_basic():
    """Test basic filtering removes low-similarity chunks."""
    chunks = [
        {"chunk_text": "High similarity", "score": 0.85, "document_id": "doc1", "chunk_index": 0},
        {"chunk_text": "Medium similarity", "score": 0.65, "document_id": "doc2", "chunk_index": 1},
        {"chunk_text": "Low similarity", "score": 0.35, "document_id": "doc3", "chunk_index": 2},
    ]
    
    filtered, metadata = filter_by_similarity(chunks, threshold=0.5, min_chunks=2)
    
    assert len(filtered) == 2
    assert all(chunk["score"] >= 0.5 for chunk in filtered)
    assert metadata["original_count"] == 3
    assert metadata["filtered_count"] == 2
    assert metadata["fallback_triggered"] is False


def test_filter_by_similarity_all_below_threshold():
    """Test fallback when all chunks are below threshold."""
    chunks = [
        {"chunk_text": "Low 1", "score": 0.3, "document_id": "doc1", "chunk_index": 0},
        {"chunk_text": "Low 2", "score": 0.25, "document_id": "doc2", "chunk_index": 1},
        {"chunk_text": "Low 3", "score": 0.2, "document_id": "doc3", "chunk_index": 2},
    ]
    
    filtered, metadata = filter_by_similarity(chunks, threshold=0.5, min_chunks=2)
    
    # Should fallback to top 2 chunks
    assert len(filtered) == 2
    assert metadata["fallback_triggered"] is True
    # Should be sorted by score (descending)
    assert filtered[0]["score"] >= filtered[1]["score"]


def test_filter_by_similarity_threshold_zero():
    """Test that threshold=0.0 passes all chunks (backward compatible)."""
    chunks = [
        {"chunk_text": "Any", "score": 0.1, "document_id": "doc1", "chunk_index": 0},
        {"chunk_text": "Any", "score": 0.05, "document_id": "doc2", "chunk_index": 1},
    ]
    
    filtered, metadata = filter_by_similarity(chunks, threshold=0.0, min_chunks=1)
    
    assert len(filtered) == 2
    assert metadata["fallback_triggered"] is False


def test_filter_by_similarity_empty_list():
    """Test filtering empty list."""
    filtered, metadata = filter_by_similarity([], threshold=0.5, min_chunks=2)
    
    assert len(filtered) == 0
    assert metadata["original_count"] == 0
    assert metadata["filtered_count"] == 0


def test_filter_by_similarity_metadata_scores_range():
    """Test that metadata includes scores range."""
    chunks = [
        {"chunk_text": "High", "score": 0.9, "document_id": "doc1", "chunk_index": 0},
        {"chunk_text": "Low", "score": 0.1, "document_id": "doc2", "chunk_index": 1},
    ]
    
    filtered, metadata = filter_by_similarity(chunks, threshold=0.5, min_chunks=1)
    
    assert metadata["scores_range"] == (0.1, 0.9)
    assert metadata["threshold"] == 0.5


@pytest.mark.asyncio
async def test_noop_reranker_preserves_order():
    """Test that NoOpReranker preserves original order."""
    reranker = NoOpReranker()
    chunks = [
        {"chunk_text": "First", "score": 0.8, "document_id": "doc1", "chunk_index": 0},
        {"chunk_text": "Second", "score": 0.7, "document_id": "doc2", "chunk_index": 1},
    ]
    
    result = await reranker.rerank("test query", chunks)
    
    assert result == chunks
    assert result[0]["chunk_text"] == "First"
    assert result[1]["chunk_text"] == "Second"


def test_get_reranker_noop():
    """Test getting NoOpReranker."""
    reranker = get_reranker("noop")
    assert isinstance(reranker, NoOpReranker)


def test_get_reranker_unknown_falls_back():
    """Test that unknown reranker type falls back to NoOpReranker."""
    reranker = get_reranker("unknown_type")
    assert isinstance(reranker, NoOpReranker)

