"""
History summarizer service for conversation context management.

Summarizes conversation history when context limit is approached,
preserving key facts and decisions while reducing token count.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Literal

from .ollama_client import get_ollama_client
from .chatgpt_client import call_chatgpt
from ..schemas import ChatRequest, ChatMessage

logger = logging.getLogger("app.summarizer")


# Known context window sizes for common models (in tokens)
MODEL_CONTEXT_LIMITS: dict[str, int] = {
    # OpenAI models
    "gpt-4": 8192,
    "gpt-4-32k": 32768,
    "gpt-4-turbo": 128000,
    "gpt-4-turbo-preview": 128000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-3.5-turbo": 16385,
    "gpt-3.5-turbo-16k": 16385,
    # Ollama / local models
    "qwen2.5:14b": 32768,
    "qwen2.5:7b": 32768,
    "qwen2.5:3b": 32768,
    "qwen2.5:1.5b": 32768,
    "qwen2.5:0.5b": 32768,
    "llama3.2:3b": 131072,
    "llama3.2:1b": 131072,
    "llama3.1:8b": 131072,
    "llama3.1:70b": 131072,
    "llama3:8b": 8192,
    "llama3:70b": 8192,
    "llama2:7b": 4096,
    "llama2:13b": 4096,
    "llama2:70b": 4096,
    "mistral:7b": 32768,
    "mixtral:8x7b": 32768,
    "codellama:7b": 16384,
    "codellama:13b": 16384,
    "codellama:34b": 16384,
    "phi3:mini": 128000,
    "phi3:medium": 128000,
    "gemma:2b": 8192,
    "gemma:7b": 8192,
    "gemma2:9b": 8192,
    "gemma2:27b": 8192,
    "deepseek-coder:6.7b": 16384,
    "deepseek-coder:33b": 16384,
}

# Default context limit if model not found
DEFAULT_CONTEXT_LIMIT = 8192


class HistorySummarizer:
    """
    Summarizes conversation history when context limit is approached.

    The summarizer:
    1. Detects when messages exceed a configurable threshold of the model's context limit
    2. Summarizes older messages while keeping recent messages intact
    3. Uses the same provider (local or cloud) for summarization

    This allows long conversations to continue without losing important context.
    """

    SUMMARIZE_PROMPT = """Summarize the following conversation concisely,
preserving key facts, decisions, and context needed for continuation:

{conversation}

Summary:"""

    # System prompt for the summarization call
    SUMMARIZE_SYSTEM_PROMPT = """You are a conversation summarizer. Your task is to create concise summaries that:
1. Preserve all important facts, decisions, and conclusions
2. Maintain key context needed to continue the conversation
3. Keep track of any pending questions or tasks
4. Note any important technical details or code discussed
5. Be as brief as possible while retaining essential information

Respond only with the summary, no preamble or explanation."""

    def __init__(self, chars_per_token: float = 4.0):
        """
        Initialize the summarizer.

        Args:
            chars_per_token: Estimated characters per token for rough token counting.
                            Default 4.0 is a reasonable estimate for English text.
        """
        self.chars_per_token = chars_per_token

    def _count_tokens(self, messages: list[dict]) -> int:
        """
        Estimate token count for messages.

        This uses a simple character-based estimation. For more accurate counting,
        tiktoken could be used for OpenAI models, but this approach works for
        both cloud and local models without additional dependencies.

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            Estimated token count
        """
        total_chars = 0
        for msg in messages:
            # Count role (typically 1-2 tokens)
            role = msg.get("role", "")
            total_chars += len(role) + 4  # Add overhead for role formatting

            # Count content
            content = msg.get("content", "")
            total_chars += len(content)

            # Add per-message overhead (separators, etc.)
            total_chars += 4

        # Convert to tokens
        tokens = int(total_chars / self.chars_per_token)

        logger.debug(
            "Token count estimate: %d chars -> %d tokens (%.1f chars/token)",
            total_chars,
            tokens,
            self.chars_per_token,
        )

        return tokens

    def _get_context_limit(self, model: str) -> int:
        """
        Get context window limit for a model.

        Args:
            model: Model name (e.g., "gpt-4o-mini", "qwen2.5:14b")

        Returns:
            Context limit in tokens
        """
        # Try exact match first
        if model in MODEL_CONTEXT_LIMITS:
            return MODEL_CONTEXT_LIMITS[model]

        # Try base model name (without version/size suffix)
        # Handle formats like "qwen2.5:14b" -> "qwen2.5"
        base_model = model.split(":")[0] if ":" in model else model

        # Also handle "gpt-4-turbo-preview" -> "gpt-4-turbo"
        for known_model, limit in MODEL_CONTEXT_LIMITS.items():
            if model.startswith(known_model) or known_model.startswith(base_model):
                logger.debug(
                    "Context limit for %s: %d (matched %s)",
                    model,
                    limit,
                    known_model,
                )
                return limit

        # Default fallback
        logger.warning(
            "Unknown model %s, using default context limit %d",
            model,
            DEFAULT_CONTEXT_LIMIT,
        )
        return DEFAULT_CONTEXT_LIMIT

    async def should_summarize(
        self,
        messages: list[dict],
        model: str,
        threshold: float = 0.9,
    ) -> bool:
        """
        Check if messages exceed threshold of context limit.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name to check context limit for
            threshold: Fraction of context limit to trigger summarization (0.0-1.0)

        Returns:
            True if summarization is recommended
        """
        token_count = self._count_tokens(messages)
        context_limit = self._get_context_limit(model)
        threshold_tokens = int(context_limit * threshold)

        should_summarize = token_count > threshold_tokens

        logger.info(
            "Should summarize check: tokens=%d limit=%d threshold=%d (%.0f%%) -> %s",
            token_count,
            context_limit,
            threshold_tokens,
            threshold * 100,
            should_summarize,
        )

        return should_summarize

    def _format_conversation_for_summary(self, messages: list[dict]) -> str:
        """
        Format messages into a readable conversation string for summarization.

        Args:
            messages: List of message dicts to format

        Returns:
            Formatted conversation string
        """
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown").capitalize()
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n\n".join(lines)

    async def summarize(
        self,
        messages: list[dict],
        keep_recent: int = 4,
        provider: Literal["cloud", "local"] = "local",
        model: str | None = None,
    ) -> list[dict]:
        """
        Summarize old messages, keep recent ones intact.

        This method:
        1. Splits messages into old (to summarize) and recent (to keep)
        2. Calls the LLM to summarize the old messages
        3. Returns [system_message_with_summary] + recent_messages

        Args:
            messages: List of message dicts with 'role' and 'content'
            keep_recent: Number of recent messages to keep intact
            provider: Provider to use for summarization ("cloud" or "local")
            model: Model to use (default: provider's default)

        Returns:
            New message list with summary as system message + recent messages
        """
        if len(messages) <= keep_recent:
            logger.debug(
                "Not enough messages to summarize: %d <= %d",
                len(messages),
                keep_recent,
            )
            return messages

        # Separate system messages from conversation
        system_messages = [m for m in messages if m.get("role") == "system"]
        conversation_messages = [m for m in messages if m.get("role") != "system"]

        if len(conversation_messages) <= keep_recent:
            logger.debug(
                "Not enough conversation messages to summarize: %d <= %d",
                len(conversation_messages),
                keep_recent,
            )
            return messages

        # Split into old (to summarize) and recent (to keep)
        old_messages = conversation_messages[:-keep_recent]
        recent_messages = conversation_messages[-keep_recent:]

        logger.info(
            "Summarizing %d old messages, keeping %d recent",
            len(old_messages),
            len(recent_messages),
        )

        # Format old messages for summarization
        conversation_text = self._format_conversation_for_summary(old_messages)
        prompt = self.SUMMARIZE_PROMPT.format(conversation=conversation_text)

        # Generate summary using appropriate provider
        try:
            if provider == "local":
                summary = await self._summarize_local(prompt, model)
            else:
                summary = await self._summarize_cloud(prompt, model)
        except Exception as e:
            logger.error("Summarization failed: %s", e)
            # On failure, return original messages rather than losing context
            return messages

        # Build new message list
        result = []

        # Include original system messages
        result.extend(system_messages)

        # Add summary as a system message
        summary_message = {
            "role": "system",
            "content": f"[Previous conversation summary]\n{summary}\n[End of summary]",
        }
        result.append(summary_message)

        # Add recent messages
        result.extend(recent_messages)

        logger.info(
            "Summarization complete: %d messages -> %d messages (summary: %d chars)",
            len(messages),
            len(result),
            len(summary),
        )

        return result

    async def _summarize_local(
        self,
        prompt: str,
        model: str | None = None,
    ) -> str:
        """
        Generate summary using local Ollama model.

        Args:
            prompt: Summarization prompt with conversation
            model: Model to use (default: Ollama default)

        Returns:
            Summary text
        """
        client = get_ollama_client()

        messages = [
            {"role": "system", "content": self.SUMMARIZE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        response = await client.chat(
            messages=messages,
            model=model,
            temperature=0.3,  # Lower temperature for more focused summaries
            max_tokens=1024,  # Summaries should be concise
        )

        logger.debug(
            "Local summarization: model=%s tokens=%s",
            response.model,
            response.tokens_used,
        )

        return response.content

    async def _summarize_cloud(
        self,
        prompt: str,
        model: str | None = None,
    ) -> str:
        """
        Generate summary using cloud OpenAI model.

        Args:
            prompt: Summarization prompt with conversation
            model: Model to use (default: OpenAI default)

        Returns:
            Summary text
        """
        messages = [
            ChatMessage(role="system", content=self.SUMMARIZE_SYSTEM_PROMPT),
            ChatMessage(role="user", content=prompt),
        ]

        request = ChatRequest(
            messages=messages,
            model=model,
            temperature=0.3,  # Lower temperature for more focused summaries
            max_tokens=1024,  # Summaries should be concise
        )

        response, _ = await call_chatgpt(request)

        if response.choices:
            summary = response.choices[0].message.content
            logger.debug(
                "Cloud summarization: model=%s tokens=%s",
                response.model,
                response.usage.total_tokens if response.usage else None,
            )
            return summary

        raise RuntimeError("No content in cloud summarization response")


# Module-level singleton for convenience
_summarizer: HistorySummarizer | None = None


def get_summarizer() -> HistorySummarizer:
    """
    Get or create the global HistorySummarizer instance.

    Returns:
        Singleton HistorySummarizer instance
    """
    global _summarizer
    if _summarizer is None:
        _summarizer = HistorySummarizer()
    return _summarizer
