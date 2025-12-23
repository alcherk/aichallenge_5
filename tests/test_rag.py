"""Tests for RAG functionality."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.app.rag.chunkenizer_adapter import retrieve_chunks
from app.app.rag.context_builder import build_context_block
from app.app.rag.prompt_injector import inject_rag_context


@pytest.mark.asyncio
async def test_retrieve_chunks_success():
    """Test successful chunk retrieval from Chunkenizer."""
    mock_response = {
        "query": "test query",
        "results": [
            {
                "score": 0.85,
                "document_id": "doc-123",
                "document_name": "test.txt",
                "chunk_index": 0,
                "chunk_text": "This is a test chunk.",
                "token_count": 10,
                "metadata": {},
            },
            {
                "score": 0.75,
                "document_id": "doc-123",
                "document_name": "test.txt",
                "chunk_index": 1,
                "chunk_text": "Another test chunk.",
                "token_count": 8,
                "metadata": {},
            },
        ],
        "total_results": 2,
    }
    
    with patch("httpx.AsyncClient") as mock_client:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = MagicMock()
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
        
        result = await retrieve_chunks("test query", top_k=5)
        
        assert len(result) == 2
        assert result[0]["chunk_text"] == "This is a test chunk."
        assert result[0]["document_id"] == "doc-123"
        assert result[0]["document_name"] == "test.txt"
        assert result[0]["chunk_index"] == 0
        assert result[0]["score"] == 0.85


@pytest.mark.asyncio
async def test_retrieve_chunks_empty_query():
    """Test that empty query returns empty list."""
    result = await retrieve_chunks("")
    assert result == []
    
    result = await retrieve_chunks("   ")
    assert result == []


@pytest.mark.asyncio
async def test_retrieve_chunks_api_error():
    """Test graceful handling of API errors."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=Exception("API error")
        )
        
        result = await retrieve_chunks("test query")
        assert result == []


def test_build_context_block():
    """Test context block building with citations."""
    chunks = [
        {
            "chunk_text": "First chunk text here.",
            "document_id": "doc-123",
            "document_name": "test1.txt",
            "chunk_index": 0,
        },
        {
            "chunk_text": "Second chunk text here.",
            "document_id": "doc-456",
            "document_name": "test2.txt",
            "chunk_index": 5,
        },
    ]
    
    context = build_context_block(chunks)
    
    assert "CONTEXT:" in context
    assert "First chunk text here." in context
    assert "[test1.txt:doc-123:0]" in context
    assert "Second chunk text here." in context
    assert "[test2.txt:doc-456:5]" in context


def test_build_context_block_empty():
    """Test that empty chunks return empty string."""
    context = build_context_block([])
    assert context == ""
    
    context = build_context_block([{"chunk_text": ""}])
    assert context == ""


def test_build_context_block_without_document_name():
    """Test that citation falls back to doc_id:chunk_index when document_name is missing."""
    chunks = [
        {
            "chunk_text": "Chunk without document name.",
            "document_id": "doc-123",
            "chunk_index": 0,
        },
    ]
    
    context = build_context_block(chunks)
    
    assert "CONTEXT:" in context
    assert "Chunk without document name." in context
    assert "[doc-123:0]" in context
    assert "[doc-123:0]" in context  # Should not have document_name in citation


def test_build_context_block_truncation():
    """Test that context is truncated if exceeds max_chars."""
    chunks = [
        {
            "chunk_text": "A" * 5000,  # 5000 chars
            "document_id": "doc-1",
            "document_name": "doc1.txt",
            "chunk_index": 0,
        },
        {
            "chunk_text": "B" * 5000,  # 5000 chars
            "document_id": "doc-2",
            "document_name": "doc2.txt",
            "chunk_index": 1,
        },
    ]
    
    # Max chars is 8000, so only first chunk should fit
    context = build_context_block(chunks, max_chars=8000)
    
    assert "CONTEXT:" in context
    assert "A" * 5000 in context
    # Second chunk should be truncated or omitted
    assert len(context) <= 8000 + 100  # Allow some overhead


def test_inject_rag_context():
    """Test injecting RAG context into messages."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is Python?"},
    ]
    
    context = "CONTEXT:\n\nPython is a language. [doc.txt:doc-1:0]"
    
    result = inject_rag_context(messages, context)
    
    assert len(result) == 2
    assert result[0]["role"] == "system"
    assert result[1]["role"] == "user"
    assert "CONTEXT:" in result[1]["content"]
    assert "What is Python?" in result[1]["content"]
    assert "Answer ONLY using the provided context" in result[1]["content"]
    assert "[doc_name:doc_id:chunk_index]" in result[1]["content"]


def test_inject_rag_context_no_user_message():
    """Test injecting context when no user message exists."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
    ]
    
    context = "CONTEXT:\n\nSome context. [doc.txt:doc-1:0]"
    
    result = inject_rag_context(messages, context)
    
    assert len(result) == 2
    assert result[1]["role"] == "user"
    assert "CONTEXT:" in result[1]["content"]
    assert "[doc_name:doc_id:chunk_index]" in result[1]["content"]


def test_inject_rag_context_empty_context():
    """Test that empty context doesn't modify messages."""
    messages = [
        {"role": "user", "content": "Hello"},
    ]
    
    result = inject_rag_context(messages, "")
    assert result == messages
    
    result = inject_rag_context(messages, "   ")
    assert result == messages

