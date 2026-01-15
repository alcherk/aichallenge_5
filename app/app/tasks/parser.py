"""Parser for todo.md task format.

Task format: ## [priority] Title (id:xxx, @assignee, due:YYYY-MM-DD, status:xxx)

Example:
    ## [high] Fix authentication bug (id:a1b2c3d4, @alex, due:2024-01-20)

    Description of the task goes here.
"""

import re
import secrets
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger("app.tasks.parser")

# Regex for parsing task header
# ## [priority] Title (id:xxx, @assignee, due:YYYY-MM-DD, status:xxx)
TASK_HEADER_PATTERN = re.compile(
    r"^##\s+\[(?P<priority>high|medium|low)\]\s+"
    r"(?P<title>.+?)\s+"
    r"\(id:(?P<id>[a-f0-9]{8})"
    r"(?:,\s*@(?P<assignee>\w+))?"
    r"(?:,\s*due:(?P<deadline>\d{4}-\d{2}-\d{2}))?"
    r"(?:,\s*status:(?P<status>todo|in_progress|done))?"
    r"\)$",
    re.IGNORECASE,
)


@dataclass
class Task:
    """Represents a single task."""

    id: str
    title: str
    priority: str  # high, medium, low
    assignee: str
    status: str = "todo"  # todo, in_progress, done
    deadline: Optional[str] = None  # YYYY-MM-DD format
    description: str = ""

    def to_header(self) -> str:
        """Serialize task to markdown header format."""
        parts = [f"id:{self.id}"]

        if self.assignee:
            parts.append(f"@{self.assignee}")

        if self.deadline:
            parts.append(f"due:{self.deadline}")

        if self.status and self.status != "todo":
            parts.append(f"status:{self.status}")

        meta = ", ".join(parts)
        return f"## [{self.priority}] {self.title} ({meta})"

    def to_markdown(self) -> str:
        """Serialize task to full markdown format (header + description)."""
        lines = [self.to_header()]
        if self.description:
            lines.append("")
            lines.append(self.description)
        return "\n".join(lines)

    def is_overdue(self) -> bool:
        """Check if task is overdue."""
        if not self.deadline or self.status == "done":
            return False
        try:
            deadline_date = datetime.strptime(self.deadline, "%Y-%m-%d").date()
            return deadline_date < date.today()
        except ValueError:
            return False

    def days_until_deadline(self) -> Optional[int]:
        """Get days until deadline (negative if overdue)."""
        if not self.deadline:
            return None
        try:
            deadline_date = datetime.strptime(self.deadline, "%Y-%m-%d").date()
            return (deadline_date - date.today()).days
        except ValueError:
            return None

    def matches_query(self, query: str) -> bool:
        """Check if task matches a fuzzy search query."""
        query_lower = query.lower()
        return (
            query_lower in self.title.lower()
            or query_lower in self.description.lower()
            or query_lower in self.id.lower()
        )


def generate_task_id() -> str:
    """Generate a unique 8-character hex ID for a task."""
    return secrets.token_hex(4)


def parse_tasks(content: str) -> List[Task]:
    """Parse todo.md content into a list of tasks.

    Args:
        content: The raw content of todo.md file

    Returns:
        List of Task objects
    """
    tasks: List[Task] = []
    current_task: Optional[Task] = None
    description_lines: List[str] = []

    lines = content.split("\n")

    for line in lines:
        # Try to match task header
        match = TASK_HEADER_PATTERN.match(line.strip())

        if match:
            # Save previous task if exists
            if current_task is not None:
                current_task.description = "\n".join(description_lines).strip()
                tasks.append(current_task)

            # Create new task
            groups = match.groupdict()
            current_task = Task(
                id=groups["id"],
                title=groups["title"],
                priority=groups["priority"].lower(),
                assignee=groups.get("assignee") or "",
                status=groups.get("status") or "todo",
                deadline=groups.get("deadline"),
                description="",
            )
            description_lines = []
        elif current_task is not None:
            # Accumulate description lines
            description_lines.append(line)

    # Don't forget the last task
    if current_task is not None:
        current_task.description = "\n".join(description_lines).strip()
        tasks.append(current_task)

    logger.debug("Parsed %d tasks from content", len(tasks))
    return tasks


def serialize_tasks(tasks: List[Task]) -> str:
    """Serialize a list of tasks to todo.md format.

    Args:
        tasks: List of Task objects

    Returns:
        The todo.md content as a string
    """
    if not tasks:
        return "# Tasks\n\nNo tasks yet.\n"

    sections = ["# Tasks\n"]

    for task in tasks:
        sections.append(task.to_markdown())

    return "\n\n".join(sections) + "\n"


def find_task_by_query(tasks: List[Task], query: str) -> Tuple[Optional[Task], List[Task]]:
    """Find a task by fuzzy search query.

    Args:
        tasks: List of tasks to search
        query: Search query (partial title, description, or ID)

    Returns:
        Tuple of (exact_match, all_matches)
        - exact_match: Single task if only one matches, None otherwise
        - all_matches: All matching tasks
    """
    matches = [task for task in tasks if task.matches_query(query)]

    if len(matches) == 1:
        return matches[0], matches

    return None, matches


def validate_deadline(deadline: str) -> Tuple[bool, Optional[str]]:
    """Validate a deadline string.

    Args:
        deadline: Date string in YYYY-MM-DD format

    Returns:
        Tuple of (is_valid, warning_message)
    """
    try:
        deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()

        if deadline_date < date.today():
            return True, f"Deadline {deadline} is in the past"

        return True, None
    except ValueError:
        return False, f"Invalid date format: {deadline}. Use YYYY-MM-DD"


def validate_priority(priority: str) -> bool:
    """Validate priority value."""
    return priority.lower() in ("high", "medium", "low")


def validate_status(status: str) -> bool:
    """Validate status value."""
    return status.lower() in ("todo", "in_progress", "done")
