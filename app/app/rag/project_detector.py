"""Detect if a question is about the project."""
import re
from typing import List


# Project-related keywords (Russian and English)
PROJECT_KEYWORDS = [
    # Russian
    "проект",
    "код",
    "архитектура",
    "документация",
    "API",
    "схема",
    "структура",
    "модуль",
    "компонент",
    "эндпоинт",
    "сервис",
    "функция",
    "класс",
    "файл",
    "конфигурация",
    "настройка",
    "развертывание",
    "деплой",
    # English
    "project",
    "code",
    "architecture",
    "documentation",
    "schema",
    "structure",
    "module",
    "component",
    "endpoint",
    "service",
    "function",
    "class",
    "file",
    "config",
    "configuration",
    "deployment",
    "deploy",
]

# Technology stack keywords
TECH_KEYWORDS = [
    "fastapi",
    "react",
    "typescript",
    "python",
    "pydantic",
    "zustand",
    "vite",
    "tailwind",
    "docker",
    "uvicorn",
    "httpx",
    "rag",
    "mcp",
    "chunkenizer",
    "qdrant",
]

# Project file/module names
PROJECT_MODULES = [
    "chatgpt_client",
    "main.py",
    "config.py",
    "schemas.py",
    "rag",
    "mcp",
    "filesystem_server",
    "git_server",
    "chunkenizer",
    "filter",
    "reranker",
]


def is_project_question(query: str) -> bool:
    """
    Determine if a query is about the project.
    
    Args:
        query: User query text
    
    Returns:
        True if the query appears to be about the project
    """
    if not query or not query.strip():
        return False
    
    query_lower = query.lower()
    
    # Check for project keywords
    for keyword in PROJECT_KEYWORDS:
        if keyword in query_lower:
            return True
    
    # Check for technology stack keywords
    for tech in TECH_KEYWORDS:
        if tech in query_lower:
            return True
    
    # Check for project module/file names
    for module in PROJECT_MODULES:
        if module in query_lower:
            return True
    
    # Check for /help command
    if query_lower.strip().startswith("/help"):
        return True
    
    # Check for file path patterns
    if re.search(r'\b(app|frontend|scripts|tests)/', query_lower):
        return True
    
    # Check for common project question patterns
    project_patterns = [
        r'как\s+(работает|устроен|настроен)',
        r'как\s+(использовать|применить|настроить)',
        r'что\s+(такое|делает|означает)',
        r'где\s+(находится|расположен|определен)',
        r'how\s+(does|to|is)',
        r'what\s+(is|does|are)',
        r'where\s+(is|are)',
    ]
    
    for pattern in project_patterns:
        if re.search(pattern, query_lower):
            return True
    
    return False


def extract_help_query(query: str) -> str:
    """
    Extract the actual question from /help command.
    
    Args:
        query: User query (may start with /help)
    
    Returns:
        The question without /help prefix
    """
    query = query.strip()
    if query.lower().startswith("/help"):
        # Remove /help and any following whitespace
        question = query[5:].strip()
        return question if question else "Tell me about this project"
    return query
