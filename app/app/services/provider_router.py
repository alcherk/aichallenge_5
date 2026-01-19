"""
Provider router for routing requests to appropriate LLM provider.

Supports two providers:
- "cloud": OpenAI API via existing chatgpt_client functions
- "local": Ollama via OllamaClient

Both providers are wrapped with a unified response format (ProviderResponse/StreamChunk).

Includes:
- Caching support via ResponseCache for non-streaming requests
- MCP tool calling for local models via Ollama's tool API
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncGenerator, Literal

from ..config import get_settings
from ..schemas import ChatRequest, ChatMessage
from .ollama_client import (
    OllamaClient,
    OllamaResponse,
    ToolCall,
    get_ollama_client,
    format_tool_result_message,
    format_assistant_tool_call_message,
)
from .chatgpt_client import call_chatgpt, stream_chatgpt
from .cache import ResponseCache, get_response_cache, CachedResponse
from .summarizer import HistorySummarizer, get_summarizer
from ..mcp.manager import ensure_mcp_manager, MCPManager

logger = logging.getLogger("app.provider_router")

# Maximum number of tool call rounds to prevent infinite loops
MAX_TOOL_ROUNDS = 8


@dataclass
class ProviderResponse:
    """Unified response format from any LLM provider."""

    content: str
    model: str
    provider: Literal["cloud", "local"]
    tokens_used: int | None = None
    inference_time_ms: int | None = None
    summarized: bool = False  # True if context was auto-summarized


@dataclass
class StreamChunk:
    """Unified streaming chunk format from any LLM provider."""

    delta: str
    model: str | None = None
    provider: Literal["cloud", "local"] | None = None
    done: bool = False


class ProviderRouter:
    """
    Routes requests to appropriate LLM provider.

    Provides a unified interface for both cloud (OpenAI) and local (Ollama) providers.
    The existing cloud functionality remains unchanged - this class wraps the existing
    functions without modifying them.

    Includes caching support for non-streaming requests. Cache can be bypassed
    via the `use_cache` parameter.
    """

    def __init__(
        self,
        ollama_client: OllamaClient | None = None,
        cache: ResponseCache | None = None,
        summarizer: HistorySummarizer | None = None,
    ):
        """
        Initialize the provider router.

        Args:
            ollama_client: Optional OllamaClient instance. If not provided,
                          the global singleton will be used.
            cache: Optional ResponseCache instance. If not provided,
                  the global singleton will be used.
            summarizer: Optional HistorySummarizer instance. If not provided,
                       the global singleton will be used.
        """
        self._ollama_client = ollama_client
        self._cache = cache
        self._summarizer = summarizer

    @property
    def ollama_client(self) -> OllamaClient:
        """Get or create the Ollama client."""
        if self._ollama_client is None:
            self._ollama_client = get_ollama_client()
        return self._ollama_client

    @property
    def cache(self) -> ResponseCache:
        """Get or create the response cache."""
        if self._cache is None:
            self._cache = get_response_cache()
        return self._cache

    @property
    def summarizer(self) -> HistorySummarizer:
        """Get or create the history summarizer."""
        if self._summarizer is None:
            self._summarizer = get_summarizer()
        return self._summarizer

    async def chat(
        self,
        messages: list[dict],
        provider: Literal["cloud", "local"] = "cloud",
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        use_cache: bool = True,
        **kwargs,
    ) -> ProviderResponse:
        """
        Route chat request to appropriate provider.

        Args:
            messages: List of message dicts with 'role' and 'content'
            provider: Provider to use ("cloud" or "local")
            model: Model name (uses provider default if not specified)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            use_cache: Whether to use caching (default True). Set to False
                      to bypass cache for this request.
            **kwargs: Additional provider-specific options

        Returns:
            ProviderResponse with unified format

        Raises:
            RuntimeError: On provider errors
            httpx.TimeoutException: On timeout (local provider)
            httpx.HTTPStatusError: On HTTP errors
        """
        start_time = time.monotonic()

        # Determine effective model name for cache key
        effective_model = model
        if effective_model is None:
            if provider == "local":
                effective_model = self.ollama_client.default_model
            else:
                effective_model = "cloud-default"

        logger.info(
            "Router chat request: provider=%s model=%s messages=%d temperature=%.2f use_cache=%s",
            provider,
            effective_model,
            len(messages),
            temperature,
            use_cache,
        )

        # Auto-summarize if context is approaching limit
        auto_summarize = kwargs.get("auto_summarize", True)
        summarize_threshold = kwargs.get("summarize_threshold", 0.85)
        summarized = False
        working_messages = messages

        if auto_summarize:
            should_summarize = await self.summarizer.should_summarize(
                messages=messages,
                model=effective_model,
                threshold=summarize_threshold,
            )
            if should_summarize:
                logger.info(
                    "Context approaching limit, auto-summarizing %d messages",
                    len(messages),
                )
                working_messages = await self.summarizer.summarize(
                    messages=messages,
                    keep_recent=4,
                    provider=provider,
                    model=effective_model,
                )
                summarized = len(working_messages) < len(messages)
                if summarized:
                    logger.info(
                        "Summarization reduced messages: %d -> %d",
                        len(messages),
                        len(working_messages),
                    )

        # Check cache if enabled (use working_messages for cache key)
        cache_key: str | None = None
        if use_cache:
            cache_params = {
                "provider": provider,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            cache_key = self.cache.cache_key(effective_model, working_messages, cache_params)

            cached = await self.cache.get(cache_key)
            if cached is not None:
                logger.info(
                    "Cache hit for key=%s model=%s provider=%s",
                    cache_key[:16],
                    cached.model,
                    cached.provider,
                )
                return ProviderResponse(
                    content=cached.content,
                    model=cached.model,
                    provider=cached.provider,  # type: ignore
                    tokens_used=cached.metadata.get("tokens_used"),
                    inference_time_ms=cached.metadata.get("inference_time_ms"),
                    summarized=summarized,  # Pass through summarization state
                )

        # Call the appropriate provider (use working_messages which may be summarized)
        if provider == "local":
            response = await self._chat_local(
                messages=working_messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
        else:
            response = await self._chat_cloud(
                messages=working_messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                start_time=start_time,
                **kwargs,
            )

        # Store in cache if enabled
        if use_cache and cache_key is not None:
            await self.cache.set(
                key=cache_key,
                response=response.content,
                model=response.model,
                provider=response.provider,
                metadata={
                    "tokens_used": response.tokens_used,
                    "inference_time_ms": response.inference_time_ms,
                },
            )
            logger.debug(
                "Cached response for key=%s model=%s",
                cache_key[:16],
                response.model,
            )

        # Update response with summarization flag
        response.summarized = summarized
        return response

    async def _chat_local(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> ProviderResponse:
        """
        Execute chat via local Ollama provider with optional MCP tool support.

        If mcp_enabled is True and tools are available, the model can invoke
        MCP tools and we'll execute a multi-turn conversation loop.
        """
        # Extract Ollama-specific options
        top_p = kwargs.get("top_p", 0.9)

        # Extract MCP options
        mcp_enabled = kwargs.get("mcp_enabled", False)
        mcp_config_path = kwargs.get("mcp_config_path")
        workspace_root = kwargs.get("workspace_root")

        # Get MCP manager and tools if MCP is enabled
        mcp_manager: MCPManager | None = None
        tools: list[dict] | None = None

        if mcp_enabled:
            settings = get_settings()
            workspace_path = Path(workspace_root) if workspace_root else Path(settings.workspace_root)

            try:
                mcp_manager = await ensure_mcp_manager(
                    mcp_config_path=mcp_config_path or settings.mcp_config_path,
                    workspace_root=workspace_path,
                )
                if mcp_manager:
                    tools = mcp_manager.openai_tools()
                    if tools:
                        logger.info(
                            "MCP tools enabled for local model: %d tools available",
                            len(tools),
                        )
            except Exception as e:
                logger.warning("Failed to initialize MCP for local model: %s", e)
                # Continue without tools

        # Build working copy of messages for potential tool loop
        working_messages = list(messages)
        total_tokens = 0
        total_inference_time_ms = 0

        # Tool execution loop
        for round_num in range(MAX_TOOL_ROUNDS):
            response = await self.ollama_client.chat(
                messages=working_messages,
                model=model,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens or 2048,
                tools=tools,
            )

            # Accumulate metrics
            if response.tokens_used:
                total_tokens += response.tokens_used
            if response.inference_time_ms:
                total_inference_time_ms += response.inference_time_ms

            # Check if model wants to call tools
            if response.tool_calls and mcp_manager:
                logger.info(
                    "Local model requested %d tool calls (round %d)",
                    len(response.tool_calls),
                    round_num + 1,
                )

                # Add assistant message with tool calls to history
                working_messages.append(format_assistant_tool_call_message(response.tool_calls))

                # Execute each tool call
                for tool_call in response.tool_calls:
                    try:
                        result = await self._execute_tool_call(mcp_manager, tool_call)
                        working_messages.append(
                            format_tool_result_message(tool_call, result, is_error=False)
                        )
                        logger.debug(
                            "Tool %s executed successfully",
                            tool_call.name,
                        )
                    except Exception as e:
                        logger.error(
                            "Tool %s failed: %s",
                            tool_call.name,
                            e,
                        )
                        working_messages.append(
                            format_tool_result_message(tool_call, e, is_error=True)
                        )

                # Continue to next round
                continue

            # No tool calls - we have the final response
            logger.info(
                "Router local chat completed: model=%s tokens=%s time=%sms rounds=%d",
                response.model,
                total_tokens or response.tokens_used,
                total_inference_time_ms or response.inference_time_ms,
                round_num + 1,
            )

            return ProviderResponse(
                content=response.content,
                model=response.model,
                provider="local",
                tokens_used=total_tokens or response.tokens_used,
                inference_time_ms=total_inference_time_ms or response.inference_time_ms,
            )

        # Exceeded max rounds - return last response with warning
        logger.warning(
            "Local model tool loop exceeded %d rounds, returning last response",
            MAX_TOOL_ROUNDS,
        )
        return ProviderResponse(
            content=response.content + "\n\n[Warning: Tool execution limit reached]",
            model=response.model,
            provider="local",
            tokens_used=total_tokens,
            inference_time_ms=total_inference_time_ms,
        )

    async def _execute_tool_call(
        self,
        mcp_manager: MCPManager,
        tool_call: ToolCall,
    ) -> Any:
        """
        Execute a single tool call via MCP manager.

        Args:
            mcp_manager: The MCP manager to use for tool execution
            tool_call: The tool call to execute

        Returns:
            The result from the tool execution

        Raises:
            RuntimeError: If the tool is unknown or execution fails
        """
        logger.debug(
            "Executing tool call: name=%s args=%s",
            tool_call.name,
            list(tool_call.arguments.keys()) if tool_call.arguments else [],
        )

        return await mcp_manager.call_openai_tool(
            tool_call.name,
            tool_call.arguments,
        )

    async def _chat_cloud(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        start_time: float | None = None,
        **kwargs,
    ) -> ProviderResponse:
        """Execute chat via cloud OpenAI provider."""
        # Convert messages to ChatRequest format
        chat_messages = [
            ChatMessage(role=m["role"], content=m["content"]) for m in messages
        ]

        payload = ChatRequest(
            messages=chat_messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            # Pass through any additional options
            mcp_enabled=kwargs.get("mcp_enabled"),
            mcp_config_path=kwargs.get("mcp_config_path"),
            workspace_root=kwargs.get("workspace_root"),
            assistant_mode=kwargs.get("assistant_mode"),
        )

        # Call existing cloud function
        response, rag_metadata = await call_chatgpt(payload)

        # Calculate inference time if we have start_time
        inference_time_ms = None
        if start_time is not None:
            inference_time_ms = int((time.monotonic() - start_time) * 1000)

        # Extract content from ChatResponse
        content = ""
        if response.choices:
            content = response.choices[0].message.content

        # Extract token usage
        tokens_used = None
        if response.usage:
            tokens_used = response.usage.total_tokens

        logger.info(
            "Router cloud chat completed: model=%s tokens=%s time=%sms",
            response.model,
            tokens_used,
            inference_time_ms,
        )

        return ProviderResponse(
            content=content,
            model=response.model,
            provider="cloud",
            tokens_used=tokens_used,
            inference_time_ms=inference_time_ms,
        )

    async def stream_chat(
        self,
        messages: list[dict],
        provider: Literal["cloud", "local"] = "cloud",
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        use_cache: bool = True,
        **kwargs,
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Route streaming chat to appropriate provider.

        Args:
            messages: List of message dicts with 'role' and 'content'
            provider: Provider to use ("cloud" or "local")
            model: Model name (uses provider default if not specified)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            use_cache: Whether to cache the final result (default True).
                      The accumulated response will be cached after streaming completes.
            **kwargs: Additional provider-specific options

        Yields:
            StreamChunk with unified format

        Raises:
            RuntimeError: On provider errors
            httpx.TimeoutException: On timeout
            httpx.HTTPStatusError: On HTTP errors
        """
        start_time = time.monotonic()

        # Determine effective model name for cache key
        effective_model = model
        if effective_model is None:
            if provider == "local":
                effective_model = self.ollama_client.default_model
            else:
                effective_model = "cloud-default"

        logger.info(
            "Router stream request: provider=%s model=%s messages=%d use_cache=%s",
            provider,
            effective_model,
            len(messages),
            use_cache,
        )

        # Auto-summarize if context is approaching limit
        auto_summarize = kwargs.get("auto_summarize", True)
        summarize_threshold = kwargs.get("summarize_threshold", 0.85)
        working_messages = messages

        if auto_summarize:
            should_summarize = await self.summarizer.should_summarize(
                messages=messages,
                model=effective_model,
                threshold=summarize_threshold,
            )
            if should_summarize:
                logger.info(
                    "Context approaching limit for stream, auto-summarizing %d messages",
                    len(messages),
                )
                working_messages = await self.summarizer.summarize(
                    messages=messages,
                    keep_recent=4,
                    provider=provider,
                    model=effective_model,
                )
                if len(working_messages) < len(messages):
                    logger.info(
                        "Summarization reduced messages for stream: %d -> %d",
                        len(messages),
                        len(working_messages),
                    )

        # Prepare cache key if caching is enabled (use working_messages)
        cache_key: str | None = None
        if use_cache:
            cache_params = {
                "provider": provider,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            cache_key = self.cache.cache_key(effective_model, working_messages, cache_params)

            # Check cache - if hit, yield cached content as a single chunk
            cached = await self.cache.get(cache_key)
            if cached is not None:
                logger.info(
                    "Cache hit for streaming key=%s model=%s provider=%s",
                    cache_key[:16],
                    cached.model,
                    cached.provider,
                )
                # Yield the cached content as a single chunk
                yield StreamChunk(
                    delta=cached.content,
                    model=cached.model,
                    provider=cached.provider,  # type: ignore
                    done=False,
                )
                # Yield done chunk
                yield StreamChunk(
                    delta="",
                    model=cached.model,
                    provider=cached.provider,  # type: ignore
                    done=True,
                )
                return

        # Accumulate content for caching
        accumulated_content: list[str] = []
        actual_model: str | None = effective_model

        # Stream from provider (use working_messages which may be summarized)
        if provider == "local":
            stream = self._stream_local(
                messages=working_messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
        else:
            stream = self._stream_cloud(
                messages=working_messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )

        async for chunk in stream:
            # Track model from response
            if chunk.model:
                actual_model = chunk.model

            # Accumulate content for caching
            if chunk.delta:
                accumulated_content.append(chunk.delta)

            yield chunk

        # Cache the accumulated result if caching is enabled
        if use_cache and cache_key is not None and accumulated_content:
            full_content = "".join(accumulated_content)
            inference_time_ms = int((time.monotonic() - start_time) * 1000)

            await self.cache.set(
                key=cache_key,
                response=full_content,
                model=actual_model or effective_model,
                provider=provider,
                metadata={
                    "tokens_used": None,  # Token count not available for streaming
                    "inference_time_ms": inference_time_ms,
                },
            )
            logger.debug(
                "Cached streamed response for key=%s model=%s chars=%d",
                cache_key[:16],
                actual_model,
                len(full_content),
            )

    async def _stream_local(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream via local Ollama provider."""
        # Extract Ollama-specific options
        top_p = kwargs.get("top_p", 0.9)

        # Use model from client if not specified
        actual_model = model or self.ollama_client.default_model

        # Stream from Ollama - it yields raw string tokens
        async for token in self.ollama_client.stream_chat(
            messages=messages,
            model=model,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens or 2048,
        ):
            yield StreamChunk(
                delta=token,
                model=actual_model,
                provider="local",
                done=False,
            )

        # Send final done chunk
        yield StreamChunk(
            delta="",
            model=actual_model,
            provider="local",
            done=True,
        )

        logger.debug("Router local stream completed: model=%s", actual_model)

    async def _stream_cloud(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream via cloud OpenAI provider."""
        # Convert messages to ChatRequest format
        chat_messages = [
            ChatMessage(role=m["role"], content=m["content"]) for m in messages
        ]

        payload = ChatRequest(
            messages=chat_messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            # Pass through any additional options
            mcp_enabled=kwargs.get("mcp_enabled"),
            mcp_config_path=kwargs.get("mcp_config_path"),
            workspace_root=kwargs.get("workspace_root"),
            assistant_mode=kwargs.get("assistant_mode"),
        )

        # Track model from response
        actual_model: str | None = model

        # Stream from cloud - it yields dicts with choices/delta structure
        async for event in stream_chatgpt(payload):
            # Extract model from initial response.created event
            if "model" in event and event.get("model"):
                actual_model = event["model"]

            # Extract delta content from choices
            choices = event.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                content = delta.get("content", "")

                if content:
                    yield StreamChunk(
                        delta=content,
                        model=actual_model,
                        provider="cloud",
                        done=False,
                    )

        # Send final done chunk
        yield StreamChunk(
            delta="",
            model=actual_model,
            provider="cloud",
            done=True,
        )

        logger.debug("Router cloud stream completed: model=%s", actual_model)


# Module-level singleton for convenience
_router: ProviderRouter | None = None


def get_provider_router() -> ProviderRouter:
    """
    Get or create the global ProviderRouter instance.

    Returns:
        Singleton ProviderRouter instance
    """
    global _router
    if _router is None:
        _router = ProviderRouter()
    return _router
