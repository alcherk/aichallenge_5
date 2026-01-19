"""Tests for History Summarizer Service."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.app.services.summarizer import (
    HistorySummarizer,
    get_summarizer,
    MODEL_CONTEXT_LIMITS,
    DEFAULT_CONTEXT_LIMIT,
)


@pytest.fixture
def summarizer():
    """Create a HistorySummarizer instance for testing."""
    return HistorySummarizer(chars_per_token=4.0)


@pytest.fixture
def sample_messages():
    """Create sample messages for testing."""
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
        {"role": "assistant", "content": "I'm doing well, thank you!"},
        {"role": "user", "content": "What is the capital of France?"},
        {"role": "assistant", "content": "The capital of France is Paris."},
        {"role": "user", "content": "Tell me more about Paris."},
        {"role": "assistant", "content": "Paris is known for the Eiffel Tower and great cuisine."},
    ]


@pytest.fixture
def large_messages():
    """Create a large set of messages that should trigger summarization."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
    ]
    # Generate enough messages to exceed typical context limits
    for i in range(100):
        messages.append({"role": "user", "content": f"Question number {i}: " + "A" * 500})
        messages.append({"role": "assistant", "content": f"Answer number {i}: " + "B" * 500})
    return messages


class TestShouldSummarize:
    """Tests for the should_summarize method."""

    @pytest.mark.asyncio
    async def test_should_summarize_threshold(self, summarizer, large_messages):
        """Test that should_summarize returns True when messages exceed threshold."""
        # Large messages with a small model context should trigger summarization
        result = await summarizer.should_summarize(
            messages=large_messages,
            model="gpt-4",  # 8192 context limit
            threshold=0.9,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_should_summarize_under_threshold(self, summarizer, sample_messages):
        """Test that should_summarize returns False when under threshold."""
        # Small set of messages should not trigger summarization
        result = await summarizer.should_summarize(
            messages=sample_messages,
            model="gpt-4o",  # 128000 context limit
            threshold=0.9,
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_should_summarize_custom_threshold(self, summarizer, sample_messages):
        """Test should_summarize with custom threshold values."""
        # With a very low threshold, even small messages should trigger
        # Create messages with known token count
        messages = [
            {"role": "user", "content": "A" * 4000},  # ~1000 tokens
        ]

        # With gpt-4 (8192 limit) and threshold 0.01 (~82 tokens), this should trigger
        result = await summarizer.should_summarize(
            messages=messages,
            model="gpt-4",
            threshold=0.01,
        )
        assert result is True


class TestTokenCounting:
    """Tests for token estimation."""

    def test_token_counting_basic(self, summarizer):
        """Test that token estimation is reasonable for basic messages."""
        messages = [
            {"role": "user", "content": "Hello world"},  # ~11 chars + overhead
        ]

        tokens = summarizer._count_tokens(messages)

        # With 4 chars per token and overhead, should be reasonable
        # "user" (4) + 4 overhead + "Hello world" (11) + 4 overhead = ~23 chars / 4 = ~6 tokens
        assert tokens > 0
        assert tokens < 20  # Should be reasonable for this short message

    def test_token_counting_multiple_messages(self, summarizer, sample_messages):
        """Test token counting with multiple messages."""
        tokens = summarizer._count_tokens(sample_messages)

        # Should have a reasonable count for our sample messages
        assert tokens > 0

        # Calculate expected roughly:
        # Each message has role + content + overhead
        # 7 messages with varying lengths should give meaningful token count
        total_content_length = sum(len(m.get("content", "")) for m in sample_messages)
        expected_min = total_content_length // 6  # Conservative estimate
        expected_max = total_content_length  # Upper bound

        assert tokens >= expected_min
        assert tokens <= expected_max

    def test_token_counting_empty_messages(self, summarizer):
        """Test token counting with empty message list."""
        tokens = summarizer._count_tokens([])
        assert tokens == 0

    def test_token_counting_custom_chars_per_token(self):
        """Test that chars_per_token parameter affects estimation."""
        messages = [{"role": "user", "content": "A" * 100}]

        summarizer_default = HistorySummarizer(chars_per_token=4.0)
        summarizer_custom = HistorySummarizer(chars_per_token=2.0)

        tokens_default = summarizer_default._count_tokens(messages)
        tokens_custom = summarizer_custom._count_tokens(messages)

        # With half the chars_per_token, should get roughly double the tokens
        assert tokens_custom > tokens_default


class TestContextLimitLookup:
    """Tests for context limit lookup."""

    def test_context_limit_known_models(self, summarizer):
        """Test that known models return correct limits."""
        # Test several known models
        assert summarizer._get_context_limit("gpt-4") == 8192
        assert summarizer._get_context_limit("gpt-4o") == 128000
        assert summarizer._get_context_limit("gpt-4o-mini") == 128000
        assert summarizer._get_context_limit("gpt-3.5-turbo") == 16385
        assert summarizer._get_context_limit("qwen2.5:14b") == 32768
        assert summarizer._get_context_limit("llama3.2:3b") == 131072

    def test_context_limit_unknown_model(self, summarizer):
        """Test that unknown models return default limit."""
        result = summarizer._get_context_limit("unknown-model-xyz")
        assert result == DEFAULT_CONTEXT_LIMIT

    def test_context_limit_partial_match(self, summarizer):
        """Test that partial model names can match."""
        # Model names with version suffixes should still match base models
        # This tests the partial matching logic
        # Note: The matching logic checks if our model starts with known model
        # or if known model starts with our base model
        result = summarizer._get_context_limit("gpt-4-turbo-preview")
        # Should match gpt-4-turbo-preview exactly (in MODEL_CONTEXT_LIMITS)
        assert result == 128000

    def test_context_limit_all_known_models_defined(self):
        """Test that MODEL_CONTEXT_LIMITS contains expected models."""
        # Verify key models are in the lookup
        assert "gpt-4" in MODEL_CONTEXT_LIMITS
        assert "gpt-4o" in MODEL_CONTEXT_LIMITS
        assert "gpt-3.5-turbo" in MODEL_CONTEXT_LIMITS
        assert "qwen2.5:14b" in MODEL_CONTEXT_LIMITS
        assert "llama3.2:3b" in MODEL_CONTEXT_LIMITS


class TestSummarize:
    """Tests for the summarize method."""

    @pytest.mark.asyncio
    async def test_summarize_keeps_recent(self, summarizer, sample_messages):
        """Test that recent messages are preserved during summarization."""
        mock_summary = "Previous conversation discussed greetings and France."

        with patch.object(
            summarizer, "_summarize_local", new_callable=AsyncMock
        ) as mock_local:
            mock_local.return_value = mock_summary

            result = await summarizer.summarize(
                messages=sample_messages,
                keep_recent=2,
                provider="local",
            )

            # Should have system message(s) + summary message + 2 recent messages
            # Original: 1 system + 6 conversation messages
            # After: 1 original system + 1 summary + 2 recent = 4
            assert len(result) == 4

            # Check last 2 messages are the recent ones (preserved)
            assert result[-2] == sample_messages[-2]  # Second to last
            assert result[-1] == sample_messages[-1]  # Last

    @pytest.mark.asyncio
    async def test_summarize_preserves_system_messages(self, summarizer, sample_messages):
        """Test that system messages are preserved during summarization."""
        mock_summary = "Summary of previous conversation."

        with patch.object(
            summarizer, "_summarize_local", new_callable=AsyncMock
        ) as mock_local:
            mock_local.return_value = mock_summary

            result = await summarizer.summarize(
                messages=sample_messages,
                keep_recent=2,
                provider="local",
            )

            # Find all system messages
            system_messages = [m for m in result if m.get("role") == "system"]

            # Should have at least 2 system messages:
            # 1. Original system message
            # 2. Summary message (also system role)
            assert len(system_messages) >= 2

            # Original system message should be preserved
            original_system = sample_messages[0]
            assert original_system in result

            # Summary should be a system message containing the summary text
            summary_msg = [m for m in system_messages if "summary" in m.get("content", "").lower()]
            assert len(summary_msg) == 1
            assert mock_summary in summary_msg[0]["content"]

    @pytest.mark.asyncio
    async def test_summarize_local_provider(self, summarizer, sample_messages):
        """Test that local provider uses Ollama for summarization."""
        mock_summary = "Local summary of the conversation."

        with patch.object(
            summarizer, "_summarize_local", new_callable=AsyncMock
        ) as mock_local:
            mock_local.return_value = mock_summary

            result = await summarizer.summarize(
                messages=sample_messages,
                keep_recent=2,
                provider="local",
                model="qwen2.5:14b",
            )

            # Verify _summarize_local was called
            mock_local.assert_called_once()

            # Check that the model was passed (positional arg is prompt, model is second positional)
            call_args = mock_local.call_args
            # First positional argument is prompt, second is model
            assert call_args[0][1] == "qwen2.5:14b"

    @pytest.mark.asyncio
    async def test_summarize_cloud_provider(self, summarizer, sample_messages):
        """Test that cloud provider uses OpenAI for summarization."""
        mock_summary = "Cloud summary of the conversation."

        with patch.object(
            summarizer, "_summarize_cloud", new_callable=AsyncMock
        ) as mock_cloud:
            mock_cloud.return_value = mock_summary

            result = await summarizer.summarize(
                messages=sample_messages,
                keep_recent=2,
                provider="cloud",
                model="gpt-4o-mini",
            )

            # Verify _summarize_cloud was called
            mock_cloud.assert_called_once()

            # Check that the model was passed (positional arg is prompt, model is second positional)
            call_args = mock_cloud.call_args
            # First positional argument is prompt, second is model
            assert call_args[0][1] == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_summarize_failure_returns_original(self, summarizer, sample_messages):
        """Test that on error, original messages are returned."""
        with patch.object(
            summarizer, "_summarize_local", new_callable=AsyncMock
        ) as mock_local:
            mock_local.side_effect = Exception("LLM API error")

            result = await summarizer.summarize(
                messages=sample_messages,
                keep_recent=2,
                provider="local",
            )

            # Should return original messages unchanged
            assert result == sample_messages

    @pytest.mark.asyncio
    async def test_summarize_not_enough_messages(self, summarizer):
        """Test that messages below keep_recent are returned unchanged."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        result = await summarizer.summarize(
            messages=messages,
            keep_recent=4,  # More than we have
            provider="local",
        )

        # Should return original messages unchanged
        assert result == messages

    @pytest.mark.asyncio
    async def test_summarize_format_includes_markers(self, summarizer, sample_messages):
        """Test that summary message includes proper markers."""
        mock_summary = "This is the summary content."

        with patch.object(
            summarizer, "_summarize_local", new_callable=AsyncMock
        ) as mock_local:
            mock_local.return_value = mock_summary

            result = await summarizer.summarize(
                messages=sample_messages,
                keep_recent=2,
                provider="local",
            )

            # Find the summary message
            summary_messages = [
                m for m in result
                if m.get("role") == "system" and "summary" in m.get("content", "").lower()
            ]

            assert len(summary_messages) == 1
            summary_content = summary_messages[0]["content"]

            # Check for expected markers
            assert "[Previous conversation summary]" in summary_content
            assert "[End of summary]" in summary_content
            assert mock_summary in summary_content


class TestSummarizeLocal:
    """Tests for local (Ollama) summarization."""

    @pytest.mark.asyncio
    async def test_summarize_local_calls_ollama(self, summarizer):
        """Test that _summarize_local uses Ollama client correctly."""
        mock_response = MagicMock()
        mock_response.content = "Summarized conversation content."
        mock_response.model = "qwen2.5:14b"
        mock_response.tokens_used = 150

        mock_client = MagicMock()
        mock_client.chat = AsyncMock(return_value=mock_response)

        with patch(
            "app.app.services.summarizer.get_ollama_client",
            return_value=mock_client,
        ):
            result = await summarizer._summarize_local(
                prompt="Summarize this conversation...",
                model="qwen2.5:14b",
            )

            assert result == "Summarized conversation content."

            # Verify Ollama client was called with correct parameters
            mock_client.chat.assert_called_once()
            call_kwargs = mock_client.chat.call_args[1]

            assert call_kwargs["model"] == "qwen2.5:14b"
            assert call_kwargs["temperature"] == 0.3  # Lower for summaries
            assert call_kwargs["max_tokens"] == 1024

            # Check messages structure
            messages = call_kwargs["messages"]
            assert len(messages) == 2
            assert messages[0]["role"] == "system"
            assert messages[1]["role"] == "user"
            assert "Summarize this conversation..." in messages[1]["content"]


class TestSummarizeCloud:
    """Tests for cloud (OpenAI) summarization."""

    @pytest.mark.asyncio
    async def test_summarize_cloud_calls_openai(self, summarizer):
        """Test that _summarize_cloud uses OpenAI client correctly."""
        from app.app.schemas import ChatResponse, ChatChoice, ChatMessage, ChatUsage

        mock_response = ChatResponse(
            id="chatcmpl-123",
            model="gpt-4o-mini",
            choices=[
                ChatChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content="Cloud summarized content."),
                    finish_reason="stop",
                )
            ],
            usage=ChatUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        )

        with patch(
            "app.app.services.summarizer.call_chatgpt",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = (mock_response, None)

            result = await summarizer._summarize_cloud(
                prompt="Summarize this conversation...",
                model="gpt-4o-mini",
            )

            assert result == "Cloud summarized content."

            # Verify call_chatgpt was called
            mock_call.assert_called_once()
            request = mock_call.call_args[0][0]

            assert request.model == "gpt-4o-mini"
            assert request.temperature == 0.3
            assert request.max_tokens == 1024
            assert len(request.messages) == 2

    @pytest.mark.asyncio
    async def test_summarize_cloud_no_choices_raises(self, summarizer):
        """Test that _summarize_cloud raises on empty response."""
        from app.app.schemas import ChatResponse

        mock_response = ChatResponse(
            id="chatcmpl-123",
            model="gpt-4o-mini",
            choices=[],  # Empty choices
        )

        with patch(
            "app.app.services.summarizer.call_chatgpt",
            new_callable=AsyncMock,
        ) as mock_call:
            mock_call.return_value = (mock_response, None)

            with pytest.raises(RuntimeError, match="No content"):
                await summarizer._summarize_cloud(
                    prompt="Summarize this...",
                    model="gpt-4o-mini",
                )


class TestGetSummarizer:
    """Tests for the singleton accessor."""

    def test_get_summarizer_returns_instance(self):
        """Test that get_summarizer returns a HistorySummarizer instance."""
        summarizer = get_summarizer()
        assert isinstance(summarizer, HistorySummarizer)

    def test_get_summarizer_singleton(self):
        """Test that get_summarizer returns the same instance."""
        summarizer1 = get_summarizer()
        summarizer2 = get_summarizer()
        assert summarizer1 is summarizer2


class TestFormatConversation:
    """Tests for conversation formatting."""

    def test_format_conversation_for_summary(self, summarizer):
        """Test that conversation is formatted correctly for summarization."""
        messages = [
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": "Python is a programming language."},
        ]

        result = summarizer._format_conversation_for_summary(messages)

        assert "User: What is Python?" in result
        assert "Assistant: Python is a programming language." in result

    def test_format_conversation_empty(self, summarizer):
        """Test formatting empty message list."""
        result = summarizer._format_conversation_for_summary([])
        assert result == ""

    def test_format_conversation_missing_fields(self, summarizer):
        """Test formatting messages with missing fields."""
        messages = [
            {"role": "user"},  # Missing content
            {"content": "Hello"},  # Missing role
        ]

        # Should handle gracefully
        result = summarizer._format_conversation_for_summary(messages)
        assert "User:" in result
        assert "Unknown: Hello" in result
