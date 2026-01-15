"""Command handlers for task management.

Handles:
- /tasks - List tasks
- /add - Create new task
- /status - Project status summary
- /priority - Priority recommendations
- Task updates (status changes, deletions)
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .parser import (
    Task,
    find_task_by_query,
    generate_task_id,
    parse_tasks,
    serialize_tasks,
    validate_deadline,
    validate_priority,
)

logger = logging.getLogger("app.tasks.commands")

TASKS_FILE = "todo.md"

# Priority order for sorting
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass
class CommandResult:
    """Result of a command execution."""

    success: bool
    message: str
    tasks: Optional[List[Task]] = None
    needs_confirmation: bool = False
    confirmation_context: Optional[Dict[str, Any]] = None


async def read_tasks_file(mcp_manager: Any, workspace_root: Path) -> Tuple[List[Task], Optional[str]]:
    """Read and parse tasks from todo.md.

    Returns:
        Tuple of (tasks, error_message)
    """
    try:
        file_path = str(workspace_root / TASKS_FILE)
        result = await mcp_manager.call_openai_tool(
            "mcp_builtin_filesystem__read_file",
            {"path": file_path},
        )

        if isinstance(result, dict) and result.get("error"):
            # File doesn't exist - return empty list
            if "not found" in str(result.get("error", "")).lower():
                return [], None
            return [], str(result.get("error"))

        content = ""
        if isinstance(result, dict):
            content = result.get("content", "") or result.get("text", "") or ""
        elif isinstance(result, str):
            content = result
        elif isinstance(result, list):
            # MCP might return content as list of text blocks
            for item in result:
                if isinstance(item, dict) and item.get("type") == "text":
                    content += item.get("text", "")
                elif isinstance(item, str):
                    content += item

        if not content.strip():
            return [], None

        tasks = parse_tasks(content)
        return tasks, None

    except Exception as e:
        logger.error("Failed to read tasks file: %s", e, exc_info=True)
        return [], str(e)


async def write_tasks_file(
    mcp_manager: Any, workspace_root: Path, tasks: List[Task]
) -> Optional[str]:
    """Write tasks to todo.md.

    Returns:
        Error message if failed, None if successful
    """
    try:
        file_path = str(workspace_root / TASKS_FILE)
        content = serialize_tasks(tasks)

        result = await mcp_manager.call_openai_tool(
            "mcp_builtin_filesystem__write_file",
            {"path": file_path, "content": content},
        )

        if isinstance(result, dict) and result.get("error"):
            return str(result.get("error"))

        return None

    except Exception as e:
        logger.error("Failed to write tasks file: %s", e, exc_info=True)
        return str(e)


async def handle_tasks_command(
    mcp_manager: Any,
    workspace_root: Path,
    filter_priority: Optional[str] = None,
    filter_status: Optional[str] = None,
    filter_assignee: Optional[str] = None,
) -> CommandResult:
    """Handle /tasks command - list all tasks.

    Args:
        mcp_manager: MCP manager for file operations
        workspace_root: Path to workspace root
        filter_priority: Optional priority filter (high/medium/low)
        filter_status: Optional status filter (todo/in_progress/done)
        filter_assignee: Optional assignee filter (@username)
    """
    logger.info(
        "Executing /tasks command: priority=%s status=%s assignee=%s",
        filter_priority, filter_status, filter_assignee
    )
    tasks, error = await read_tasks_file(mcp_manager, workspace_root)

    if error:
        return CommandResult(
            success=False,
            message=f"Ошибка чтения файла задач: {error}",
        )

    if not tasks:
        return CommandResult(
            success=True,
            message="Задач нет",
            tasks=[],
        )

    # Apply filters
    filtered = tasks
    if filter_priority:
        filtered = [t for t in filtered if t.priority == filter_priority.lower()]
    if filter_status:
        filtered = [t for t in filtered if t.status == filter_status.lower()]
    if filter_assignee:
        assignee = filter_assignee.lstrip("@")
        filtered = [t for t in filtered if t.assignee.lower() == assignee.lower()]

    if not filtered:
        return CommandResult(
            success=True,
            message="Задач с указанными фильтрами не найдено",
            tasks=[],
        )

    # Format output as markdown list
    lines = []
    for task in filtered:
        checkbox = "[x]" if task.status == "done" else "[ ]"
        parts = [f"- {checkbox} {task.title}"]

        meta = [task.priority]
        if task.assignee:
            meta.append(f"@{task.assignee}")
        if task.deadline:
            meta.append(f"due: {task.deadline}")
        if task.status == "in_progress":
            meta.append("in_progress")

        parts.append(f"({', '.join(meta)})")
        lines.append(" ".join(parts))

    return CommandResult(
        success=True,
        message="\n".join(lines),
        tasks=filtered,
    )


async def handle_add_command(
    mcp_manager: Any,
    workspace_root: Path,
    title: str,
    priority: str,
    assignee: str,
    deadline: Optional[str] = None,
    description: str = "",
) -> CommandResult:
    """Handle /add command - create a new task.

    Args:
        mcp_manager: MCP manager for file operations
        workspace_root: Path to workspace root
        title: Task title (required)
        priority: Task priority (required: high/medium/low)
        assignee: Task assignee (required: username without @)
        deadline: Optional deadline in YYYY-MM-DD format
        description: Optional task description
    """
    logger.info(
        "Executing /add command: title='%s' priority=%s assignee=%s deadline=%s",
        title[:30] if title else None, priority, assignee, deadline
    )
    # Validate inputs
    if not title or not title.strip():
        return CommandResult(
            success=False,
            message="Ошибка: название задачи обязательно",
        )

    if not validate_priority(priority):
        return CommandResult(
            success=False,
            message=f"Ошибка: недопустимый приоритет '{priority}'. Используйте: high, medium, low",
        )

    if not assignee or not assignee.strip():
        return CommandResult(
            success=False,
            message="Ошибка: исполнитель обязателен",
        )

    warnings = []
    if deadline:
        is_valid, warning = validate_deadline(deadline)
        if not is_valid:
            return CommandResult(
                success=False,
                message=f"Ошибка: {warning}",
            )
        if warning:
            warnings.append(warning)

    # Read existing tasks
    tasks, error = await read_tasks_file(mcp_manager, workspace_root)
    if error:
        return CommandResult(
            success=False,
            message=f"Ошибка чтения файла задач: {error}",
        )

    # Create new task
    task = Task(
        id=generate_task_id(),
        title=title.strip(),
        priority=priority.lower(),
        assignee=assignee.strip().lstrip("@"),
        status="todo",
        deadline=deadline,
        description=description.strip(),
    )

    tasks.append(task)

    # Write back
    error = await write_tasks_file(mcp_manager, workspace_root, tasks)
    if error:
        return CommandResult(
            success=False,
            message=f"Ошибка записи файла задач: {error}",
        )

    # Format response
    meta_parts = [task.priority, f"@{task.assignee}"]
    if task.deadline:
        meta_parts.append(f"due: {task.deadline}")

    message = f"Задача создана:\n- [ ] {task.title} (id:{task.id}, {', '.join(meta_parts)})"

    if warnings:
        message += f"\n\n⚠️ Предупреждение: {'; '.join(warnings)}"

    return CommandResult(
        success=True,
        message=message,
        tasks=[task],
    )


async def handle_status_command(
    mcp_manager: Any,
    workspace_root: Path,
    git_context: Optional[Dict[str, Any]] = None,
) -> CommandResult:
    """Handle /status command - project status summary.

    Args:
        mcp_manager: MCP manager for file operations
        workspace_root: Path to workspace root
        git_context: Optional git context (branch, modified files, etc.)
    """
    logger.info("Executing /status command: git_context=%s", "yes" if git_context else "no")
    tasks, error = await read_tasks_file(mcp_manager, workspace_root)

    if error:
        return CommandResult(
            success=False,
            message=f"Ошибка чтения файла задач: {error}",
        )

    # Count by status
    todo_count = len([t for t in tasks if t.status == "todo"])
    in_progress_count = len([t for t in tasks if t.status == "in_progress"])
    done_count = len([t for t in tasks if t.status == "done"])

    # Analyze risks
    overdue_tasks = [t for t in tasks if t.is_overdue()]
    soon_tasks = [
        t for t in tasks
        if t.days_until_deadline() is not None
        and 0 <= t.days_until_deadline() <= 3
        and t.status != "done"
    ]

    # Build response
    lines = ["## Статус проекта\n"]

    # Task statistics
    lines.append("**Задачи:**")
    lines.append(f"- Todo: {todo_count}")
    lines.append(f"- In progress: {in_progress_count}")
    lines.append(f"- Done: {done_count}")

    # Git info
    if git_context:
        lines.append("\n**Git:**")
        if git_context.get("branch"):
            lines.append(f"- Ветка: {git_context['branch']}")
        if git_context.get("last_commit"):
            lines.append(f"- Последний коммит: {git_context['last_commit']}")
        if git_context.get("modified_files"):
            lines.append(f"- Измененные файлы: {len(git_context['modified_files'])}")

    # Risks
    risks = []
    if overdue_tasks:
        task_names = ", ".join(t.title for t in overdue_tasks[:3])
        if len(overdue_tasks) > 3:
            task_names += f" (+{len(overdue_tasks) - 3} еще)"
        risks.append(f"⚠️ {len(overdue_tasks)} задач просрочено ({task_names})")

    if soon_tasks:
        task_names = ", ".join(t.title for t in soon_tasks[:3])
        if len(soon_tasks) > 3:
            task_names += f" (+{len(soon_tasks) - 3} еще)"
        risks.append(f"⚠️ {len(soon_tasks)} задач с дедлайном в ближайшие 3 дня ({task_names})")

    if risks:
        lines.append("\n**Риски:**")
        lines.extend(risks)

    return CommandResult(
        success=True,
        message="\n".join(lines),
        tasks=tasks,
    )


async def handle_priority_command(
    mcp_manager: Any,
    workspace_root: Path,
    rag_context: Optional[str] = None,
) -> CommandResult:
    """Handle /priority command - priority recommendations.

    Args:
        mcp_manager: MCP manager for file operations
        workspace_root: Path to workspace root
        rag_context: Optional context from RAG (blockers, dependencies)
    """
    logger.info("Executing /priority command")
    tasks, error = await read_tasks_file(mcp_manager, workspace_root)

    if error:
        return CommandResult(
            success=False,
            message=f"Ошибка чтения файла задач: {error}",
        )

    # Filter to active tasks (not done)
    active_tasks = [t for t in tasks if t.status != "done"]

    if not active_tasks:
        return CommandResult(
            success=True,
            message="Нет активных задач. Всё сделано! 🎉",
            tasks=[],
        )

    # Sort by:
    # 1. Overdue first
    # 2. Then by priority (high > medium > low)
    # 3. Then by deadline (soonest first)
    def sort_key(task: Task) -> Tuple[int, int, int]:
        # Overdue gets highest priority (0)
        overdue = 0 if task.is_overdue() else 1

        # Priority order
        priority = PRIORITY_ORDER.get(task.priority, 2)

        # Deadline (earlier is better, no deadline = far future)
        days = task.days_until_deadline()
        deadline = days if days is not None else 9999

        return (overdue, priority, deadline)

    sorted_tasks = sorted(active_tasks, key=sort_key)
    top_tasks = sorted_tasks[:3]

    # Format as numbered list
    lines = []
    for i, task in enumerate(top_tasks, 1):
        parts = [f"{i}. {task.title}"]

        meta = []
        if task.assignee:
            meta.append(f"@{task.assignee}")
        if task.is_overdue():
            meta.append("просрочено!")
        elif task.deadline:
            days = task.days_until_deadline()
            if days == 0:
                meta.append("дедлайн сегодня")
            elif days == 1:
                meta.append("дедлайн завтра")
            elif days is not None and days <= 7:
                meta.append(f"через {days} дн.")
        meta.append(f"{task.priority} priority")

        parts.append(f"({', '.join(meta)})")
        lines.append(" ".join(parts))

    return CommandResult(
        success=True,
        message="\n".join(lines),
        tasks=top_tasks,
    )


async def handle_task_update(
    mcp_manager: Any,
    workspace_root: Path,
    query: str,
    new_status: Optional[str] = None,
    new_priority: Optional[str] = None,
    new_assignee: Optional[str] = None,
    new_deadline: Optional[str] = None,
) -> CommandResult:
    """Handle task update (status change, etc.).

    Args:
        mcp_manager: MCP manager for file operations
        workspace_root: Path to workspace root
        query: Search query to find the task
        new_status: New status (todo/in_progress/done)
        new_priority: New priority (high/medium/low)
        new_assignee: New assignee
        new_deadline: New deadline (YYYY-MM-DD)
    """
    logger.info(
        "Executing task update: query='%s' new_status=%s new_priority=%s new_assignee=%s",
        query[:30] if query else None, new_status, new_priority, new_assignee
    )
    tasks, error = await read_tasks_file(mcp_manager, workspace_root)

    if error:
        return CommandResult(
            success=False,
            message=f"Ошибка чтения файла задач: {error}",
        )

    if not tasks:
        return CommandResult(
            success=False,
            message="Задач нет",
        )

    # Find task
    task, matches = find_task_by_query(tasks, query)

    if not matches:
        return CommandResult(
            success=False,
            message=f"Задача не найдена: '{query}'",
        )

    if task is None:
        # Multiple matches - ask for clarification
        options = "\n".join(
            f"- {t.title} (id:{t.id}, @{t.assignee})" for t in matches[:5]
        )
        return CommandResult(
            success=False,
            message=f"Найдено несколько задач. Уточните:\n{options}",
        )

    # Apply updates
    changes = []
    if new_status and new_status != task.status:
        old_status = task.status
        task.status = new_status
        changes.append(f"статус: {old_status} → {new_status}")

    if new_priority and new_priority != task.priority:
        if not validate_priority(new_priority):
            return CommandResult(
                success=False,
                message=f"Недопустимый приоритет: {new_priority}",
            )
        old_priority = task.priority
        task.priority = new_priority.lower()
        changes.append(f"приоритет: {old_priority} → {new_priority}")

    if new_assignee:
        old_assignee = task.assignee
        task.assignee = new_assignee.lstrip("@")
        changes.append(f"исполнитель: @{old_assignee} → @{task.assignee}")

    if new_deadline:
        is_valid, warning = validate_deadline(new_deadline)
        if not is_valid:
            return CommandResult(
                success=False,
                message=f"Ошибка: {warning}",
            )
        old_deadline = task.deadline or "не указан"
        task.deadline = new_deadline
        changes.append(f"дедлайн: {old_deadline} → {new_deadline}")

    if not changes:
        return CommandResult(
            success=True,
            message=f"Задача '{task.title}' не изменена",
            tasks=[task],
        )

    # Write back
    error = await write_tasks_file(mcp_manager, workspace_root, tasks)
    if error:
        return CommandResult(
            success=False,
            message=f"Ошибка записи файла задач: {error}",
        )

    return CommandResult(
        success=True,
        message=f"Задача '{task.title}' (id:{task.id}) обновлена:\n- " + "\n- ".join(changes),
        tasks=[task],
    )


async def handle_task_delete(
    mcp_manager: Any,
    workspace_root: Path,
    query: str,
    confirmed: bool = False,
) -> CommandResult:
    """Handle task deletion.

    Args:
        mcp_manager: MCP manager for file operations
        workspace_root: Path to workspace root
        query: Search query to find the task
        confirmed: Whether deletion is confirmed
    """
    logger.info("Executing task delete: query='%s' confirmed=%s", query[:30] if query else None, confirmed)
    tasks, error = await read_tasks_file(mcp_manager, workspace_root)

    if error:
        return CommandResult(
            success=False,
            message=f"Ошибка чтения файла задач: {error}",
        )

    if not tasks:
        return CommandResult(
            success=False,
            message="Задач нет",
        )

    # Find task
    task, matches = find_task_by_query(tasks, query)

    if not matches:
        return CommandResult(
            success=False,
            message=f"Задача не найдена: '{query}'",
        )

    if task is None:
        # Multiple matches
        options = "\n".join(
            f"- {t.title} (id:{t.id}, @{t.assignee})" for t in matches[:5]
        )
        return CommandResult(
            success=False,
            message=f"Найдено несколько задач. Уточните:\n{options}",
        )

    # Require confirmation
    if not confirmed:
        return CommandResult(
            success=True,
            message=f"Вы уверены, что хотите удалить задачу \"{task.title}\" (id:{task.id})?",
            needs_confirmation=True,
            confirmation_context={
                "action": "delete",
                "task_id": task.id,
                "task_title": task.title,
            },
        )

    # Remove task
    tasks = [t for t in tasks if t.id != task.id]

    # Write back
    error = await write_tasks_file(mcp_manager, workspace_root, tasks)
    if error:
        return CommandResult(
            success=False,
            message=f"Ошибка записи файла задач: {error}",
        )

    return CommandResult(
        success=True,
        message=f"Задача \"{task.title}\" (id:{task.id}) удалена",
        tasks=[],
    )
