"""
LLM-based prompt classifier for conditional system prompts.

Uses Ollama to classify user messages into categories:
- code: Programming, debugging, API, system administration
- creative: Writing, storytelling, copywriting
- analysis: Data analysis, logical tasks, mathematics
- general: General questions and conversations
"""
from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from ..schemas import ClassificationResult, PromptMode

if TYPE_CHECKING:
    from .ollama_client import OllamaClient

logger = logging.getLogger("app.classifier")

# Classifier system prompt
CLASSIFIER_SYSTEM_PROMPT = """Ты классификатор запросов. Твоя задача — определить категорию запроса пользователя.

Категории:
- code: Программирование, код, дебаг, API, системное администрирование, технические вопросы про IT
- creative: Написание текстов, истории, стихи, сценарии, копирайтинг, креативный контент
- analysis: Анализ данных, логические задачи, математика, статистика, рассуждения
- general: Общие вопросы, разговоры, всё что не подходит под другие категории

Отвечай ТОЛЬКО в формате JSON, без дополнительного текста:
{"category": "code", "confidence": 0.9}

Поле confidence — число от 0.0 до 1.0, показывающее уверенность в классификации."""

CLASSIFIER_USER_TEMPLATE = """Классифицируй запрос:
"{message}"
"""

# Valid categories
VALID_CATEGORIES: list[PromptMode] = ["code", "creative", "analysis", "general"]


class PromptClassifier:
    """
    LLM-based classifier for user requests.

    Uses session-level caching to avoid repeated classification calls
    for similar messages within the same conversation.
    """

    def __init__(self, client: OllamaClient, model: str | None = None):
        """
        Initialize classifier.

        Args:
            client: OllamaClient instance for making classification requests
            model: Model to use for classification (default: client's default)
        """
        self.client = client
        self.model = model
        self._session_cache: dict[str, ClassificationResult] = {}

    async def classify(self, message: str) -> ClassificationResult:
        """
        Classify a user message into a category.

        Uses session cache for similar messages. Falls back to 'general'
        on any error.

        Args:
            message: User message to classify

        Returns:
            ClassificationResult with category and confidence
        """
        # Normalize message for cache key (first 100 chars, lowercased, stripped)
        cache_key = self._normalize_for_cache(message)

        # Check cache
        if cache_key in self._session_cache:
            cached = self._session_cache[cache_key]
            logger.debug("Cache hit for classification: %s -> %s", cache_key[:50], cached.category)
            return cached

        # Call LLM for classification
        try:
            result = await self._call_classifier(message)
            self._session_cache[cache_key] = result
            logger.info(
                "Classified message: category=%s confidence=%.2f message=%s",
                result.category,
                result.confidence,
                message[:50] + "..." if len(message) > 50 else message,
            )
            return result

        except Exception as e:
            logger.warning("Classification failed, using 'general': %s", e)
            fallback = ClassificationResult(category="general", confidence=0.0)
            self._session_cache[cache_key] = fallback
            return fallback

    async def _call_classifier(self, message: str) -> ClassificationResult:
        """
        Make classification request to LLM.

        Args:
            message: User message to classify

        Returns:
            ClassificationResult parsed from LLM response

        Raises:
            Exception: On LLM call failure or parse error
        """
        messages = [
            {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
            {"role": "user", "content": CLASSIFIER_USER_TEMPLATE.format(message=message[:500])},
        ]

        # Use low temperature for deterministic classification
        response = await self.client.chat(
            messages=messages,
            model=self.model,
            temperature=0.1,
            max_tokens=100,
        )

        return self._parse_response(response.content)

    def _parse_response(self, content: str) -> ClassificationResult:
        """
        Parse LLM response into ClassificationResult.

        Args:
            content: Raw LLM response text

        Returns:
            ClassificationResult

        Raises:
            ValueError: If response cannot be parsed
        """
        # Try to extract JSON from response
        content = content.strip()

        # Try direct JSON parse first
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Try to find JSON in the response
            json_match = re.search(r'\{[^}]+\}', content)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    raise ValueError(f"Could not parse classification response: {content[:100]}")
            else:
                raise ValueError(f"No JSON found in classification response: {content[:100]}")

        # Validate and extract fields
        category = data.get("category", "general")
        if category not in VALID_CATEGORIES:
            logger.warning("Invalid category '%s', using 'general'", category)
            category = "general"

        confidence = data.get("confidence", 0.5)
        try:
            confidence = float(confidence)
            confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]
        except (TypeError, ValueError):
            confidence = 0.5

        return ClassificationResult(category=category, confidence=confidence)

    def _normalize_for_cache(self, message: str) -> str:
        """
        Normalize message for cache key.

        Uses first 100 characters, lowercased and stripped.

        Args:
            message: Original message

        Returns:
            Normalized cache key
        """
        return message[:100].lower().strip()

    def clear_session_cache(self):
        """Clear the session cache."""
        self._session_cache.clear()
        logger.debug("Classifier session cache cleared")

    def get_cache_size(self) -> int:
        """Get current cache size."""
        return len(self._session_cache)


# Module-level classifier instance
_classifier: PromptClassifier | None = None


def get_classifier(client: OllamaClient, model: str | None = None) -> PromptClassifier:
    """
    Get or create the global classifier instance.

    Args:
        client: OllamaClient instance
        model: Optional model override

    Returns:
        PromptClassifier instance
    """
    global _classifier
    if _classifier is None:
        _classifier = PromptClassifier(client, model)
    return _classifier


def clear_classifier_cache():
    """Clear the global classifier's session cache."""
    global _classifier
    if _classifier is not None:
        _classifier.clear_session_cache()
