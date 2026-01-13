"""Detect if a question is about the project."""
import re
from typing import List, Tuple, Optional


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


def extract_review_query(query: str) -> Tuple[str, Optional[str]]:
    """
    Extract review query and optional commit hash.
    
    Examples:
    - "/review" -> ("", None)  # Review uncommitted
    - "/review commit" -> ("", "HEAD")  # Review last commit
    - "/review HEAD~1" -> ("", "HEAD~1")  # Review specific commit
    
    Args:
        query: User query (may start with /review)
    
    Returns:
        Tuple of (optional query text, optional commit hash)
    """
    query = query.strip()
    if not query.lower().startswith("/review"):
        return (query, None)
    
    # Remove /review prefix
    rest = query[7:].strip()
    
    if not rest:
        # Just "/review" - review uncommitted changes
        return ("", None)
    
    # Check for commit references
    rest_lower = rest.lower()
    if rest_lower == "commit" or rest_lower.startswith("commit "):
        # "/review commit" or "/review commit <hash>"
        commit_part = rest[7:].strip() if rest_lower.startswith("commit ") else "HEAD"
        return ("", commit_part if commit_part else "HEAD")
    
    # Check if it looks like a commit hash or reference (HEAD, HEAD~1, etc.)
    if re.match(r'^(HEAD|HEAD~[\d]+|[a-f0-9]{7,40})$', rest, re.IGNORECASE):
        return ("", rest)
    
    # Otherwise, treat as query text (for future extensibility)
    return (rest, None)


def build_review_rag_queries(changed_files: List[str], diff: str) -> List[str]:
    """
    Build RAG queries to find relevant documentation and code.
    
    Queries:
    1. Architecture guides (WEB_UI_ARCHITECTURE.md, CONTEXT.md patterns)
    2. Code style guides (from project docs)
    3. Related classes/functions (from changed file names)
    4. Similar implementations (from diff content keywords)
    
    Args:
        changed_files: List of changed file paths
        diff: Git diff content
    
    Returns:
        List of query strings for RAG retrieval
    """
    queries = []
    
    # 1. Architecture and code style queries
    queries.append("architecture patterns design principles SOLID DRY KISS")
    queries.append("code style conventions naming standards documentation")
    
    # 2. Extract file names and module names from changed files
    module_names = []
    file_names = []
    for file_path in changed_files:
        # Extract module/class names from file paths
        if "/" in file_path:
            parts = file_path.split("/")
            # Get last part (filename) and parent directory
            filename = parts[-1]
            if len(parts) > 1:
                parent_dir = parts[-2]
                module_names.append(parent_dir)
            file_names.append(filename.replace(".py", "").replace(".ts", "").replace(".tsx", ""))
        else:
            file_names.append(file_path.replace(".py", "").replace(".ts", "").replace(".tsx", ""))
    
    # Build queries from file/module names
    if module_names:
        unique_modules = list(set(module_names))
        queries.append(f"module {' '.join(unique_modules[:3])} implementation")
    
    if file_names:
        unique_files = list(set(file_names))
        queries.append(f"class function {' '.join(unique_files[:3])}")
    
    # 3. Extract keywords from diff (function names, class names, etc.)
    diff_lower = diff.lower()
    
    # Look for function/class definitions
    function_pattern = r'def\s+(\w+)\s*\('
    class_pattern = r'class\s+(\w+)'
    
    functions = re.findall(function_pattern, diff)
    classes = re.findall(class_pattern, diff)
    
    if functions:
        queries.append(f"function {' '.join(functions[:3])} implementation")
    
    if classes:
        queries.append(f"class {' '.join(classes[:3])} architecture")
    
    # 4. Extract technology keywords from diff
    tech_keywords_in_diff = []
    for tech in TECH_KEYWORDS:
        if tech in diff_lower:
            tech_keywords_in_diff.append(tech)
    
    if tech_keywords_in_diff:
        queries.append(f"{' '.join(tech_keywords_in_diff[:3])} best practices")
    
    # 5. General review query
    queries.append("code review best practices error handling security performance")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_queries = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique_queries.append(q)
    
    return unique_queries
