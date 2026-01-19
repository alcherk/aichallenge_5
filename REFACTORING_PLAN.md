# Refactoring Plan: ChatGPT Proxy Service

**Created:** 2024-01-19
**Status:** Planning
**Estimated Scope:** ~1,589 lines of code to refactor

---

## Overview

This plan breaks down the refactoring of `chatgpt_client.py` and related modules into **5 independent work streams** that can be executed in parallel by different developers. Each stream has clearly defined boundaries and interfaces.

---

## Architecture Target

```
app/app/
├── services/
│   ├── chatgpt_client.py         # Orchestration only (~150 lines)
│   ├── message_preparation.py    # Message & tool conversion (~150 lines)
│   ├── rag_integration.py        # RAG retrieval & context (~200 lines)
│   ├── task_handler.py           # Task commands (/add, /tasks) (~300 lines)
│   ├── developer_assistant.py    # Dev mode, /review, /help (~250 lines)
│   └── responses_api.py          # OpenAI Responses API (~150 lines)
├── prompts.py                    # All system prompts centralized
├── constants.py                  # Magic numbers → named constants
└── utils/
    └── http_utils.py             # Shared HTTP utilities

frontend/src/
├── config.ts                     # Centralized configuration
└── utils/
    └── messages.ts               # Message handling utilities
```

---

## Work Streams

### Legend
- 🟢 **Independent** - Can start immediately
- 🟡 **Soft dependency** - Can start, but needs coordination
- 🔴 **Hard dependency** - Must wait for another stream

---

## Stream 1: Constants & Prompts Extraction
**Developer:** Dev A
**Status:** 🟢 Independent
**Estimated Files:** 2 new, 3 modified
**Risk:** Low

### Tasks

#### 1.1 Create `app/app/constants.py`
Extract all magic numbers and hardcoded values.

```python
"""Application-wide constants."""

class LLM:
    """LLM-related constants."""
    MAX_TOOL_ROUNDS = 8  # From chatgpt_client.py:233, 1502
    LOGGING_CHUNK_INTERVAL = 25  # From chatgpt_client.py:226


class RAG:
    """RAG subsystem constants."""
    REVIEW_TOP_K_MULTIPLIER = 3  # From chatgpt_client.py:892
    REVIEW_CONTEXT_MULTIPLIER = 2  # From chatgpt_client.py:917
    MIN_REVIEW_TOP_K = 15  # From chatgpt_client.py:892
    DEFAULT_MIN_CHUNKS = 2  # From filter.py


class Streaming:
    """Streaming constants."""
    CHUNK_SIZE = 24  # From ChatContainer.tsx:75
    INTERVAL_MS = 25  # From ChatContainer.tsx:76
```

**Source locations to extract from:**
- `chatgpt_client.py:226` - `chunk_count % 25`
- `chatgpt_client.py:233, 1502` - `max_rounds = 8`
- `chatgpt_client.py:892` - `max(15, settings.rag_top_k * 3)`
- `chatgpt_client.py:917` - `settings.rag_max_context_chars * 2`
- `ChatContainer.tsx:75-76` - streaming chunk values

#### 1.2 Create `app/app/prompts.py`
Extract all system prompts.

```python
"""Centralized system prompts for all modes."""

# Default system prompt (Russian)
DEFAULT_SYSTEM_PROMPT = """Ты — полезный ассистент..."""

# Staff Engineer review prompt
# Source: chatgpt_client.py:790-838, 1272-1320
REVIEW_SYSTEM_PROMPT = """Ты Staff Engineer с 15+ годами опыта...
... (full prompt from lines 790-838)
"""

# Help command prompt
# Source: chatgpt_client.py:841-850, 1322-1331
HELP_SYSTEM_PROMPT = """Ты ассистент разработчика...
... (full prompt)
"""

# Project-related questions prompt
# Source: chatgpt_client.py:853-860, 1335-1342
PROJECT_SYSTEM_PROMPT = """Ты ассистент разработчика...
... (full prompt)
"""

# Assistant mode prompt
# Source: chatgpt_client.py:352-360
ASSISTANT_MODE_SYSTEM_PROMPT = """You are an assistant that answers questions...
... (full prompt)
"""
```

**Source locations:**
- `chatgpt_client.py:149-162` - Default Russian prompt
- `chatgpt_client.py:790-838` - Review prompt (first occurrence)
- `chatgpt_client.py:1272-1320` - Review prompt (duplicate)
- `chatgpt_client.py:841-850` - Help prompt (first)
- `chatgpt_client.py:1322-1331` - Help prompt (duplicate)
- `chatgpt_client.py:853-860` - Project prompt (first)
- `chatgpt_client.py:1335-1342` - Project prompt (duplicate)

#### 1.3 Update imports in `chatgpt_client.py`
Replace inline prompts/constants with imports.

### Acceptance Criteria
- [ ] All magic numbers extracted to `constants.py`
- [ ] All system prompts extracted to `prompts.py`
- [ ] Original behavior unchanged (run existing tests)
- [ ] No duplicate prompt definitions remain

---

## Stream 2: Message & Tool Utilities
**Developer:** Dev B
**Status:** 🟢 Independent
**Estimated Files:** 2 new, 2 modified
**Risk:** Low

### Tasks

#### 2.1 Create `app/app/services/message_preparation.py`

Extract message and tool conversion functions.

```python
"""Message preparation and tool conversion utilities."""

from typing import Any

def prepare_messages(payload: "ChatRequest") -> list[dict]:
    """
    Prepare messages for API call, injecting system prompt if needed.

    Source: chatgpt_client.py:155-189 (_prepare_messages)
    """
    pass


def tools_to_responses_api(tools: list[dict]) -> list[dict]:
    """
    Convert tools to Responses API format.

    Source: chatgpt_client.py:57-98 (_tools_to_responses_api)
    """
    pass


def extract_text_from_responses(response: dict) -> str:
    """
    Extract text content from Responses API response.

    Source: chatgpt_client.py:101-113 (_extract_text_from_responses)
    """
    pass


def extract_tool_calls_from_responses(response: dict) -> list[dict]:
    """
    Extract tool calls from Responses API response.

    Source: chatgpt_client.py:116-140 (_extract_tool_calls_from_responses)
    """
    pass


def format_tool_result_for_responses(tool_call_id: str, result: str) -> dict:
    """
    Format tool result for Responses API continuation.

    Source: chatgpt_client.py:143-152 (_format_tool_result_for_responses)
    """
    pass
```

**Functions to extract:**
| Function | Current Location | Lines |
|----------|------------------|-------|
| `_prepare_messages` | `chatgpt_client.py` | 155-189 |
| `_tools_to_responses_api` | `chatgpt_client.py` | 57-98 |
| `_extract_text_from_responses` | `chatgpt_client.py` | 101-113 |
| `_extract_tool_calls_from_responses` | `chatgpt_client.py` | 116-140 |
| `_format_tool_result_for_responses` | `chatgpt_client.py` | 143-152 |

#### 2.2 Create `app/app/utils/http_utils.py`

Extract HTTP utilities.

```python
"""HTTP utilities for error handling and response parsing."""

import httpx


def extract_upstream_error(response: httpx.Response) -> dict:
    """
    Extract error details from upstream API response.

    Source: main.py:158-196 (_extract_upstream_error)
    Also duplicated at: main.py:425-450
    """
    pass
```

#### 2.3 Update imports
- Update `chatgpt_client.py` to import from `message_preparation.py`
- Update `main.py` to import from `http_utils.py`

### Acceptance Criteria
- [ ] All message/tool functions extracted with same signatures
- [ ] Duplicate error extraction consolidated
- [ ] Unit tests pass for extracted functions
- [ ] Integration tests pass

---

## Stream 3: RAG Integration Module
**Developer:** Dev C
**Status:** 🟢 Independent
**Estimated Files:** 1 new, 2 modified
**Risk:** Medium

### Tasks

#### 3.1 Create `app/app/services/rag_integration.py`

Consolidate all RAG-related logic from `chatgpt_client.py`.

```python
"""RAG retrieval and context injection service."""

from dataclasses import dataclass
from typing import Optional

from app.app.rag.chunkenizer_adapter import retrieve_chunks
from app.app.rag.filter import filter_by_similarity
from app.app.rag.context_builder import build_context_block
from app.app.rag.prompt_injector import inject_rag_context


@dataclass
class RAGResult:
    """Result of RAG retrieval."""
    context_block: str
    chunks_used: int
    total_retrieved: int
    filtered_count: int
    metadata: dict


async def retrieve_rag_context(
    query: str,
    *,
    top_k: int = 5,
    max_context_chars: int = 8000,
    min_similarity: float = 0.0,
    is_review: bool = False,
    is_help: bool = False,
) -> RAGResult:
    """
    Retrieve and filter RAG context for a query.

    This consolidates the RAG retrieval logic from:
    - chatgpt_client.py:877-1035 (call_chatgpt RAG block)
    - chatgpt_client.py:1359-1484 (stream_chatgpt RAG block)

    Args:
        query: The user query to search for
        top_k: Number of chunks to retrieve
        max_context_chars: Maximum context size
        min_similarity: Minimum similarity threshold
        is_review: If True, use review-specific settings (3x top_k, 2x context)
        is_help: If True, use help-specific settings (2x top_k)

    Returns:
        RAGResult with context and metadata
    """
    pass


def inject_context_into_messages(
    messages: list[dict],
    rag_result: RAGResult,
    *,
    strict_mode: bool = False,
) -> list[dict]:
    """
    Inject RAG context into message list.

    Args:
        messages: List of chat messages
        rag_result: RAG retrieval result
        strict_mode: If True, use strict injection (for Assistant Mode)

    Returns:
        Updated messages with RAG context
    """
    pass
```

**Code blocks to consolidate:**

| Block | Location | Lines | Notes |
|-------|----------|-------|-------|
| RAG retrieval (non-streaming) | `chatgpt_client.py` | 877-1035 | ~160 lines |
| RAG retrieval (streaming) | `chatgpt_client.py` | 1359-1484 | ~125 lines (duplicate) |
| Review RAG settings | `chatgpt_client.py` | 892, 917 | top_k/context multipliers |
| Help RAG settings | `chatgpt_client.py` | 949-950 | 2x top_k |

#### 3.2 Standardize RAG error handling

Create consistent error handling across RAG modules.

```python
# app/app/rag/errors.py
class RAGError(Exception):
    """Base exception for RAG subsystem."""
    pass

class ChunkenizationError(RAGError):
    """Error during chunk retrieval."""
    pass

class ContextBuildError(RAGError):
    """Error building context block."""
    pass
```

### Acceptance Criteria
- [ ] Single source of truth for RAG retrieval logic
- [ ] Review/help modes work with appropriate settings
- [ ] RAG metadata properly populated
- [ ] Error handling is consistent
- [ ] Both `call_chatgpt` and `stream_chatgpt` use same RAG function

---

## Stream 4: Task Handler Module
**Developer:** Dev D
**Status:** 🟢 Independent
**Estimated Files:** 1 new, 1 modified
**Risk:** Medium

### Tasks

#### 4.1 Create `app/app/services/task_handler.py`

Extract task command handling from `chatgpt_client.py`.

```python
"""Task command handler for /add, /tasks, /done, etc."""

from dataclasses import dataclass
from typing import Optional, Literal
from app.app.rag.project_detector import TaskCommandInfo


@dataclass
class TaskResult:
    """Result of task command execution."""
    success: bool
    message: str
    data: Optional[dict] = None
    should_return_early: bool = True  # If True, skip LLM call


class TaskHandler:
    """
    Handles task management commands.

    Consolidates logic from:
    - chatgpt_client.py:445-694 (call_chatgpt task block)
    - chatgpt_client.py:1177-1357 (stream_chatgpt task block)
    """

    def __init__(self, mcp_manager, workspace_root: str):
        self.mcp_manager = mcp_manager
        self.workspace_root = workspace_root

    async def process_command(
        self,
        command_info: TaskCommandInfo,
    ) -> TaskResult:
        """
        Process a task command and return result.

        Commands handled:
        - /tasks [filter] - List tasks
        - /add <description> - Add new task
        - /done <id> - Mark task complete
        - /delete <id> - Delete task
        - /edit <id> <changes> - Edit task
        - /assign <id> @user - Assign task
        - /priority <id> <level> - Set priority
        """
        pass

    async def _handle_tasks(self, filter_str: str) -> TaskResult:
        """List tasks with optional filter."""
        pass

    async def _handle_add(self, description: str, args: dict) -> TaskResult:
        """Add a new task."""
        pass

    async def _handle_done(self, task_id: str) -> TaskResult:
        """Mark task as complete."""
        pass

    async def _handle_delete(self, task_id: str) -> TaskResult:
        """Delete a task."""
        pass
```

**Code blocks to extract:**

| Block | Location | Lines | Notes |
|-------|----------|-------|-------|
| Task detection | `chatgpt_client.py` | 445-470 | Command parsing |
| Task routing | `chatgpt_client.py` | 470-694 | Switch on command type |
| MCP tool calls | `chatgpt_client.py` | 520-650 | Task CRUD operations |
| Duplicate in streaming | `chatgpt_client.py` | 1177-1357 | Same logic |

#### 4.2 Update `project_detector.py`

Move any task-specific parsing helpers to the task handler.

```python
# Functions to potentially move:
# - parse_add_args() (lines 561-610)
# - format_task_response() (if exists)
```

### Acceptance Criteria
- [ ] All task commands work identically to before
- [ ] Task handler is independently testable
- [ ] MCP integration is clean and mockable
- [ ] Error messages are user-friendly

---

## Stream 5: Developer Assistant Module
**Developer:** Dev E
**Status:** 🟡 Soft dependency on Stream 1 (prompts)
**Estimated Files:** 1 new, 1 modified
**Risk:** Medium

### Tasks

#### 5.1 Create `app/app/services/developer_assistant.py`

Extract developer assistant mode logic.

```python
"""Developer assistant mode for /review, /help, and project questions."""

from dataclasses import dataclass
from typing import Optional, Literal
from app.app.prompts import (
    REVIEW_SYSTEM_PROMPT,
    HELP_SYSTEM_PROMPT,
    PROJECT_SYSTEM_PROMPT,
)


@dataclass
class DevAssistantContext:
    """Context prepared for developer assistant mode."""
    system_prompt: str
    git_context: Optional[str]
    review_diff: Optional[str]
    mode: Literal["review", "help", "project", "normal"]
    metadata: dict


class DeveloperAssistant:
    """
    Handles developer assistant mode (/review, /help, project questions).

    Consolidates logic from:
    - chatgpt_client.py:695-875 (call_chatgpt dev assistant block)
    - chatgpt_client.py:1229-1357 (stream_chatgpt dev assistant block)
    """

    def __init__(self, mcp_manager):
        self.mcp_manager = mcp_manager

    async def prepare_context(
        self,
        user_query: str,
        workspace_root: str,
    ) -> DevAssistantContext:
        """
        Analyze query and prepare appropriate context.

        Returns DevAssistantContext with:
        - Appropriate system prompt (review/help/project)
        - Git context if relevant
        - Review diff if /review command
        - Mode indicator
        """
        pass

    def _detect_mode(self, query: str) -> Literal["review", "help", "project", "normal"]:
        """
        Detect which mode based on query.

        - /review ... -> "review"
        - /help ... -> "help"
        - Project-related question -> "project"
        - Otherwise -> "normal"
        """
        pass

    async def _get_review_diff(self, query: str, workspace: str) -> str:
        """
        Get diff for review command.

        Source: chatgpt_client.py:710-746
        """
        pass

    async def _get_git_context(self, workspace: str) -> str:
        """
        Get git context (status, recent commits).

        Source: chatgpt_client.py:770-785
        """
        pass
```

**Code blocks to extract:**

| Block | Location | Lines | Notes |
|-------|----------|-------|-------|
| Mode detection | `chatgpt_client.py` | 699-765 | /review, /help, project check |
| Git context retrieval | `chatgpt_client.py` | 770-785 | MCP git calls |
| Review diff | `chatgpt_client.py` | 710-746 | Commit parsing |
| System prompt selection | `chatgpt_client.py` | 787-860 | Conditional prompts |
| Duplicate in streaming | `chatgpt_client.py` | 1229-1357 | Same logic |

### Acceptance Criteria
- [ ] `/review` command works for all cases (uncommitted, HEAD, specific commit)
- [ ] `/help` command searches project correctly
- [ ] Project-related questions detected accurately
- [ ] Git context properly included
- [ ] Prompts imported from `prompts.py` (Stream 1)

---

## Stream 6: Frontend Configuration (Independent)
**Developer:** Dev F
**Status:** 🟢 Independent
**Estimated Files:** 2 new, 2 modified
**Risk:** Low

### Tasks

#### 6.1 Create `frontend/src/config.ts`

Centralize frontend configuration.

```typescript
/**
 * Centralized application configuration.
 * Values come from environment variables with sensible defaults.
 */

export const CONFIG = {
  // API configuration
  API_BASE_URL: import.meta.env.VITE_API_BASE_URL || '',

  // MCP configuration
  MCP_CONFIG_PATH: import.meta.env.VITE_MCP_CONFIG_PATH || '/api/config/mcp',
  WORKSPACE_ROOT: import.meta.env.VITE_WORKSPACE_ROOT || '/workspace',

  // Streaming configuration
  STREAMING: {
    CHUNK_SIZE: 24,  // Characters per tick
    INTERVAL_MS: 25,  // Milliseconds between ticks
  },
} as const;

export type Config = typeof CONFIG;
```

#### 6.2 Create `frontend/src/utils/messages.ts`

Extract message handling utilities.

```typescript
/**
 * Message creation and handling utilities.
 */

import type { Message, StructuredResponse } from '../types';

export const createErrorMessage = (
  error: StructuredResponse | Error | string
): Message => {
  let content: string;

  if (typeof error === 'string') {
    content = `Error: ${error}`;
  } else if (error instanceof Error) {
    content = `Error: ${error.message}`;
  } else {
    content = `Error: ${error?.error?.detail || error?.message || 'Request failed'}`;
  }

  return {
    role: 'assistant',
    content,
  };
};

export const createAssistantMessage = (content: string): Message => ({
  role: 'assistant',
  content,
});
```

#### 6.3 Update `ChatContainer.tsx`

Replace hardcoded values with config imports.

```typescript
// Before (lines 42-46)
const fallbackConfigPath = '/Users/lex/Projects/ai/AI_Challenge_5/week1_day1/mcp_servers.json';
const defaultWorkspaceRoot = '/Users/lex/Projects/ai/AI_Challenge_5/week1_day1';

// After
import { CONFIG } from '../../config';
const { MCP_CONFIG_PATH, WORKSPACE_ROOT } = CONFIG;
```

#### 6.4 Add backend config endpoint (optional)

```python
# app/app/main.py - new endpoint
@app.get("/api/config")
async def get_config():
    """Return client-safe configuration."""
    return {
        "mcp_config_path": settings.mcp_config_path,
        "workspace_root": settings.workspace_root,
        "rag_enabled": settings.rag_enabled,
    }
```

### Acceptance Criteria
- [ ] No hardcoded paths in frontend code
- [ ] Configuration is centralized
- [ ] Environment variables work in dev and production
- [ ] Error message creation is consistent

---

## Integration Phase

**Status:** 🔴 Hard dependency on Streams 1-5
**Developer:** All developers together
**When:** After all streams complete

### Tasks

#### I.1 Refactor `chatgpt_client.py` main functions

After all modules are extracted, refactor the main functions to use them:

```python
# app/app/services/chatgpt_client.py (target: ~150 lines)

from .message_preparation import prepare_messages, extract_text_from_responses
from .rag_integration import retrieve_rag_context, inject_context_into_messages
from .task_handler import TaskHandler
from .developer_assistant import DeveloperAssistant
from ..prompts import ASSISTANT_MODE_SYSTEM_PROMPT
from ..constants import LLM


async def call_chatgpt(payload: ChatRequest) -> tuple[StructuredResponse, dict]:
    """
    Main non-streaming chat function.
    Orchestrates modules but contains no business logic itself.
    """
    messages = prepare_messages(payload)
    rag_metadata = {}

    # Assistant Mode
    if payload.assistant_mode:
        return await _handle_assistant_mode(payload, messages)

    # Task Commands
    task_handler = TaskHandler(mcp_manager, workspace_root)
    task_cmd = detect_task_command(messages)
    if task_cmd:
        result = await task_handler.process_command(task_cmd)
        if result.should_return_early:
            return _build_task_response(result), {"task_command": True}

    # Developer Assistant
    if settings.dev_assistant_mode:
        dev_assistant = DeveloperAssistant(mcp_manager)
        context = await dev_assistant.prepare_context(user_query, workspace_root)
        messages = _apply_dev_context(messages, context)
        rag_metadata["dev_mode"] = context.mode

    # RAG Retrieval
    if settings.rag_enabled:
        rag_result = await retrieve_rag_context(
            user_query,
            is_review=context.mode == "review",
            is_help=context.mode == "help",
        )
        messages = inject_context_into_messages(messages, rag_result)
        rag_metadata.update(rag_result.metadata)

    # LLM Call
    response = await _call_openai(messages, payload)
    return response, rag_metadata
```

#### I.2 Run full test suite

```bash
pytest tests/ -v
```

#### I.3 Manual testing checklist

- [ ] Basic chat works
- [ ] Streaming works
- [ ] `/review` command works (uncommitted, HEAD, specific commit)
- [ ] `/help` command works
- [ ] `/tasks` command works
- [ ] `/add` command works
- [ ] RAG context injection works
- [ ] Assistant Mode works
- [ ] MCP tools work

---

## Coordination Notes

### Shared Interfaces

All streams must agree on these interfaces before starting:

```python
# Shared type definitions (create app/app/types.py if needed)

@dataclass
class RAGMetadata:
    chunks_used: int
    total_retrieved: int
    filtered_count: int
    context_chars: int
    query: str

@dataclass
class DevAssistantContext:
    system_prompt: str
    git_context: Optional[str]
    review_diff: Optional[str]
    mode: Literal["review", "help", "project", "normal"]
```

### Git Workflow

1. Create feature branch per stream: `refactor/stream-1-constants`, etc.
2. Each stream works independently
3. Integration branch: `refactor/integration`
4. Merge streams into integration branch
5. Final testing on integration branch
6. Merge to main

### Communication Points

- **Daily:** Quick sync on interface changes
- **Blockers:** Immediate Slack/Discord notification
- **Interface changes:** PR review required from affected streams

---

## Timeline Suggestion

```
Week 1:
├── Day 1-2: All streams start (parallel)
├── Day 3-4: Streams 1, 2, 6 complete (low risk)
├── Day 5: Streams 3, 4, 5 complete (medium risk)

Week 2:
├── Day 1-2: Integration phase
├── Day 3: Testing and bug fixes
├── Day 4: Code review
├── Day 5: Merge to main
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Interface mismatch between streams | Define interfaces upfront, review together |
| Breaking existing functionality | Keep original code until integration, run tests continuously |
| Merge conflicts | Each stream touches different code sections |
| Missing edge cases | Comprehensive manual testing checklist |

---

## Success Metrics

After refactoring:
- [ ] `chatgpt_client.py` reduced from 1,589 to ~150 lines
- [ ] No code duplication between `call_chatgpt` and `stream_chatgpt`
- [ ] Each module independently testable
- [ ] All existing tests pass
- [ ] No regression in functionality
