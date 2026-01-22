"""
Prompt templates for conditional system prompts.

Provides category-specific system prompts and default parameters
for optimizing LLM responses based on request type.
"""
from typing import TypedDict


class CategoryDefaults(TypedDict):
    """Default parameters for a prompt category."""
    num_ctx: int
    temperature: float


# Default system prompts for each category (Russian)
DEFAULT_TEMPLATES: dict[str, str] = {
    "code": """Ты опытный программист-эксперт. Отвечай точно, с примерами кода.
Используй правильное форматирование (markdown code blocks).
Объясняй сложные концепции простым языком.
Если нужно показать код — всегда указывай язык программирования.""",

    "creative": """Ты креативный писатель с богатым воображением.
Создавай оригинальный, увлекательный контент.
Используй яркие образы и выразительный язык.
Не бойся экспериментировать со стилем.""",

    "analysis": """Ты аналитик с логическим мышлением.
Структурируй ответы. Приводи аргументы и доказательства.
Если нужны вычисления — показывай ход решения пошагово.
Делай выводы на основе фактов.""",

    "general": """Ты полезный ассистент. Отвечай чётко и по существу.
Если вопрос неоднозначен — уточни.
Будь дружелюбным и профессиональным.""",
}

# Default Ollama parameters for each category
CATEGORY_DEFAULTS: dict[str, CategoryDefaults] = {
    "code": {"num_ctx": 16384, "temperature": 0.2},
    "creative": {"num_ctx": 8192, "temperature": 0.9},
    "analysis": {"num_ctx": 16384, "temperature": 0.3},
    "general": {"num_ctx": 4096, "temperature": 0.7},
}

# Category display info for UI
CATEGORY_INFO: dict[str, dict[str, str]] = {
    "code": {
        "name": "Technical",
        "emoji": "💻",
        "description": "Программирование, дебаг, API, системное администрирование",
    },
    "creative": {
        "name": "Creative",
        "emoji": "✨",
        "description": "Тексты, сторителлинг, копирайтинг",
    },
    "analysis": {
        "name": "Analysis",
        "emoji": "📊",
        "description": "Анализ данных, логические задачи, математика",
    },
    "general": {
        "name": "General",
        "emoji": "💬",
        "description": "Общие вопросы и разговоры",
    },
}


def get_template(category: str) -> str:
    """Get system prompt template for a category."""
    return DEFAULT_TEMPLATES.get(category, DEFAULT_TEMPLATES["general"])


def get_category_defaults(category: str) -> CategoryDefaults:
    """Get default parameters for a category."""
    return CATEGORY_DEFAULTS.get(category, CATEGORY_DEFAULTS["general"])


def get_all_categories() -> list[str]:
    """Get list of all available categories."""
    return list(DEFAULT_TEMPLATES.keys())
