"""
Provider router for routing requests to appropriate LLM provider.

Supports two providers:
- "cloud": OpenAI API via existing chatgpt_client functions
- "local": Ollama via OllamaClient

Both providers are wrapped with a unified response format (ProviderResponse/StreamChunk).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import AsyncGenerator, Literal

from ..schemas import ChatRequest, ChatMessage
from .ollama_client import OllamaClient, get_ollama_client
from .chatgpt_client import call_chatgpt, stream_chatgpt

logger = logging.getLogger("app.provider_router")


@dataclass
class ProviderResponse:
    """Unified response format from any LLM provider."""

    content: str
    model: str
    provider: Literal["cloud", "local"]
    tokens_used: int | None = None
    inference_time_ms: int | None = None


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
    """

    def __init__(self, ollama_client: OllamaClient | None = None):
        """
        Initialize the provider router.

        Args:
            ollama_client: Optional OllamaClient instance. If not provided,
                          the global singleton will be used.
        """
        self._ollama_client = ollama_client

    @property
    def ollama_client(self) -> OllamaClient:
        """Get or create the Ollama client."""
        if self._ollama_client is None:
            self._ollama_client = get_ollama_client()
        return self._ollama_client

    async def chat(
        self,
        messages: list[dict],
        provider: Literal["cloud", "local"] = "cloud",
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
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
            **kwargs: Additional provider-specific options

        Returns:
            ProviderResponse with unified format

        Raises:
            RuntimeError: On provider errors
            httpx.TimeoutException: On timeout (local provider)
            httpx.HTTPStatusError: On HTTP errors
        """
        start_time = time.monotonic()

        logger.info(
            "Router chat request: provider=%s model=%s messages=%d temperature=%.2f",
            provider,
            model,
            len(messages),
            temperature,
        )

        if provider == "local":
            return await self._chat_local(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
        else:
            return await self._chat_cloud(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                start_time=start_time,
                **kwargs,
            )

    async def _chat_local(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> ProviderResponse:
        """Execute chat via local Ollama provider."""
        # Extract Ollama-specific options
        top_p = kwargs.get("top_p", 0.9)

        # Call Ollama
        response = await self.ollama_client.chat(
            messages=messages,
            model=model,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens or 2048,
        )

        logger.info(
            "Router local chat completed: model=%s tokens=%s time=%sms",
            response.model,
            response.tokens_used,
            response.inference_time_ms,
        )

        return ProviderResponse(
            content=response.content,
            model=response.model,
            provider="local",
            tokens_used=response.tokens_used,
            inference_time_ms=response.inference_time_ms,
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
            **kwargs: Additional provider-specific options

        Yields:
            StreamChunk with unified format

        Raises:
            RuntimeError: On provider errors
            httpx.TimeoutException: On timeout
            httpx.HTTPStatusError: On HTTP errors
        """
        logger.info(
            "Router stream request: provider=%s model=%s messages=%d",
            provider,
            model,
            len(messages),
        )

        if provider == "local":
            async for chunk in self._stream_local(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            ):
                yield chunk
        else:
            async for chunk in self._stream_cloud(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            ):
                yield chunk

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
