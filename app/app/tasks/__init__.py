"""Task management module for the team assistant."""

from .parser import parse_tasks, serialize_tasks, Task
from .commands import (
    handle_tasks_command,
    handle_add_command,
    handle_status_command,
    handle_priority_command,
    handle_task_update,
    handle_task_delete,
)

__all__ = [
    "parse_tasks",
    "serialize_tasks",
    "Task",
    "handle_tasks_command",
    "handle_add_command",
    "handle_status_command",
    "handle_priority_command",
    "handle_task_update",
    "handle_task_delete",
]
