"""
Ollama client for local LLM inference.

Provides an OpenAI-compatible interface for Ollama, supporting:
- Non-streaming chat completions
- Streaming chat completions
- Health checks
- Model listing
- Tool calling (MCP integration)
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

import httpx

from ..config import get_settings

logger = logging.getLogger("app.ollama")


@dataclass
class OllamaModel:
    """Represents an Ollama model with metadata."""
    name: str
    size: int
    modified_at: str
    digest: str


@dataclass
class OllamaStatus:
    """Health check status for Ollama server."""
    available: bool
    models: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class ToolCall:
    """Represents a tool call request from the model."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class OllamaResponse:
    """Response from Ollama chat completion."""
    content: str
    model: str
    tokens_used: int | None = None
    inference_time_ms: int | None = None
    tool_calls: list[ToolCall] | None = None
    finish_reason: str = "stop"


class OllamaClient:
    """
    OpenAI-compatible client for Ollama.

    Uses the Ollama API at /api/chat for chat completions and /api/tags for model listing.
    Supports both streaming and non-streaming modes.
    """

    def __init__(
        self,
        base_url: str | None = None,
        default_model: str | None = None,
        timeout: int | None = None,
    ):
        """
        Initialize Ollama client.

        Args:
            base_url: Ollama server URL (default: from settings)
            default_model: Default model to use (default: from settings)
            timeout: Request timeout in seconds (default: from settings)
        """
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.default_model = default_model or settings.ollama_default_model
        self.timeout = timeout or settings.ollama_timeout

        # Track current request for potential cancellation
        self._current_client: httpx.AsyncClient | None = None
        self._cancelled = False

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 2048,
        tools: list[dict] | None = None,
        options: dict[str, Any] | None = None,
    ) -> OllamaResponse:
        """
        Non-streaming chat completion.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name (default: client's default_model)
            temperature: Sampling temperature (0.0 to 1.0)
            top_p: Top-p sampling parameter
            max_tokens: Maximum tokens to generate
            tools: Optional list of tool definitions in OpenAI format
            options: Optional additional Ollama options (num_ctx, repeat_penalty, etc.)

        Returns:
            OllamaResponse with content, metadata, and optional tool_calls

        Raises:
            httpx.TimeoutException: On request timeout
            httpx.HTTPStatusError: On HTTP errors
            RuntimeError: On connection errors or invalid responses
        """
        model = model or self.default_model
        url = f"{self.base_url}/api/chat"

        # Build options dict with defaults and overrides
        ollama_options: dict[str, Any] = {
            "temperature": temperature,
            "top_p": top_p,
            "num_predict": max_tokens,
        }
        # Merge additional options if provided
        if options:
            ollama_options.update(options)

        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": ollama_options,
        }

        # Add tools if provided (Ollama uses OpenAI-compatible format)
        if tools:
            body["tools"] = tools
            logger.debug("Ollama chat with %d tools", len(tools))

        logger.debug(
            "Ollama chat request: model=%s messages=%d temperature=%.2f tools=%d",
            model,
            len(messages),
            temperature,
            len(tools) if tools else 0,
        )

        start_time = time.monotonic()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                self._current_client = client
                self._cancelled = False

                response = await client.post(url, json=body)
                response.raise_for_status()
                data = response.json()

        except httpx.TimeoutException as e:
            logger.error("Ollama request timed out after %ds: %s", self.timeout, e)
            raise
        except httpx.ConnectError as e:
            logger.error("Failed to connect to Ollama at %s: %s", self.base_url, e)
            raise RuntimeError(f"Cannot connect to Ollama at {self.base_url}: {e}") from e
        except httpx.HTTPStatusError as e:
            logger.error(
                "Ollama HTTP error: status=%d body=%s",
                e.response.status_code,
                e.response.text[:500] if e.response.text else "empty",
            )
            raise
        finally:
            self._current_client = None

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        # Parse response
        message = data.get("message", {})
        content = message.get("content", "")

        # Parse tool calls from response
        tool_calls = self._parse_tool_calls(message)
        finish_reason = "tool_calls" if tool_calls else "stop"

        # Extract token counts (Ollama provides eval_count for output tokens)
        eval_count = data.get("eval_count")
        prompt_eval_count = data.get("prompt_eval_count")
        tokens_used = None
        if eval_count is not None or prompt_eval_count is not None:
            tokens_used = (eval_count or 0) + (prompt_eval_count or 0)

        # Ollama provides total_duration in nanoseconds
        total_duration_ns = data.get("total_duration")
        inference_time_ms = None
        if total_duration_ns is not None:
            inference_time_ms = int(total_duration_ns / 1_000_000)

        logger.info(
            "Ollama chat completed: model=%s tokens=%s time=%dms tool_calls=%d",
            data.get("model", model),
            tokens_used,
            inference_time_ms or elapsed_ms,
            len(tool_calls) if tool_calls else 0,
        )

        return OllamaResponse(
            content=content,
            model=data.get("model", model),
            tokens_used=tokens_used,
            inference_time_ms=inference_time_ms,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
        )

    def _parse_tool_calls(self, message: dict) -> list[ToolCall] | None:
        """
        Parse tool calls from Ollama response message.

        Ollama returns tool calls in the message's tool_calls field:
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "function": {
                        "name": "tool_name",
                        "arguments": {"arg1": "value1"}
                    }
                }
            ]
        }

        Args:
            message: Response message dict from Ollama

        Returns:
            List of ToolCall objects, or None if no tool calls
        """
        raw_tool_calls = message.get("tool_calls")
        if not raw_tool_calls:
            return None

        tool_calls = []
        for i, tc in enumerate(raw_tool_calls):
            try:
                # Handle different Ollama tool call formats
                if isinstance(tc, dict):
                    function_data = tc.get("function", tc)
                    name = function_data.get("name")

                    if not name:
                        logger.warning("Tool call missing name: %s", tc)
                        continue

                    # Parse arguments - can be string or dict
                    args_raw = function_data.get("arguments", {})
                    if isinstance(args_raw, str):
                        try:
                            arguments = json.loads(args_raw)
                        except json.JSONDecodeError:
                            logger.warning(
                                "Failed to parse tool arguments as JSON: %s",
                                args_raw[:200] if len(args_raw) > 200 else args_raw,
                            )
                            arguments = {}
                    elif isinstance(args_raw, dict):
                        arguments = args_raw
                    else:
                        arguments = {}

                    # Generate a unique ID for the tool call
                    tool_call_id = tc.get("id") or f"call_{i}_{int(time.time() * 1000)}"

                    tool_calls.append(ToolCall(
                        id=tool_call_id,
                        name=name,
                        arguments=arguments,
                    ))
                    logger.debug(
                        "Parsed tool call: id=%s name=%s args=%s",
                        tool_call_id,
                        name,
                        list(arguments.keys()) if arguments else [],
                    )
            except Exception as e:
                logger.error("Error parsing tool call %d: %s", i, e, exc_info=True)
                # Continue parsing other tool calls

        return tool_calls if tool_calls else None

    async def stream_chat(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 2048,
        tools: list[dict] | None = None,
        options: dict[str, Any] | None = None,
    ) -> AsyncGenerator[str | dict, None]:
        """
        Streaming chat completion that yields tokens or tool calls.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name (default: client's default_model)
            temperature: Sampling temperature (0.0 to 1.0)
            top_p: Top-p sampling parameter
            max_tokens: Maximum tokens to generate
            tools: Optional list of tool definitions in OpenAI format
            options: Optional additional Ollama options (num_ctx, repeat_penalty, etc.)

        Yields:
            String tokens as they are generated, or a dict with tool_calls at the end

        Raises:
            httpx.TimeoutException: On request timeout
            httpx.HTTPStatusError: On HTTP errors
            RuntimeError: On connection errors

        Note:
            When tools are used and the model decides to call a tool, the final
            yield will be a dict: {"tool_calls": [ToolCall, ...], "done": True}
            instead of a string token.
        """
        model = model or self.default_model
        url = f"{self.base_url}/api/chat"

        # Build options dict with defaults and overrides
        ollama_options: dict[str, Any] = {
            "temperature": temperature,
            "top_p": top_p,
            "num_predict": max_tokens,
        }
        # Merge additional options if provided
        if options:
            ollama_options.update(options)

        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": ollama_options,
        }

        # Add tools if provided
        if tools:
            body["tools"] = tools
            logger.debug("Ollama stream with %d tools", len(tools))

        logger.debug(
            "Ollama stream request: model=%s messages=%d tools=%d",
            model,
            len(messages),
            len(tools) if tools else 0,
        )

        # Accumulate tool calls during streaming
        accumulated_tool_calls: list[dict] = []

        try:
            # Use timeout=None for streaming to allow long generations
            async with httpx.AsyncClient(timeout=None) as client:
                self._current_client = client
                self._cancelled = False

                async with client.stream("POST", url, json=body) as response:
                    if response.status_code >= 400:
                        await response.aread()
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if self._cancelled:
                            logger.info("Ollama stream cancelled by user")
                            return

                        if not line:
                            continue

                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            logger.warning("Invalid JSON in Ollama stream: %s", line[:100])
                            continue

                        # Check if done
                        if data.get("done", False):
                            logger.debug(
                                "Ollama stream completed: model=%s eval_count=%s tool_calls=%d",
                                data.get("model"),
                                data.get("eval_count"),
                                len(accumulated_tool_calls),
                            )

                            # If we accumulated tool calls, yield them at the end
                            if accumulated_tool_calls:
                                parsed_calls = []
                                for tc in accumulated_tool_calls:
                                    parsed = self._parse_single_tool_call(tc)
                                    if parsed:
                                        parsed_calls.append(parsed)

                                if parsed_calls:
                                    yield {"tool_calls": parsed_calls, "done": True}
                            return

                        # Extract message from response
                        message = data.get("message", {})

                        # Check for tool calls in streaming response
                        tool_calls_data = message.get("tool_calls")
                        if tool_calls_data:
                            # Accumulate tool calls for final yield
                            if isinstance(tool_calls_data, list):
                                accumulated_tool_calls.extend(tool_calls_data)
                            continue

                        # Extract token from message
                        content = message.get("content", "")

                        if content:
                            yield content

        except httpx.ConnectError as e:
            logger.error("Failed to connect to Ollama at %s: %s", self.base_url, e)
            raise RuntimeError(f"Cannot connect to Ollama at {self.base_url}: {e}") from e
        except httpx.HTTPStatusError as e:
            logger.error(
                "Ollama HTTP error during stream: status=%d",
                e.response.status_code,
            )
            raise
        finally:
            self._current_client = None

    def _parse_single_tool_call(self, tc: dict) -> ToolCall | None:
        """
        Parse a single tool call dict into a ToolCall object.

        Args:
            tc: Raw tool call dict from Ollama

        Returns:
            ToolCall object or None if parsing fails
        """
        try:
            function_data = tc.get("function", tc)
            name = function_data.get("name")

            if not name:
                logger.warning("Tool call missing name: %s", tc)
                return None

            # Parse arguments
            args_raw = function_data.get("arguments", {})
            if isinstance(args_raw, str):
                try:
                    arguments = json.loads(args_raw)
                except json.JSONDecodeError:
                    logger.warning("Failed to parse tool arguments: %s", args_raw[:100])
                    arguments = {}
            elif isinstance(args_raw, dict):
                arguments = args_raw
            else:
                arguments = {}

            tool_call_id = tc.get("id") or f"call_{int(time.time() * 1000)}"

            return ToolCall(
                id=tool_call_id,
                name=name,
                arguments=arguments,
            )
        except Exception as e:
            logger.error("Error parsing tool call: %s", e)
            return None

    async def health_check(self) -> OllamaStatus:
        """
        Check Ollama availability and list available models.

        Returns:
            OllamaStatus with availability and model list
        """
        try:
            models = await self.list_models()
            model_names = [m.name for m in models]

            logger.info("Ollama health check passed: %d models available", len(models))

            return OllamaStatus(
                available=True,
                models=model_names,
                error=None,
            )

        except httpx.ConnectError as e:
            error_msg = f"Cannot connect to Ollama at {self.base_url}"
            logger.warning("Ollama health check failed: %s", error_msg)
            return OllamaStatus(
                available=False,
                models=[],
                error=error_msg,
            )
        except httpx.TimeoutException as e:
            error_msg = f"Connection to Ollama timed out after {self.timeout}s"
            logger.warning("Ollama health check failed: %s", error_msg)
            return OllamaStatus(
                available=False,
                models=[],
                error=error_msg,
            )
        except Exception as e:
            error_msg = f"Ollama health check error: {type(e).__name__}: {e}"
            logger.warning("Ollama health check failed: %s", error_msg)
            return OllamaStatus(
                available=False,
                models=[],
                error=error_msg,
            )

    async def get_model_info(self, model: str | None = None) -> dict[str, Any]:
        """
        Get detailed model information including context limits.

        Uses Ollama's /api/show endpoint to retrieve model details.

        Args:
            model: Model name (default: client's default_model)

        Returns:
            Dict with model info including:
            - name: Model name
            - context_length: Maximum context window size
            - default_num_ctx: Default context size
            - parameters: Model parameters
            - size: Model size in bytes
            - modified_at: Last modification timestamp

        Raises:
            httpx.ConnectError: On connection failure
            httpx.TimeoutException: On timeout
            httpx.HTTPStatusError: On HTTP errors
        """
        model = model or self.default_model
        url = f"{self.base_url}/api/show"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json={"name": model})
                response.raise_for_status()
                data = response.json()

        except httpx.ConnectError as e:
            logger.error("Failed to connect to Ollama at %s: %s", self.base_url, e)
            raise
        except httpx.TimeoutException as e:
            logger.error("Ollama get_model_info timed out: %s", e)
            raise
        except httpx.HTTPStatusError as e:
            logger.error(
                "Ollama get_model_info HTTP error: status=%d",
                e.response.status_code,
            )
            raise

        # Extract context length from model info
        # Ollama stores this in modelfile parameters or model_info
        model_info = data.get("model_info", {})
        parameters = data.get("parameters", "")

        # Try to extract context length from various sources
        context_length = 4096  # Default fallback

        # Check model_info for context_length key
        for key in model_info:
            if "context" in key.lower():
                try:
                    context_length = int(model_info[key])
                    break
                except (ValueError, TypeError):
                    pass

        # Check parameters string for num_ctx
        if isinstance(parameters, str) and "num_ctx" in parameters:
            import re
            match = re.search(r'num_ctx\s+(\d+)', parameters)
            if match:
                context_length = int(match.group(1))

        # Some models report context_length directly
        if "context_length" in data:
            try:
                context_length = int(data["context_length"])
            except (ValueError, TypeError):
                pass

        logger.debug(
            "Model info for %s: context_length=%d",
            model,
            context_length,
        )

        return {
            "name": model,
            "context_length": context_length,
            "default_num_ctx": context_length,  # Same as max for now
            "parameters": data.get("parameters"),
            "size": data.get("size"),
            "modified_at": data.get("modified_at"),
            "template": data.get("template"),
            "modelfile": data.get("modelfile"),
            "details": data.get("details", {}),
        }

    async def list_models(self) -> list[OllamaModel]:
        """
        List available Ollama models with details.

        Returns:
            List of OllamaModel objects

        Raises:
            httpx.ConnectError: On connection failure
            httpx.TimeoutException: On timeout
            httpx.HTTPStatusError: On HTTP errors
        """
        url = f"{self.base_url}/api/tags"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

        except httpx.ConnectError as e:
            logger.error("Failed to connect to Ollama at %s: %s", self.base_url, e)
            raise
        except httpx.TimeoutException as e:
            logger.error("Ollama list models timed out: %s", e)
            raise

        models_data = data.get("models", [])
        models = []

        for m in models_data:
            if not isinstance(m, dict):
                continue

            name = m.get("name", "")
            if not name:
                continue

            models.append(OllamaModel(
                name=name,
                size=m.get("size", 0),
                modified_at=m.get("modified_at", ""),
                digest=m.get("digest", ""),
            ))

        logger.debug("Ollama list_models: found %d models", len(models))
        return models

    def cancel(self) -> bool:
        """
        Cancel current generation (if possible).

        Note: Ollama doesn't have a native cancel API, so this sets a flag
        that causes the stream to stop reading. For non-streaming requests,
        cancellation is not supported.

        Returns:
            True if cancellation was signaled, False otherwise
        """
        if self._current_client is not None:
            self._cancelled = True
            logger.info("Ollama cancellation requested")
            return True

        logger.debug("Ollama cancel called but no active request")
        return False


def format_tool_result_message(
    tool_call: ToolCall,
    result: Any,
    is_error: bool = False,
) -> dict:
    """
    Format a tool execution result as an Ollama tool message.

    Ollama expects tool results in this format:
    {
        "role": "tool",
        "content": "result string",
        "tool_call_id": "call_id"  # optional, for tracking
    }

    Args:
        tool_call: The tool call that was executed
        result: The result from the tool execution
        is_error: Whether the result is an error

    Returns:
        Dict formatted as an Ollama tool message
    """
    if is_error:
        content = json.dumps(
            {"error": {"type": type(result).__name__ if isinstance(result, Exception) else "Error", "detail": str(result)}},
            ensure_ascii=False,
        )
    else:
        if isinstance(result, str):
            content = result
        else:
            try:
                content = json.dumps(result, ensure_ascii=False)
            except (TypeError, ValueError):
                content = str(result)

    return {
        "role": "tool",
        "content": content,
        # Note: Some Ollama versions may not use tool_call_id, but we include it for compatibility
    }


def format_assistant_tool_call_message(tool_calls: list[ToolCall]) -> dict:
    """
    Format tool calls as an assistant message for conversation history.

    When the model makes tool calls, we need to include them in the conversation
    history for the next turn.

    Args:
        tool_calls: List of tool calls made by the model

    Returns:
        Dict formatted as an assistant message with tool_calls
    """
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": tc.id,
                "function": {
                    "name": tc.name,
                    "arguments": tc.arguments if isinstance(tc.arguments, str) else json.dumps(tc.arguments),
                },
            }
            for tc in tool_calls
        ],
    }


# Module-level singleton for convenience
_client: OllamaClient | None = None


def get_ollama_client() -> OllamaClient:
    """
    Get or create the global Ollama client instance.

    Returns:
        Singleton OllamaClient instance
    """
    global _client
    if _client is None:
        _client = OllamaClient()
    return _client
