"""
Ollama client for local LLM inference.

Provides an OpenAI-compatible interface for Ollama, supporting:
- Non-streaming chat completions
- Streaming chat completions
- Health checks
- Model listing
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import AsyncGenerator, Any

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
class OllamaResponse:
    """Response from Ollama chat completion."""
    content: str
    model: str
    tokens_used: int | None = None
    inference_time_ms: int | None = None


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
    ) -> OllamaResponse:
        """
        Non-streaming chat completion.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name (default: client's default_model)
            temperature: Sampling temperature (0.0 to 1.0)
            top_p: Top-p sampling parameter
            max_tokens: Maximum tokens to generate

        Returns:
            OllamaResponse with content and metadata

        Raises:
            httpx.TimeoutException: On request timeout
            httpx.HTTPStatusError: On HTTP errors
            RuntimeError: On connection errors or invalid responses
        """
        model = model or self.default_model
        url = f"{self.base_url}/api/chat"

        body = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "num_predict": max_tokens,
            },
        }

        logger.debug(
            "Ollama chat request: model=%s messages=%d temperature=%.2f",
            model,
            len(messages),
            temperature,
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
            "Ollama chat completed: model=%s tokens=%s time=%dms",
            data.get("model", model),
            tokens_used,
            inference_time_ms or elapsed_ms,
        )

        return OllamaResponse(
            content=content,
            model=data.get("model", model),
            tokens_used=tokens_used,
            inference_time_ms=inference_time_ms,
        )

    async def stream_chat(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        """
        Streaming chat completion that yields tokens.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name (default: client's default_model)
            temperature: Sampling temperature (0.0 to 1.0)
            top_p: Top-p sampling parameter
            max_tokens: Maximum tokens to generate

        Yields:
            String tokens as they are generated

        Raises:
            httpx.TimeoutException: On request timeout
            httpx.HTTPStatusError: On HTTP errors
            RuntimeError: On connection errors
        """
        model = model or self.default_model
        url = f"{self.base_url}/api/chat"

        body = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "num_predict": max_tokens,
            },
        }

        logger.debug(
            "Ollama stream request: model=%s messages=%d",
            model,
            len(messages),
        )

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
                                "Ollama stream completed: model=%s eval_count=%s",
                                data.get("model"),
                                data.get("eval_count"),
                            )
                            return

                        # Extract token from message
                        message = data.get("message", {})
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
