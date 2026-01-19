"""Tests for Provider Router Service."""
import pytest
import pytest_asyncio
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock, patch

from app.app.services.provider_router import (
    ProviderRouter,
    ProviderResponse,
    StreamChunk,
)
from app.app.services.ollama_client import OllamaClient, OllamaResponse
from app.app.services.cache import ResponseCache, CachedResponse
from app.app.services.summarizer import HistorySummarizer
from app.app.schemas import ChatResponse, ChatChoice, ChatMessage, ChatUsage


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield os.path.join(tmpdir, "cache", "test_responses.db")


@pytest_asyncio.fixture
async def cache(temp_db_path):
    """Create a ResponseCache instance with temporary database."""
    cache = ResponseCache(db_path=temp_db_path)
    await cache._init_db()
    yield cache


@pytest.fixture
def mock_ollama_client():
    """Create a mock OllamaClient."""
    client = MagicMock(spec=OllamaClient)
    client.default_model = "llama3.2:3b"
    return client


@pytest.fixture
def mock_summarizer():
    """Create a mock HistorySummarizer."""
    summarizer = MagicMock(spec=HistorySummarizer)
    # Default: no summarization needed
    summarizer.should_summarize = AsyncMock(return_value=False)
    summarizer.summarize = AsyncMock(return_value=[])
    return summarizer


@pytest.fixture
def sample_messages():
    """Sample messages for testing."""
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]


@pytest.fixture
def sample_ollama_response():
    """Sample OllamaResponse for testing."""
    return OllamaResponse(
        content="I'm doing great! How can I help you today?",
        model="llama3.2:3b",
        tokens_used=25,
        inference_time_ms=150,
    )


@pytest.fixture
def sample_chat_response():
    """Sample ChatResponse for testing cloud provider."""
    return ChatResponse(
        id="test-response-id",
        model="gpt-4o-mini",
        choices=[
            ChatChoice(
                index=0,
                message=ChatMessage(
                    role="assistant",
                    content="I'm doing great! How can I help you today?",
                ),
                finish_reason="stop",
            )
        ],
        usage=ChatUsage(
            prompt_tokens=20,
            completion_tokens=15,
            total_tokens=35,
        ),
        provider="cloud",
    )


# =============================================================================
# Test: Routing to Local Provider (Ollama)
# =============================================================================


@pytest.mark.asyncio
async def test_routes_to_ollama_when_local(
    mock_ollama_client, cache, mock_summarizer, sample_messages, sample_ollama_response
):
    """Verify local provider routes to Ollama."""
    # Setup mock
    mock_ollama_client.chat = AsyncMock(return_value=sample_ollama_response)

    # Create router with mocked dependencies
    router = ProviderRouter(
        ollama_client=mock_ollama_client,
        cache=cache,
        summarizer=mock_summarizer,
    )

    # Execute
    response = await router.chat(
        messages=sample_messages,
        provider="local",
        model="llama3.2:3b",
        temperature=0.7,
        use_cache=False,  # Bypass cache for this test
    )

    # Verify Ollama client was called
    mock_ollama_client.chat.assert_called_once()
    call_kwargs = mock_ollama_client.chat.call_args.kwargs
    assert call_kwargs["messages"] == sample_messages
    assert call_kwargs["model"] == "llama3.2:3b"
    assert call_kwargs["temperature"] == 0.7

    # Verify response format
    assert isinstance(response, ProviderResponse)
    assert response.provider == "local"
    assert response.model == "llama3.2:3b"
    assert response.content == "I'm doing great! How can I help you today?"
    assert response.tokens_used == 25
    assert response.inference_time_ms == 150


@pytest.mark.asyncio
async def test_local_provider_uses_default_model(
    mock_ollama_client, cache, mock_summarizer, sample_messages, sample_ollama_response
):
    """Verify local provider uses default model when not specified."""
    mock_ollama_client.chat = AsyncMock(return_value=sample_ollama_response)

    router = ProviderRouter(
        ollama_client=mock_ollama_client,
        cache=cache,
        summarizer=mock_summarizer,
    )

    response = await router.chat(
        messages=sample_messages,
        provider="local",
        model=None,  # Don't specify model
        use_cache=False,
    )

    # Should use default model
    call_kwargs = mock_ollama_client.chat.call_args.kwargs
    assert call_kwargs["model"] is None  # Client handles default


# =============================================================================
# Test: Routing to Cloud Provider (OpenAI)
# =============================================================================


@pytest.mark.asyncio
async def test_routes_to_openai_when_cloud(
    mock_ollama_client, cache, mock_summarizer, sample_messages, sample_chat_response
):
    """Verify cloud provider routes to OpenAI."""
    # Create router with mocked dependencies
    router = ProviderRouter(
        ollama_client=mock_ollama_client,
        cache=cache,
        summarizer=mock_summarizer,
    )

    # Mock the call_chatgpt function
    with patch(
        "app.app.services.provider_router.call_chatgpt",
        new_callable=AsyncMock,
    ) as mock_call_chatgpt:
        mock_call_chatgpt.return_value = (sample_chat_response, {})

        response = await router.chat(
            messages=sample_messages,
            provider="cloud",
            model="gpt-4o-mini",
            temperature=0.7,
            use_cache=False,
        )

        # Verify call_chatgpt was called
        mock_call_chatgpt.assert_called_once()

        # Verify response format
        assert isinstance(response, ProviderResponse)
        assert response.provider == "cloud"
        assert response.model == "gpt-4o-mini"
        assert response.content == "I'm doing great! How can I help you today?"
        assert response.tokens_used == 35
        assert response.inference_time_ms is not None


@pytest.mark.asyncio
async def test_cloud_provider_converts_messages(
    mock_ollama_client, cache, mock_summarizer, sample_messages, sample_chat_response
):
    """Verify cloud provider converts messages to ChatRequest format."""
    router = ProviderRouter(
        ollama_client=mock_ollama_client,
        cache=cache,
        summarizer=mock_summarizer,
    )

    with patch(
        "app.app.services.provider_router.call_chatgpt",
        new_callable=AsyncMock,
    ) as mock_call_chatgpt:
        mock_call_chatgpt.return_value = (sample_chat_response, {})

        await router.chat(
            messages=sample_messages,
            provider="cloud",
            use_cache=False,
        )

        # Get the ChatRequest that was passed
        call_args = mock_call_chatgpt.call_args
        chat_request = call_args[0][0]

        # Verify messages were converted to ChatMessage objects
        assert len(chat_request.messages) == 2
        assert chat_request.messages[0].role == "system"
        assert chat_request.messages[1].role == "user"


# =============================================================================
# Test: Unified Response Format
# =============================================================================


@pytest.mark.asyncio
async def test_unified_response_format(
    mock_ollama_client, cache, mock_summarizer, sample_messages
):
    """Both providers return ProviderResponse with same structure."""
    # Setup local response
    local_response = OllamaResponse(
        content="Local response content",
        model="llama3.2:3b",
        tokens_used=30,
        inference_time_ms=200,
    )
    mock_ollama_client.chat = AsyncMock(return_value=local_response)

    # Setup cloud response
    cloud_chat_response = ChatResponse(
        id="cloud-id",
        model="gpt-4o-mini",
        choices=[
            ChatChoice(
                index=0,
                message=ChatMessage(role="assistant", content="Cloud response content"),
                finish_reason="stop",
            )
        ],
        usage=ChatUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    )

    router = ProviderRouter(
        ollama_client=mock_ollama_client,
        cache=cache,
        summarizer=mock_summarizer,
    )

    # Test local provider
    local_result = await router.chat(
        messages=sample_messages,
        provider="local",
        use_cache=False,
    )

    # Test cloud provider
    with patch(
        "app.app.services.provider_router.call_chatgpt",
        new_callable=AsyncMock,
    ) as mock_call_chatgpt:
        mock_call_chatgpt.return_value = (cloud_chat_response, {})
        cloud_result = await router.chat(
            messages=sample_messages,
            provider="cloud",
            use_cache=False,
        )

    # Both should be ProviderResponse
    assert isinstance(local_result, ProviderResponse)
    assert isinstance(cloud_result, ProviderResponse)

    # Both have same fields
    assert hasattr(local_result, "content")
    assert hasattr(local_result, "model")
    assert hasattr(local_result, "provider")
    assert hasattr(local_result, "tokens_used")
    assert hasattr(local_result, "inference_time_ms")
    assert hasattr(local_result, "summarized")

    assert hasattr(cloud_result, "content")
    assert hasattr(cloud_result, "model")
    assert hasattr(cloud_result, "provider")
    assert hasattr(cloud_result, "tokens_used")
    assert hasattr(cloud_result, "inference_time_ms")
    assert hasattr(cloud_result, "summarized")

    # Providers correctly set
    assert local_result.provider == "local"
    assert cloud_result.provider == "cloud"


# =============================================================================
# Test: Streaming Both Providers
# =============================================================================


@pytest.mark.asyncio
async def test_streaming_local_provider(
    mock_ollama_client, cache, mock_summarizer, sample_messages
):
    """Streaming works for local provider."""

    # Setup streaming mock
    async def mock_stream_chat(*args, **kwargs):
        for token in ["Hello", " ", "World", "!"]:
            yield token

    mock_ollama_client.stream_chat = mock_stream_chat

    router = ProviderRouter(
        ollama_client=mock_ollama_client,
        cache=cache,
        summarizer=mock_summarizer,
    )

    # Collect chunks
    chunks = []
    async for chunk in router.stream_chat(
        messages=sample_messages,
        provider="local",
        model="llama3.2:3b",
        use_cache=False,
    ):
        chunks.append(chunk)

    # Verify chunks
    assert len(chunks) > 0
    assert all(isinstance(c, StreamChunk) for c in chunks)

    # All chunks should have provider set
    for chunk in chunks[:-1]:  # All except final done chunk
        if chunk.delta:
            assert chunk.provider == "local"
            assert chunk.model == "llama3.2:3b"

    # Last chunk should have done=True
    assert chunks[-1].done is True

    # Content should be accumulated correctly
    content = "".join(c.delta for c in chunks)
    assert content == "Hello World!"


@pytest.mark.asyncio
async def test_streaming_cloud_provider(
    mock_ollama_client, cache, mock_summarizer, sample_messages
):
    """Streaming works for cloud provider."""

    router = ProviderRouter(
        ollama_client=mock_ollama_client,
        cache=cache,
        summarizer=mock_summarizer,
    )

    # Mock stream_chatgpt to yield events
    async def mock_stream_chatgpt(payload):
        for content in ["Hello", " ", "Cloud", "!"]:
            yield {
                "model": "gpt-4o-mini",
                "choices": [{"delta": {"content": content}}],
            }

    with patch(
        "app.app.services.provider_router.stream_chatgpt",
        mock_stream_chatgpt,
    ):
        chunks = []
        async for chunk in router.stream_chat(
            messages=sample_messages,
            provider="cloud",
            model="gpt-4o-mini",
            use_cache=False,
        ):
            chunks.append(chunk)

    # Verify chunks
    assert len(chunks) > 0
    assert all(isinstance(c, StreamChunk) for c in chunks)

    # Verify content
    content_chunks = [c for c in chunks if c.delta]
    for chunk in content_chunks:
        assert chunk.provider == "cloud"

    # Last chunk should be done
    assert chunks[-1].done is True


@pytest.mark.asyncio
async def test_streaming_caches_result(
    mock_ollama_client, cache, mock_summarizer, sample_messages
):
    """Streaming caches accumulated result when complete."""

    async def mock_stream_chat(*args, **kwargs):
        for token in ["Cached", " ", "content"]:
            yield token

    mock_ollama_client.stream_chat = mock_stream_chat

    router = ProviderRouter(
        ollama_client=mock_ollama_client,
        cache=cache,
        summarizer=mock_summarizer,
    )

    # First call - should stream and cache
    chunks = []
    async for chunk in router.stream_chat(
        messages=sample_messages,
        provider="local",
        model="llama3.2:3b",
        use_cache=True,
    ):
        chunks.append(chunk)

    # Verify content was streamed
    content = "".join(c.delta for c in chunks)
    assert "Cached content" in content

    # Check cache stats - should have an entry
    stats = await cache.get_stats()
    assert stats.entries == 1


# =============================================================================
# Test: Cache Integration
# =============================================================================


@pytest.mark.asyncio
async def test_cache_hit_returns_cached_response(
    mock_ollama_client, cache, mock_summarizer, sample_messages
):
    """Cache hits return cached response without calling provider."""
    # Setup mock (should NOT be called on cache hit)
    mock_ollama_client.chat = AsyncMock()

    router = ProviderRouter(
        ollama_client=mock_ollama_client,
        cache=cache,
        summarizer=mock_summarizer,
    )

    # Pre-populate cache
    cache_params = {
        "provider": "local",
        "temperature": 0.7,
        "max_tokens": None,
    }
    cache_key = cache.cache_key("llama3.2:3b", sample_messages, cache_params)
    await cache.set(
        key=cache_key,
        response="Cached response from previous call",
        model="llama3.2:3b",
        provider="local",
        metadata={"tokens_used": 50, "inference_time_ms": 100},
    )

    # Call router with same parameters
    response = await router.chat(
        messages=sample_messages,
        provider="local",
        model="llama3.2:3b",
        temperature=0.7,
        use_cache=True,
    )

    # Verify provider was NOT called (cache hit)
    mock_ollama_client.chat.assert_not_called()

    # Verify cached response was returned
    assert response.content == "Cached response from previous call"
    assert response.model == "llama3.2:3b"
    assert response.provider == "local"
    assert response.tokens_used == 50
    assert response.inference_time_ms == 100


@pytest.mark.asyncio
async def test_cache_miss_calls_provider(
    mock_ollama_client, cache, mock_summarizer, sample_messages, sample_ollama_response
):
    """Cache misses call the provider and cache the result."""
    mock_ollama_client.chat = AsyncMock(return_value=sample_ollama_response)

    router = ProviderRouter(
        ollama_client=mock_ollama_client,
        cache=cache,
        summarizer=mock_summarizer,
    )

    # Cache is empty - should be a miss
    response = await router.chat(
        messages=sample_messages,
        provider="local",
        model="llama3.2:3b",
        temperature=0.7,
        use_cache=True,
    )

    # Verify provider WAS called
    mock_ollama_client.chat.assert_called_once()

    # Verify response
    assert response.content == sample_ollama_response.content

    # Verify result was cached
    stats = await cache.get_stats()
    assert stats.entries == 1
    assert stats.misses == 1


@pytest.mark.asyncio
async def test_cache_bypass_with_use_cache_false(
    mock_ollama_client, cache, mock_summarizer, sample_messages, sample_ollama_response
):
    """Setting use_cache=False bypasses cache."""
    mock_ollama_client.chat = AsyncMock(return_value=sample_ollama_response)

    router = ProviderRouter(
        ollama_client=mock_ollama_client,
        cache=cache,
        summarizer=mock_summarizer,
    )

    # Pre-populate cache
    cache_params = {
        "provider": "local",
        "temperature": 0.7,
        "max_tokens": None,
    }
    cache_key = cache.cache_key("llama3.2:3b", sample_messages, cache_params)
    await cache.set(
        key=cache_key,
        response="This should be bypassed",
        model="llama3.2:3b",
        provider="local",
        metadata={},
    )

    # Call with use_cache=False
    response = await router.chat(
        messages=sample_messages,
        provider="local",
        model="llama3.2:3b",
        temperature=0.7,
        use_cache=False,  # Bypass cache
    )

    # Provider SHOULD be called despite cache entry existing
    mock_ollama_client.chat.assert_called_once()

    # Response should be from provider, not cache
    assert response.content == sample_ollama_response.content


@pytest.mark.asyncio
async def test_cache_different_params_no_collision(
    mock_ollama_client, cache, mock_summarizer, sample_messages, sample_ollama_response
):
    """Different parameters produce different cache keys."""
    mock_ollama_client.chat = AsyncMock(return_value=sample_ollama_response)

    router = ProviderRouter(
        ollama_client=mock_ollama_client,
        cache=cache,
        summarizer=mock_summarizer,
    )

    # Pre-populate cache with temperature=0.5
    cache_params_05 = {
        "provider": "local",
        "temperature": 0.5,
        "max_tokens": None,
    }
    cache_key_05 = cache.cache_key("llama3.2:3b", sample_messages, cache_params_05)
    await cache.set(
        key=cache_key_05,
        response="Response at temperature 0.5",
        model="llama3.2:3b",
        provider="local",
        metadata={},
    )

    # Request with temperature=0.7 - should be cache miss
    response = await router.chat(
        messages=sample_messages,
        provider="local",
        model="llama3.2:3b",
        temperature=0.7,  # Different temperature
        use_cache=True,
    )

    # Provider should be called (different cache key)
    mock_ollama_client.chat.assert_called_once()


# =============================================================================
# Test: Summarizer Integration
# =============================================================================


@pytest.mark.asyncio
async def test_summarizer_triggers_when_threshold_exceeded(
    mock_ollama_client, cache, sample_ollama_response
):
    """Auto-summarization triggers when context threshold is exceeded."""
    # Create a mock summarizer that says summarization is needed
    mock_summarizer = MagicMock(spec=HistorySummarizer)
    mock_summarizer.should_summarize = AsyncMock(return_value=True)

    # Summarize returns condensed messages
    summarized_messages = [
        {"role": "system", "content": "[Summary of previous conversation]"},
        {"role": "user", "content": "Hello?"},
    ]
    mock_summarizer.summarize = AsyncMock(return_value=summarized_messages)

    mock_ollama_client.chat = AsyncMock(return_value=sample_ollama_response)

    router = ProviderRouter(
        ollama_client=mock_ollama_client,
        cache=cache,
        summarizer=mock_summarizer,
    )

    # Long conversation that would exceed threshold
    long_messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "First message " * 100},
        {"role": "assistant", "content": "First response " * 100},
        {"role": "user", "content": "Second message " * 100},
        {"role": "assistant", "content": "Second response " * 100},
        {"role": "user", "content": "Hello?"},
    ]

    response = await router.chat(
        messages=long_messages,
        provider="local",
        model="llama3.2:3b",
        use_cache=False,
        auto_summarize=True,
    )

    # Verify summarizer was checked
    mock_summarizer.should_summarize.assert_called_once()

    # Verify summarize was called
    mock_summarizer.summarize.assert_called_once()

    # Verify response has summarized flag
    assert response.summarized is True

    # Verify the provider was called with summarized messages
    call_kwargs = mock_ollama_client.chat.call_args.kwargs
    assert call_kwargs["messages"] == summarized_messages


@pytest.mark.asyncio
async def test_summarizer_not_triggered_when_disabled(
    mock_ollama_client, cache, sample_messages, sample_ollama_response
):
    """Auto-summarization does not trigger when auto_summarize=False."""
    mock_summarizer = MagicMock(spec=HistorySummarizer)
    mock_summarizer.should_summarize = AsyncMock(return_value=True)

    mock_ollama_client.chat = AsyncMock(return_value=sample_ollama_response)

    router = ProviderRouter(
        ollama_client=mock_ollama_client,
        cache=cache,
        summarizer=mock_summarizer,
    )

    response = await router.chat(
        messages=sample_messages,
        provider="local",
        use_cache=False,
        auto_summarize=False,  # Disable summarization
    )

    # Summarizer should NOT be called
    mock_summarizer.should_summarize.assert_not_called()
    mock_summarizer.summarize.assert_not_called()

    # Response should not be marked as summarized
    assert response.summarized is False


@pytest.mark.asyncio
async def test_summarizer_not_triggered_below_threshold(
    mock_ollama_client, cache, sample_messages, sample_ollama_response
):
    """Auto-summarization does not trigger when below threshold."""
    mock_summarizer = MagicMock(spec=HistorySummarizer)
    mock_summarizer.should_summarize = AsyncMock(return_value=False)  # Below threshold

    mock_ollama_client.chat = AsyncMock(return_value=sample_ollama_response)

    router = ProviderRouter(
        ollama_client=mock_ollama_client,
        cache=cache,
        summarizer=mock_summarizer,
    )

    response = await router.chat(
        messages=sample_messages,
        provider="local",
        use_cache=False,
        auto_summarize=True,
    )

    # should_summarize was called but returned False
    mock_summarizer.should_summarize.assert_called_once()

    # summarize should NOT be called
    mock_summarizer.summarize.assert_not_called()

    # Response should not be marked as summarized
    assert response.summarized is False


@pytest.mark.asyncio
async def test_summarizer_uses_custom_threshold(
    mock_ollama_client, cache, sample_messages, sample_ollama_response
):
    """Custom summarize_threshold is passed to summarizer."""
    mock_summarizer = MagicMock(spec=HistorySummarizer)
    mock_summarizer.should_summarize = AsyncMock(return_value=False)

    mock_ollama_client.chat = AsyncMock(return_value=sample_ollama_response)

    router = ProviderRouter(
        ollama_client=mock_ollama_client,
        cache=cache,
        summarizer=mock_summarizer,
    )

    await router.chat(
        messages=sample_messages,
        provider="local",
        use_cache=False,
        auto_summarize=True,
        summarize_threshold=0.5,  # Custom threshold
    )

    # Verify custom threshold was passed
    call_kwargs = mock_summarizer.should_summarize.call_args.kwargs
    assert call_kwargs["threshold"] == 0.5


@pytest.mark.asyncio
async def test_summarizer_streaming_integration(
    mock_ollama_client, cache, sample_ollama_response
):
    """Summarizer works with streaming endpoint."""
    mock_summarizer = MagicMock(spec=HistorySummarizer)
    mock_summarizer.should_summarize = AsyncMock(return_value=True)

    summarized_messages = [
        {"role": "system", "content": "[Summary]"},
        {"role": "user", "content": "Hi"},
    ]
    mock_summarizer.summarize = AsyncMock(return_value=summarized_messages)

    async def mock_stream_chat(messages, **kwargs):
        # Store what messages were passed
        mock_stream_chat.received_messages = messages
        for token in ["Summarized", " response"]:
            yield token

    mock_stream_chat.received_messages = None
    mock_ollama_client.stream_chat = mock_stream_chat

    router = ProviderRouter(
        ollama_client=mock_ollama_client,
        cache=cache,
        summarizer=mock_summarizer,
    )

    long_messages = [
        {"role": "user", "content": "Message " * 100},
        {"role": "assistant", "content": "Response " * 100},
        {"role": "user", "content": "Hi"},
    ]

    chunks = []
    async for chunk in router.stream_chat(
        messages=long_messages,
        provider="local",
        use_cache=False,
        auto_summarize=True,
    ):
        chunks.append(chunk)

    # Summarizer was called
    mock_summarizer.should_summarize.assert_called_once()
    mock_summarizer.summarize.assert_called_once()

    # Stream received summarized messages
    assert mock_stream_chat.received_messages == summarized_messages


# =============================================================================
# Test: Edge Cases and Error Handling
# =============================================================================


@pytest.mark.asyncio
async def test_empty_response_content(
    mock_ollama_client, cache, mock_summarizer, sample_messages
):
    """Handle empty response content gracefully."""
    empty_response = OllamaResponse(
        content="",
        model="llama3.2:3b",
        tokens_used=0,
        inference_time_ms=50,
    )
    mock_ollama_client.chat = AsyncMock(return_value=empty_response)

    router = ProviderRouter(
        ollama_client=mock_ollama_client,
        cache=cache,
        summarizer=mock_summarizer,
    )

    response = await router.chat(
        messages=sample_messages,
        provider="local",
        use_cache=False,
    )

    assert response.content == ""
    assert isinstance(response, ProviderResponse)


@pytest.mark.asyncio
async def test_none_tokens_and_time(
    mock_ollama_client, cache, mock_summarizer, sample_messages
):
    """Handle None values for tokens_used and inference_time_ms."""
    response_no_metrics = OllamaResponse(
        content="Response without metrics",
        model="llama3.2:3b",
        tokens_used=None,
        inference_time_ms=None,
    )
    mock_ollama_client.chat = AsyncMock(return_value=response_no_metrics)

    router = ProviderRouter(
        ollama_client=mock_ollama_client,
        cache=cache,
        summarizer=mock_summarizer,
    )

    response = await router.chat(
        messages=sample_messages,
        provider="local",
        use_cache=False,
    )

    assert response.tokens_used is None
    assert response.inference_time_ms is None


@pytest.mark.asyncio
async def test_streaming_cache_hit_returns_single_chunk(
    mock_ollama_client, cache, mock_summarizer, sample_messages
):
    """Cache hit for streaming returns cached content as single chunk."""
    router = ProviderRouter(
        ollama_client=mock_ollama_client,
        cache=cache,
        summarizer=mock_summarizer,
    )

    # Pre-populate cache
    cache_params = {
        "provider": "local",
        "temperature": 0.7,
        "max_tokens": None,
    }
    cache_key = cache.cache_key("llama3.2:3b", sample_messages, cache_params)
    await cache.set(
        key=cache_key,
        response="Cached streaming content",
        model="llama3.2:3b",
        provider="local",
        metadata={},
    )

    # Stream should return cached content
    chunks = []
    async for chunk in router.stream_chat(
        messages=sample_messages,
        provider="local",
        model="llama3.2:3b",
        temperature=0.7,
        use_cache=True,
    ):
        chunks.append(chunk)

    # Should have content chunk + done chunk
    assert len(chunks) == 2
    assert chunks[0].delta == "Cached streaming content"
    assert chunks[0].done is False
    assert chunks[1].delta == ""
    assert chunks[1].done is True


@pytest.mark.asyncio
async def test_provider_router_lazy_initialization(temp_db_path):
    """Router lazily initializes dependencies when not provided."""
    router = ProviderRouter()

    # Properties should be accessible (lazy init happens)
    # This tests that the singletons are created properly
    assert router.ollama_client is not None
    assert router.cache is not None
    assert router.summarizer is not None


@pytest.mark.asyncio
async def test_cloud_provider_passes_kwargs(
    mock_ollama_client, cache, mock_summarizer, sample_messages, sample_chat_response
):
    """Cloud provider passes through additional kwargs."""
    router = ProviderRouter(
        ollama_client=mock_ollama_client,
        cache=cache,
        summarizer=mock_summarizer,
    )

    with patch(
        "app.app.services.provider_router.call_chatgpt",
        new_callable=AsyncMock,
    ) as mock_call_chatgpt:
        mock_call_chatgpt.return_value = (sample_chat_response, {})

        await router.chat(
            messages=sample_messages,
            provider="cloud",
            use_cache=False,
            mcp_enabled=True,
            assistant_mode=True,
        )

        # Verify kwargs were passed through to ChatRequest
        call_args = mock_call_chatgpt.call_args
        chat_request = call_args[0][0]
        assert chat_request.mcp_enabled is True
        assert chat_request.assistant_mode is True
