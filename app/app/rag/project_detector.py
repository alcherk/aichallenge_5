"""Detect if a question is about the project or task management."""
import logging
import re
from dataclasses import dataclass
from typing import List, Tuple, Optional

logger = logging.getLogger("app.rag.project_detector")


@dataclass
class TaskCommandInfo:
    """Information about a parsed task command."""

    command: str  # tasks, add, status, priority, update, delete
    args: dict  # Parsed arguments


# Task-related keywords (Russian and English)
TASK_KEYWORDS = [
    # Russian
    "задача",
    "задачи",
    "задачу",
    "таска",
    "таски",
    "таску",
    "приоритет",
    "дедлайн",
    "срок",
    "исполнитель",
    "назначить",
    "закрыть",
    "выполнить",
    "статус",
    # English
    "task",
    "tasks",
    "priority",
    "deadline",
    "assignee",
    "assign",
    "close",
    "complete",
    "status",
    "todo",
]

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


# Task command patterns
TASK_COMMAND_PATTERNS = {
    "tasks": re.compile(r"^/tasks\s*(.*)$", re.IGNORECASE),
    "add": re.compile(r"^/add\s+(.+)$", re.IGNORECASE),
    "status": re.compile(r"^/status\s*$", re.IGNORECASE),
    "priority": re.compile(r"^/priority\s*$", re.IGNORECASE),
}

# Natural language patterns for task operations
NL_TASK_PATTERNS = {
    # List tasks
    "tasks": [
        re.compile(r"(покажи|выведи|список)\s+(все\s+)?(задач|таск)", re.IGNORECASE),
        re.compile(r"(show|list|display)\s+(all\s+)?tasks?", re.IGNORECASE),
        re.compile(r"какие\s+(есть\s+)?(задачи|таски)", re.IGNORECASE),
        re.compile(r"what\s+(are\s+(the\s+|all\s+)?)?tasks", re.IGNORECASE),
    ],
    # Add task
    "add": [
        re.compile(r"(создай|добавь|заведи|сделай)\s+(задачу|таску)", re.IGNORECASE),
        re.compile(r"(create|add|make)\s+(a\s+)?task", re.IGNORECASE),
        re.compile(r"новая\s+(задача|таска)", re.IGNORECASE),
        re.compile(r"new\s+task", re.IGNORECASE),
    ],
    # Status
    "status": [
        re.compile(r"(статус|состояние)\s+(проекта|задач)", re.IGNORECASE),
        re.compile(r"как\s+дела\s+с\s+(проектом|задачами)", re.IGNORECASE),
        re.compile(r"project\s+status", re.IGNORECASE),
        re.compile(r"how\s+(is|are)\s+(the\s+)?(project|tasks)", re.IGNORECASE),
    ],
    # Priority
    "priority": [
        re.compile(r"(что|чем)\s+(делать|заняться)\s+(первым|сначала|дальше)", re.IGNORECASE),
        re.compile(r"(приоритет|рекомендации)", re.IGNORECASE),
        re.compile(r"what\s+(should\s+I|to)\s+do\s+(first|next)", re.IGNORECASE),
        re.compile(r"(priority|priorities|recommend)", re.IGNORECASE),
    ],
    # Update status (close/complete)
    "update_done": [
        re.compile(r"(закрой|заверши|выполни|готово)\s+.*(задачу|таску)", re.IGNORECASE),
        re.compile(r"(close|complete|finish|done)\s+.*(task)", re.IGNORECASE),
        re.compile(r"(задача|таска)\s+.*(готова|выполнена|закрыта)", re.IGNORECASE),
        re.compile(r"mark\s+.*(as\s+)?(done|complete)", re.IGNORECASE),
    ],
    # Update status (in progress)
    "update_in_progress": [
        re.compile(r"(начни|приступи|возьми)\s+.*(задачу|таску)", re.IGNORECASE),
        re.compile(r"(start|begin)\s+.*(task|working)", re.IGNORECASE),
        re.compile(r"взял\s+(в\s+работу)", re.IGNORECASE),
    ],
    # Delete
    "delete": [
        re.compile(r"(удали|убери)\s+(задачу|таску)", re.IGNORECASE),
        re.compile(r"(delete|remove)\s+(the\s+)?task", re.IGNORECASE),
    ],
    # Task query - questions about tasks that need LLM analysis
    "task_query": [
        # Russian patterns
        re.compile(r"как(ая|ую|ой|ие)\s+.*(задач|таск)", re.IGNORECASE),
        re.compile(r"(какую|какой|какие)\s+(задач|таск)", re.IGNORECASE),
        re.compile(r"(что|чем)\s+(нужно|надо|следует)\s+(делать|заняться)", re.IGNORECASE),
        re.compile(r"(самая?|наиболее)\s+(важн|срочн|приоритетн)", re.IGNORECASE),
        re.compile(r"(есть\s+ли|сколько)\s+.*(задач|таск)", re.IGNORECASE),
        re.compile(r"(просроченн|overdue|горящ|срочн)", re.IGNORECASE),
        re.compile(r"над\s+чем\s+(работа|занят)", re.IGNORECASE),
        re.compile(r"(кто|чьи)\s+.*(задач|таск)", re.IGNORECASE),
        re.compile(r"(задач|таск).*(у\s+кого|назначен|исполнител)", re.IGNORECASE),
        # English patterns
        re.compile(r"which\s+(task|tasks)", re.IGNORECASE),
        re.compile(r"what\s+(task|tasks)\s+(should|need|have|is|are)", re.IGNORECASE),
        re.compile(r"(highest|lowest|most|urgent|important)\s+.*(task|priority)", re.IGNORECASE),
        re.compile(r"(any|how many)\s+.*(task|overdue)", re.IGNORECASE),
        re.compile(r"(who|whose)\s+.*(task|assigned)", re.IGNORECASE),
        re.compile(r"task.*(assigned|belong|for)\s+", re.IGNORECASE),
    ],
}


def is_task_command(query: str) -> bool:
    """Check if query is a task-related command or question.

    Args:
        query: User query text

    Returns:
        True if query is about task management
    """
    if not query or not query.strip():
        return False

    query = query.strip()

    # Check for explicit commands
    for pattern in TASK_COMMAND_PATTERNS.values():
        if pattern.match(query):
            return True

    # Check for natural language patterns
    for patterns in NL_TASK_PATTERNS.values():
        for pattern in patterns:
            if pattern.search(query):
                return True

    # Check for task keywords
    query_lower = query.lower()
    for keyword in TASK_KEYWORDS:
        if keyword in query_lower:
            return True

    return False


def parse_task_command(query: str) -> Optional[TaskCommandInfo]:
    """Parse a task command and extract its type and arguments.

    Args:
        query: User query text

    Returns:
        TaskCommandInfo if query is a task command, None otherwise
    """
    if not query or not query.strip():
        return None

    query = query.strip()
    query_preview = query[:50] + "..." if len(query) > 50 else query

    def _log_and_return(cmd_type: str, cmd: TaskCommandInfo, is_slash: bool) -> TaskCommandInfo:
        """Log command detection and return the command info."""
        source = "slash" if is_slash else "NL"
        logger.info(
            "Task command detected: type=%s source=%s cmd=%s args=%s query='%s'",
            cmd_type, source, cmd.command, cmd.args, query_preview
        )
        return cmd

    # Check for /tasks command
    match = TASK_COMMAND_PATTERNS["tasks"].match(query)
    if match:
        args_str = match.group(1).strip()
        args = {}
        if args_str:
            # Parse filter (e.g., "high", "in_progress", "@alex")
            if args_str.lower() in ("high", "medium", "low"):
                args["filter_priority"] = args_str.lower()
            elif args_str.lower() in ("todo", "in_progress", "done"):
                args["filter_status"] = args_str.lower()
            elif args_str.startswith("@"):
                args["filter_assignee"] = args_str
        return _log_and_return("tasks", TaskCommandInfo(command="tasks", args=args), is_slash=True)

    # Check for /add command
    match = TASK_COMMAND_PATTERNS["add"].match(query)
    if match:
        args_str = match.group(1).strip()
        args = _parse_add_args(args_str)
        return _log_and_return("add", TaskCommandInfo(command="add", args=args), is_slash=True)

    # Check for /status command
    if TASK_COMMAND_PATTERNS["status"].match(query):
        return _log_and_return("status", TaskCommandInfo(command="status", args={}), is_slash=True)

    # Check for /priority command
    if TASK_COMMAND_PATTERNS["priority"].match(query):
        return _log_and_return("priority", TaskCommandInfo(command="priority", args={}), is_slash=True)

    # Check natural language patterns
    # Note: Order matters! More specific patterns (add, update, delete, task_query) come before
    # general ones (tasks, priority) to avoid false matches

    # Task query first - questions about tasks need LLM analysis
    for pattern in NL_TASK_PATTERNS["task_query"]:
        if pattern.search(query):
            return _log_and_return(
                "task_query",
                TaskCommandInfo(command="task_query", args={"question": query}),
                is_slash=False
            )

    for pattern in NL_TASK_PATTERNS["tasks"]:
        if pattern.search(query):
            return _log_and_return("tasks", TaskCommandInfo(command="tasks", args={}), is_slash=False)

    for pattern in NL_TASK_PATTERNS["status"]:
        if pattern.search(query):
            return _log_and_return("status", TaskCommandInfo(command="status", args={}), is_slash=False)

    # Check "add" before "priority" since add commands may contain "приоритет" as a parameter
    for pattern in NL_TASK_PATTERNS["add"]:
        if pattern.search(query):
            # For NL add, we'll need to extract details from the query
            return _log_and_return(
                "add_nl",
                TaskCommandInfo(command="add_nl", args={"raw_query": query}),
                is_slash=False
            )

    for pattern in NL_TASK_PATTERNS["update_done"]:
        if pattern.search(query):
            # Extract task query from the message
            task_query = _extract_task_query(query)
            return _log_and_return(
                "update_done",
                TaskCommandInfo(command="update", args={"query": task_query, "new_status": "done"}),
                is_slash=False
            )

    for pattern in NL_TASK_PATTERNS["update_in_progress"]:
        if pattern.search(query):
            task_query = _extract_task_query(query)
            return _log_and_return(
                "update_in_progress",
                TaskCommandInfo(command="update", args={"query": task_query, "new_status": "in_progress"}),
                is_slash=False
            )

    for pattern in NL_TASK_PATTERNS["delete"]:
        if pattern.search(query):
            task_query = _extract_task_query(query)
            return _log_and_return(
                "delete",
                TaskCommandInfo(command="delete", args={"query": task_query}),
                is_slash=False
            )

    # Priority pattern last - it's a general fallback for priority-related queries
    for pattern in NL_TASK_PATTERNS["priority"]:
        if pattern.search(query):
            return _log_and_return("priority", TaskCommandInfo(command="priority", args={}), is_slash=False)

    logger.debug("No task command detected for query: '%s'", query_preview)
    return None


def _parse_add_args(args_str: str) -> dict:
    """Parse arguments for /add command.

    Expected format: Title @assignee priority due:YYYY-MM-DD

    Args:
        args_str: The argument string after /add

    Returns:
        Dictionary with parsed fields
    """
    args = {}

    # Extract assignee (@username)
    assignee_match = re.search(r"@(\w+)", args_str)
    if assignee_match:
        args["assignee"] = assignee_match.group(1)
        args_str = args_str.replace(assignee_match.group(0), "").strip()

    # Extract deadline (due:YYYY-MM-DD or YYYY-MM-DD)
    deadline_match = re.search(r"(?:due:|до:)?(\d{4}-\d{2}-\d{2})", args_str)
    if deadline_match:
        args["deadline"] = deadline_match.group(1)
        args_str = args_str.replace(deadline_match.group(0), "").strip()

    # Extract priority (high/medium/low)
    priority_match = re.search(r"\b(high|medium|low|высокий|средний|низкий)\b", args_str, re.IGNORECASE)
    if priority_match:
        priority = priority_match.group(1).lower()
        # Map Russian priorities to English
        priority_map = {"высокий": "high", "средний": "medium", "низкий": "low"}
        args["priority"] = priority_map.get(priority, priority)
        args_str = args_str.replace(priority_match.group(0), "").strip()

    # Remaining text is the title
    title = re.sub(r"\s+", " ", args_str).strip()
    if title:
        args["title"] = title

    return args


def _extract_task_query(query: str) -> str:
    """Extract the task identifier/query from a natural language command.

    Args:
        query: Full user query

    Returns:
        Extracted task identifier or query
    """
    # Remove common command words
    patterns_to_remove = [
        r"(закрой|заверши|выполни|удали|убери|начни|приступи|возьми)\s+",
        r"(close|complete|finish|delete|remove|start|begin)\s+",
        r"(задачу|таску|задача|таска)\s+",
        r"(the\s+)?task\s+",
        r"(в\s+работу)\s*",
        r"(про|about|named|called)\s+",
    ]

    result = query
    for pattern in patterns_to_remove:
        result = re.sub(pattern, "", result, flags=re.IGNORECASE)

    # Clean up extra whitespace
    result = re.sub(r"\s+", " ", result).strip()

    # Remove quotes if present
    result = result.strip("\"'")

    return result if result else query
