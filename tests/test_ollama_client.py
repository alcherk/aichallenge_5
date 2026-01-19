"""Tests for Ollama client for local LLM inference."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.app.services.ollama_client import (
    OllamaClient,
    OllamaModel,
    OllamaResponse,
    OllamaStatus,
    ToolCall,
    format_tool_result_message,
    format_assistant_tool_call_message,
    get_ollama_client,
)


@pytest.fixture
def client():
    """Create an OllamaClient instance with test configuration."""
    return OllamaClient(
        base_url="http://localhost:11434",
        default_model="test-model",
        timeout=30,
    )


@pytest.fixture
def mock_chat_response():
    """Mock response data for chat endpoint."""
    return {
        "model": "test-model",
        "message": {
            "role": "assistant",
            "content": "This is a test response from the model.",
        },
        "done": True,
        "eval_count": 15,
        "prompt_eval_count": 10,
        "total_duration": 500_000_000,  # 500ms in nanoseconds
    }


@pytest.fixture
def mock_models_response():
    """Mock response data for models listing endpoint."""
    return {
        "models": [
            {
                "name": "llama3:8b",
                "size": 4661200640,
                "modified_at": "2024-06-15T10:30:00Z",
                "digest": "sha256:abc123",
            },
            {
                "name": "qwen2.5:14b",
                "size": 8530000000,
                "modified_at": "2024-06-14T12:00:00Z",
                "digest": "sha256:def456",
            },
            {
                "name": "mistral:7b",
                "size": 4200000000,
                "modified_at": "2024-06-13T08:00:00Z",
                "digest": "sha256:ghi789",
            },
        ]
    }


class TestOllamaClientChat:
    """Tests for OllamaClient.chat() method."""

    @pytest.mark.asyncio
    async def test_chat_returns_response(self, client, mock_chat_response):
        """Test successful chat completion returns proper OllamaResponse."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"},
        ]

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_chat_response
            mock_response.raise_for_status = MagicMock()

            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_async_client.return_value.__aenter__.return_value = mock_client_instance

            result = await client.chat(messages)

            assert isinstance(result, OllamaResponse)
            assert result.content == "This is a test response from the model."
            assert result.model == "test-model"
            assert result.tokens_used == 25  # eval_count + prompt_eval_count
            assert result.inference_time_ms == 500
            assert result.finish_reason == "stop"
            assert result.tool_calls is None

            # Verify the request was made correctly
            mock_client_instance.post.assert_called_once()
            call_args = mock_client_instance.post.call_args
            assert call_args[0][0] == "http://localhost:11434/api/chat"
            request_body = call_args[1]["json"]
            assert request_body["model"] == "test-model"
            assert request_body["messages"] == messages
            assert request_body["stream"] is False

    @pytest.mark.asyncio
    async def test_chat_with_custom_parameters(self, client, mock_chat_response):
        """Test chat with custom temperature, top_p, and max_tokens."""
        messages = [{"role": "user", "content": "Test message"}]

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_chat_response
            mock_response.raise_for_status = MagicMock()

            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_async_client.return_value.__aenter__.return_value = mock_client_instance

            await client.chat(
                messages,
                model="custom-model",
                temperature=0.3,
                top_p=0.95,
                max_tokens=1024,
            )

            request_body = mock_client_instance.post.call_args[1]["json"]
            assert request_body["model"] == "custom-model"
            assert request_body["options"]["temperature"] == 0.3
            assert request_body["options"]["top_p"] == 0.95
            assert request_body["options"]["num_predict"] == 1024

    @pytest.mark.asyncio
    async def test_chat_with_tool_calls_response(self, client):
        """Test chat returns tool calls when model invokes tools."""
        mock_response_data = {
            "model": "test-model",
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "get_weather",
                            "arguments": {"location": "San Francisco"},
                        }
                    }
                ],
            },
            "done": True,
            "eval_count": 20,
            "prompt_eval_count": 15,
            "total_duration": 300_000_000,
        }

        messages = [{"role": "user", "content": "What's the weather in SF?"}]
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get weather info",
                    "parameters": {"type": "object", "properties": {"location": {"type": "string"}}},
                },
            }
        ]

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = MagicMock()

            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_async_client.return_value.__aenter__.return_value = mock_client_instance

            result = await client.chat(messages, tools=tools)

            assert result.finish_reason == "tool_calls"
            assert result.tool_calls is not None
            assert len(result.tool_calls) == 1
            assert result.tool_calls[0].name == "get_weather"
            assert result.tool_calls[0].arguments == {"location": "San Francisco"}


class TestOllamaClientStreamChat:
    """Tests for OllamaClient.stream_chat() method."""

    @pytest.mark.asyncio
    async def test_stream_chat_yields_tokens(self, client):
        """Test streaming chat yields tokens progressively."""
        messages = [{"role": "user", "content": "Hello"}]

        # Simulate streaming response lines
        stream_lines = [
            '{"model":"test-model","message":{"content":"Hello"},"done":false}',
            '{"model":"test-model","message":{"content":" there"},"done":false}',
            '{"model":"test-model","message":{"content":"!"},"done":false}',
            '{"model":"test-model","message":{"content":""},"done":true,"eval_count":3}',
        ]

        async def mock_aiter_lines():
            for line in stream_lines:
                yield line

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_response.aiter_lines = mock_aiter_lines
            mock_response.aread = AsyncMock()

            mock_client_instance = AsyncMock()
            mock_stream_context = AsyncMock()
            mock_stream_context.__aenter__.return_value = mock_response
            mock_stream_context.__aexit__.return_value = None
            mock_client_instance.stream = MagicMock(return_value=mock_stream_context)

            mock_async_client.return_value.__aenter__.return_value = mock_client_instance

            tokens = []
            async for token in client.stream_chat(messages):
                tokens.append(token)

            assert tokens == ["Hello", " there", "!"]

    @pytest.mark.asyncio
    async def test_stream_chat_yields_tool_calls_at_end(self, client):
        """Test streaming chat yields tool calls dict at the end when tools are invoked."""
        messages = [{"role": "user", "content": "Get weather"}]
        tools = [{"type": "function", "function": {"name": "get_weather"}}]

        stream_lines = [
            '{"model":"test-model","message":{"content":""},"done":false}',
            '{"model":"test-model","message":{"tool_calls":[{"function":{"name":"get_weather","arguments":{"city":"NYC"}}}]},"done":false}',
            '{"model":"test-model","message":{"content":""},"done":true,"eval_count":5}',
        ]

        async def mock_aiter_lines():
            for line in stream_lines:
                yield line

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_response.aiter_lines = mock_aiter_lines
            mock_response.aread = AsyncMock()

            mock_client_instance = AsyncMock()
            mock_stream_context = AsyncMock()
            mock_stream_context.__aenter__.return_value = mock_response
            mock_stream_context.__aexit__.return_value = None
            mock_client_instance.stream = MagicMock(return_value=mock_stream_context)

            mock_async_client.return_value.__aenter__.return_value = mock_client_instance

            results = []
            async for item in client.stream_chat(messages, tools=tools):
                results.append(item)

            # Last item should be the tool_calls dict
            assert len(results) == 1
            assert isinstance(results[0], dict)
            assert "tool_calls" in results[0]
            assert results[0]["done"] is True
            assert len(results[0]["tool_calls"]) == 1
            assert results[0]["tool_calls"][0].name == "get_weather"

    @pytest.mark.asyncio
    async def test_stream_chat_handles_empty_lines(self, client):
        """Test streaming gracefully handles empty lines in stream."""
        messages = [{"role": "user", "content": "Test"}]

        stream_lines = [
            "",
            '{"model":"test-model","message":{"content":"Hi"},"done":false}',
            "",
            '{"model":"test-model","message":{"content":""},"done":true}',
        ]

        async def mock_aiter_lines():
            for line in stream_lines:
                yield line

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_response.aiter_lines = mock_aiter_lines
            mock_response.aread = AsyncMock()

            mock_client_instance = AsyncMock()
            mock_stream_context = AsyncMock()
            mock_stream_context.__aenter__.return_value = mock_response
            mock_stream_context.__aexit__.return_value = None
            mock_client_instance.stream = MagicMock(return_value=mock_stream_context)

            mock_async_client.return_value.__aenter__.return_value = mock_client_instance

            tokens = []
            async for token in client.stream_chat(messages):
                tokens.append(token)

            assert tokens == ["Hi"]


class TestOllamaClientHealthCheck:
    """Tests for OllamaClient.health_check() method."""

    @pytest.mark.asyncio
    async def test_health_check_available(self, client, mock_models_response):
        """Test health check returns available status when Ollama is running."""
        with patch("httpx.AsyncClient") as mock_async_client:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_models_response
            mock_response.raise_for_status = MagicMock()

            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_async_client.return_value.__aenter__.return_value = mock_client_instance

            status = await client.health_check()

            assert isinstance(status, OllamaStatus)
            assert status.available is True
            assert status.error is None
            assert len(status.models) == 3
            assert "llama3:8b" in status.models
            assert "qwen2.5:14b" in status.models
            assert "mistral:7b" in status.models

    @pytest.mark.asyncio
    async def test_health_check_unavailable_connection_error(self, client):
        """Test health check returns unavailable when Ollama is not running."""
        with patch("httpx.AsyncClient") as mock_async_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_async_client.return_value.__aenter__.return_value = mock_client_instance

            status = await client.health_check()

            assert isinstance(status, OllamaStatus)
            assert status.available is False
            assert status.models == []
            assert "Cannot connect to Ollama" in status.error

    @pytest.mark.asyncio
    async def test_health_check_unavailable_timeout(self, client):
        """Test health check returns unavailable on timeout."""
        with patch("httpx.AsyncClient") as mock_async_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                side_effect=httpx.TimeoutException("Connection timed out")
            )
            mock_async_client.return_value.__aenter__.return_value = mock_client_instance

            status = await client.health_check()

            assert isinstance(status, OllamaStatus)
            assert status.available is False
            assert status.models == []
            assert "timed out" in status.error.lower()


class TestOllamaClientListModels:
    """Tests for OllamaClient.list_models() method."""

    @pytest.mark.asyncio
    async def test_list_models(self, client, mock_models_response):
        """Test listing available models returns proper OllamaModel objects."""
        with patch("httpx.AsyncClient") as mock_async_client:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_models_response
            mock_response.raise_for_status = MagicMock()

            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_async_client.return_value.__aenter__.return_value = mock_client_instance

            models = await client.list_models()

            assert len(models) == 3
            assert all(isinstance(m, OllamaModel) for m in models)

            llama = next(m for m in models if m.name == "llama3:8b")
            assert llama.size == 4661200640
            assert llama.digest == "sha256:abc123"
            assert llama.modified_at == "2024-06-15T10:30:00Z"

    @pytest.mark.asyncio
    async def test_list_models_empty(self, client):
        """Test listing models when none are installed."""
        with patch("httpx.AsyncClient") as mock_async_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"models": []}
            mock_response.raise_for_status = MagicMock()

            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_async_client.return_value.__aenter__.return_value = mock_client_instance

            models = await client.list_models()

            assert models == []

    @pytest.mark.asyncio
    async def test_list_models_connection_error(self, client):
        """Test list_models raises on connection error."""
        with patch("httpx.AsyncClient") as mock_async_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_async_client.return_value.__aenter__.return_value = mock_client_instance

            with pytest.raises(httpx.ConnectError):
                await client.list_models()


class TestOllamaClientTimeoutHandling:
    """Tests for timeout handling in OllamaClient."""

    @pytest.mark.asyncio
    async def test_timeout_handling_chat(self, client):
        """Test chat request raises TimeoutException on timeout."""
        messages = [{"role": "user", "content": "Test"}]

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(
                side_effect=httpx.TimeoutException("Request timed out")
            )
            mock_async_client.return_value.__aenter__.return_value = mock_client_instance

            with pytest.raises(httpx.TimeoutException):
                await client.chat(messages)

    @pytest.mark.asyncio
    async def test_timeout_handling_list_models(self, client):
        """Test list_models request raises TimeoutException on timeout."""
        with patch("httpx.AsyncClient") as mock_async_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                side_effect=httpx.TimeoutException("Request timed out")
            )
            mock_async_client.return_value.__aenter__.return_value = mock_client_instance

            with pytest.raises(httpx.TimeoutException):
                await client.list_models()

    @pytest.mark.asyncio
    async def test_connection_error_raises_runtime_error(self, client):
        """Test chat converts ConnectError to RuntimeError with helpful message."""
        messages = [{"role": "user", "content": "Test"}]

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_async_client.return_value.__aenter__.return_value = mock_client_instance

            with pytest.raises(RuntimeError) as exc_info:
                await client.chat(messages)

            assert "Cannot connect to Ollama" in str(exc_info.value)


class TestOllamaClientHTTPErrors:
    """Tests for HTTP error handling."""

    @pytest.mark.asyncio
    async def test_http_status_error_raised(self, client):
        """Test HTTP errors are raised properly."""
        messages = [{"role": "user", "content": "Test"}]

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"

            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Server Error",
                request=MagicMock(),
                response=mock_response,
            )

            mock_async_client.return_value.__aenter__.return_value = mock_client_instance

            with pytest.raises(httpx.HTTPStatusError):
                await client.chat(messages)


class TestOllamaClientCancellation:
    """Tests for request cancellation."""

    def test_cancel_returns_true_when_active(self, client):
        """Test cancel returns True when there's an active request."""
        client._current_client = MagicMock()

        result = client.cancel()

        assert result is True
        assert client._cancelled is True

    def test_cancel_returns_false_when_no_request(self, client):
        """Test cancel returns False when no active request."""
        client._current_client = None

        result = client.cancel()

        assert result is False


class TestToolCallParsing:
    """Tests for tool call parsing."""

    def test_parse_tool_calls_with_function_wrapper(self, client):
        """Test parsing tool calls with function wrapper format."""
        message = {
            "tool_calls": [
                {
                    "function": {
                        "name": "get_weather",
                        "arguments": {"location": "NYC"},
                    }
                }
            ]
        }

        result = client._parse_tool_calls(message)

        assert result is not None
        assert len(result) == 1
        assert result[0].name == "get_weather"
        assert result[0].arguments == {"location": "NYC"}

    def test_parse_tool_calls_with_string_arguments(self, client):
        """Test parsing tool calls where arguments is a JSON string."""
        message = {
            "tool_calls": [
                {
                    "function": {
                        "name": "search",
                        "arguments": '{"query": "test"}',
                    }
                }
            ]
        }

        result = client._parse_tool_calls(message)

        assert result is not None
        assert len(result) == 1
        assert result[0].arguments == {"query": "test"}

    def test_parse_tool_calls_with_invalid_json_arguments(self, client):
        """Test parsing tool calls with invalid JSON arguments falls back to empty dict."""
        message = {
            "tool_calls": [
                {
                    "function": {
                        "name": "test_tool",
                        "arguments": "not valid json",
                    }
                }
            ]
        }

        result = client._parse_tool_calls(message)

        assert result is not None
        assert len(result) == 1
        assert result[0].arguments == {}

    def test_parse_tool_calls_missing_name(self, client):
        """Test parsing tool calls without name skips the entry."""
        message = {
            "tool_calls": [
                {"function": {"arguments": {"test": "value"}}},
                {"function": {"name": "valid_tool", "arguments": {}}},
            ]
        }

        result = client._parse_tool_calls(message)

        assert result is not None
        assert len(result) == 1
        assert result[0].name == "valid_tool"

    def test_parse_tool_calls_empty_list(self, client):
        """Test parsing empty tool calls returns None."""
        message = {"tool_calls": []}
        result = client._parse_tool_calls(message)
        assert result is None

    def test_parse_tool_calls_none(self, client):
        """Test parsing when no tool_calls field returns None."""
        message = {"content": "Hello"}
        result = client._parse_tool_calls(message)
        assert result is None


class TestHelperFunctions:
    """Tests for module-level helper functions."""

    def test_format_tool_result_message_success(self):
        """Test formatting successful tool result."""
        tool_call = ToolCall(
            id="call_123",
            name="get_weather",
            arguments={"location": "NYC"},
        )
        result = {"temperature": 72, "condition": "sunny"}

        message = format_tool_result_message(tool_call, result)

        assert message["role"] == "tool"
        assert json.loads(message["content"]) == result

    def test_format_tool_result_message_string_result(self):
        """Test formatting string tool result."""
        tool_call = ToolCall(id="call_123", name="search", arguments={})
        result = "Search results: item1, item2"

        message = format_tool_result_message(tool_call, result)

        assert message["role"] == "tool"
        assert message["content"] == result

    def test_format_tool_result_message_error(self):
        """Test formatting error tool result."""
        tool_call = ToolCall(id="call_123", name="failing_tool", arguments={})
        error = ValueError("Something went wrong")

        message = format_tool_result_message(tool_call, error, is_error=True)

        assert message["role"] == "tool"
        content = json.loads(message["content"])
        assert "error" in content
        assert content["error"]["type"] == "ValueError"
        assert "Something went wrong" in content["error"]["detail"]

    def test_format_assistant_tool_call_message(self):
        """Test formatting assistant message with tool calls."""
        tool_calls = [
            ToolCall(id="call_1", name="tool_a", arguments={"arg1": "val1"}),
            ToolCall(id="call_2", name="tool_b", arguments={"arg2": "val2"}),
        ]

        message = format_assistant_tool_call_message(tool_calls)

        assert message["role"] == "assistant"
        assert message["content"] == ""
        assert len(message["tool_calls"]) == 2
        assert message["tool_calls"][0]["id"] == "call_1"
        assert message["tool_calls"][0]["function"]["name"] == "tool_a"


class TestOllamaClientSingleton:
    """Tests for the singleton client getter."""

    def test_get_ollama_client_returns_instance(self):
        """Test get_ollama_client returns an OllamaClient."""
        with patch("app.app.services.ollama_client.get_settings") as mock_settings:
            mock_settings.return_value.ollama_base_url = "http://localhost:11434"
            mock_settings.return_value.ollama_default_model = "test-model"
            mock_settings.return_value.ollama_timeout = 60

            # Reset singleton
            import app.app.services.ollama_client as ollama_module
            ollama_module._client = None

            client = get_ollama_client()

            assert isinstance(client, OllamaClient)

    def test_get_ollama_client_returns_same_instance(self):
        """Test get_ollama_client returns the same instance on subsequent calls."""
        with patch("app.app.services.ollama_client.get_settings") as mock_settings:
            mock_settings.return_value.ollama_base_url = "http://localhost:11434"
            mock_settings.return_value.ollama_default_model = "test-model"
            mock_settings.return_value.ollama_timeout = 60

            # Reset singleton
            import app.app.services.ollama_client as ollama_module
            ollama_module._client = None

            client1 = get_ollama_client()
            client2 = get_ollama_client()

            assert client1 is client2


class TestOllamaDataClasses:
    """Tests for Ollama data classes."""

    def test_ollama_model_creation(self):
        """Test OllamaModel dataclass creation."""
        model = OllamaModel(
            name="llama3:8b",
            size=4661200640,
            modified_at="2024-06-15T10:30:00Z",
            digest="sha256:abc123",
        )

        assert model.name == "llama3:8b"
        assert model.size == 4661200640
        assert model.modified_at == "2024-06-15T10:30:00Z"
        assert model.digest == "sha256:abc123"

    def test_ollama_status_available(self):
        """Test OllamaStatus for available server."""
        status = OllamaStatus(
            available=True,
            models=["llama3:8b", "qwen2.5:14b"],
            error=None,
        )

        assert status.available is True
        assert len(status.models) == 2
        assert status.error is None

    def test_ollama_status_unavailable(self):
        """Test OllamaStatus for unavailable server."""
        status = OllamaStatus(
            available=False,
            models=[],
            error="Connection refused",
        )

        assert status.available is False
        assert status.models == []
        assert status.error == "Connection refused"

    def test_ollama_response_creation(self):
        """Test OllamaResponse dataclass creation."""
        response = OllamaResponse(
            content="Test response",
            model="test-model",
            tokens_used=50,
            inference_time_ms=200,
            tool_calls=None,
            finish_reason="stop",
        )

        assert response.content == "Test response"
        assert response.model == "test-model"
        assert response.tokens_used == 50
        assert response.inference_time_ms == 200
        assert response.finish_reason == "stop"

    def test_tool_call_creation(self):
        """Test ToolCall dataclass creation."""
        tool_call = ToolCall(
            id="call_123",
            name="get_weather",
            arguments={"location": "NYC"},
        )

        assert tool_call.id == "call_123"
        assert tool_call.name == "get_weather"
        assert tool_call.arguments == {"location": "NYC"}
