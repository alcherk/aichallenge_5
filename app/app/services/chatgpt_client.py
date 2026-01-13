from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging
import os

import httpx

from ..config import get_settings
from ..schemas import ChatRequest, ChatResponse
from ..mcp.manager import ensure_mcp_manager
from ..rag.chunkenizer_adapter import retrieve_chunks
from ..rag.context_builder import build_context_block
from ..rag.prompt_injector import inject_rag_context
from ..rag.filter import filter_by_similarity
from ..rag.reranker import get_reranker
from ..rag.project_detector import is_project_question, extract_help_query, extract_review_query, build_review_rag_queries
from ..rag.git_context import get_git_context, format_git_context, get_review_diff
from ..rag.context_builder import build_review_context

logger = logging.getLogger("app.openai")


def _truthy_env(name: str) -> bool:
    v = (os.getenv(name, "") or "").strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


def _json_preview(value: Any, *, limit: int = 8000) -> tuple[str, bool]:
    try:
        s = json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        s = str(value)
    if len(s) > limit:
        return (s[:limit] + "…", True)
    return (s, False)

def _tools_to_responses_api(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert Chat Completions-style tools into Responses API tool definitions.

    Chat Completions tool:
      {"type":"function","function":{"name": "...", "description": "...", "parameters": {...}}}

    Responses API tool:
      {"type":"function","name":"...","description":"...","parameters": {...}}
    """
    out: List[Dict[str, Any]] = []
    for t in tools or []:
        if not isinstance(t, dict):
            continue
        t_type = t.get("type")
        if t_type != "function":
            # Pass through unknown tool types if present (future-proof).
            out.append(t)
            continue

        # Already in Responses format?
        if isinstance(t.get("name"), str) and t.get("name"):
            out.append(t)
            continue

        fn = t.get("function") or {}
        if not isinstance(fn, dict):
            fn = {}
        name = fn.get("name")
        if not isinstance(name, str) or not name:
            # Skip invalid tools; upstream will error otherwise.
            continue

        out.append(
            {
                "type": "function",
                "name": name,
                "description": fn.get("description"),
                "parameters": fn.get("parameters"),
            }
        )
    return out


def _messages_to_responses_input(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert Chat Completions-style messages -> Responses API `input`.
    Minimal shape used here:
      [{"role": "...", "content": "..."}]
    """
    out: List[Dict[str, Any]] = []
    for m in messages:
        role = m.get("role")
        content = m.get("content")
        if role and content is not None:
            out.append({"role": role, "content": content})
    return out


def _extract_text_from_responses(response_json: Dict[str, Any]) -> str:
    """
    Extract assistant text from a Responses API response object.
    """
    output = response_json.get("output") or []
    parts: List[str] = []
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "message":
                continue
            if item.get("role") != "assistant":
                continue
            content = item.get("content") or []
            if isinstance(content, list):
                for c in content:
                    if not isinstance(c, dict):
                        continue
                    # Most common: {"type":"output_text","text":"..."}
                    if c.get("type") in ("output_text", "text") and isinstance(c.get("text"), str):
                        parts.append(c["text"])
            elif isinstance(content, str):
                parts.append(content)
    return "".join(parts)


def _responses_usage_to_chat_usage(response_json: Dict[str, Any]) -> Optional[Dict[str, int]]:
    usage = response_json.get("usage")
    if not isinstance(usage, dict):
        return None
    prompt = usage.get("input_tokens")
    completion = usage.get("output_tokens")
    total = usage.get("total_tokens")
    if isinstance(prompt, int) and isinstance(completion, int) and isinstance(total, int):
        return {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": total}
    return None


def _prepare_messages(payload: ChatRequest) -> List[Dict[str, Any]]:
    """
    Prepare OpenAI messages from the inbound request (includes system prompt if missing).

    Note: we intentionally return raw dicts (not pydantic models) because
    OpenAI tool messages use additional roles/fields not present in our schemas.
    """
    messages = [m.dict() for m in payload.messages]

    has_system_message = any(msg.get("role") == "system" for msg in messages)
    if not has_system_message:
        system_prompt = """Ты помощник-прокси между пользователем и системой.

Твоя задача — сначала ПОНЯТЬ задачу, а потом решать.

Формат ответа: обычный текст или Markdown.

Если информации недостаточно, задай уточняющие вопросы.

Если информации достаточно и можно решить задачу, предоставь подробное решение.

Правила:
- Не придумывай ответ на задачу, если нет данных — сперва задавай вопросы.
- Когда считаешь, что вопросов достаточно, предоставь итоговый ответ.
- Используй Markdown для форматирования (заголовки, списки, код и т.д.)."""

        messages.insert(
            0,
            {
                "role": "system",
                "content": system_prompt,
            },
        )

    return messages


def _normalize_tool_calls(tool_calls: Any) -> List[Dict[str, Any]]:
    """
    Ensure tool_calls are in the OpenAI-required shape:
    [{id, type:"function", function:{name, arguments}}...]
    """
    out: List[Dict[str, Any]] = []
    if not isinstance(tool_calls, list):
        return out
    for tc in tool_calls:
        if not isinstance(tc, dict):
            continue
        fn = tc.get("function") or {}
        if not isinstance(fn, dict):
            fn = {}
        out.append(
            {
                "id": tc.get("id"),
                "type": tc.get("type") or "function",
                "function": {
                    "name": fn.get("name"),
                    "arguments": fn.get("arguments") or "",
                },
            }
        )
    return out


async def _generate_single_answer(
    payload: ChatRequest,
    messages: List[Dict[str, Any]],
    settings: Any,
    headers: Dict[str, str],
    mgr: Any,
    resp_tools: List[Dict[str, Any]],
) -> ChatResponse:
    """
    Helper function to generate a single LLM answer given prepared messages.
    Used for comparison mode to generate baseline and enhanced answers.
    """
    base_input = _messages_to_responses_input(messages)
    
    max_rounds = 8
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        previous_response_id: Optional[str] = None
        for _ in range(max_rounds):
            body: Dict[str, Any] = {
                "model": payload.model or settings.openai_model,
                "input": base_input,
            }
            if previous_response_id:
                body["previous_response_id"] = previous_response_id

            if resp_tools:
                body["tools"] = resp_tools
                body["tool_choice"] = "auto"

            if payload.temperature is not None:
                body["temperature"] = payload.temperature
            if payload.max_tokens is not None:
                body["max_tokens"] = payload.max_tokens

            base = str(settings.openai_api_base).rstrip("/")
            path = str(getattr(settings, "openai_chat_path", "chat/responses")).lstrip("/")
            url = f"{base}/{path}"
            
            response = await client.post(url, json=body, headers=headers)
            response.raise_for_status()
            data = response.json()

            # Handle tool calls (same as original)
            output = data.get("output") or []
            function_calls: List[Dict[str, Any]] = []
            if isinstance(output, list):
                for item in output:
                    if isinstance(item, dict) and item.get("type") == "function_call":
                        function_calls.append(item)

            if function_calls:
                if mgr is None:
                    raise RuntimeError("Model requested tool calls but MCP is not enabled")
                response_id = data.get("id")
                if not isinstance(response_id, str) or not response_id:
                    raise RuntimeError("Upstream returned tool calls but no response id was provided")

                tool_outputs: List[Dict[str, Any]] = []
                for fc in function_calls:
                    call_id = fc.get("call_id") or fc.get("id")
                    name = fc.get("name")
                    args_raw = fc.get("arguments") or "{}"
                    if not isinstance(call_id, str) or not call_id:
                        continue
                    try:
                        args = json.loads(args_raw) if isinstance(args_raw, str) else {}
                    except Exception:
                        args = {}
                    try:
                        result = await mgr.call_openai_tool(str(name), args)
                        tool_outputs.append({
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps(result, ensure_ascii=False),
                        })
                    except Exception as e:
                        tool_outputs.append({
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps(
                                {"error": {"type": type(e).__name__, "detail": str(e)}},
                                ensure_ascii=False,
                            ),
                        })

                previous_response_id = response_id
                base_input = tool_outputs
                continue

            # Final text response
            full_text = _extract_text_from_responses(data)
            usage_obj = _responses_usage_to_chat_usage(data)
            return ChatResponse(
                id=str(data.get("id") or "resp"),
                model=str(data.get("model") or (payload.model or settings.openai_model)),
                choices=[{
                    "index": 0,
                    "message": {"role": "assistant", "content": full_text},
                    "finish_reason": "stop",
                }],
                usage=usage_obj,
            )

    raise RuntimeError("Tool loop exceeded maximum rounds")


async def call_chatgpt(payload: ChatRequest) -> Tuple[ChatResponse, Optional[Dict[str, Any]]]:
    settings = get_settings()

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }

    messages = _prepare_messages(payload)
    
    # Store baseline messages for comparison mode (before RAG processing)
    baseline_messages = None
    rag_metadata = None  # Will store RAG decision-making metadata
    
    # Developer assistant mode: detect project questions and /help command
    is_help_command = False
    is_review_command = False
    review_commit_hash = None
    is_project_related = False
    git_context_str = ""
    git_context = None
    dev_assistant_system_prompt = None
    review_diff_data = None
    
    if settings.dev_assistant_mode:
        user_messages = [m for m in messages if m.get("role") == "user"]
        if user_messages:
            user_query = user_messages[-1].get("content", "")
            if user_query and user_query.strip():
                # Check for /review command
                if user_query.strip().lower().startswith("/review"):
                    is_review_command = True
                    original_query = user_query
                    _, review_commit_hash = extract_review_query(user_query)
                    logger.info(f"/review command detected: '{original_query}' -> commit={review_commit_hash}")
                    # For /review, we'll get diff and build RAG queries from it
                    is_project_related = True
                    
                    # Get MCP manager for git diff
                    logger.info(f"Review command: getting git diff (commit={review_commit_hash or 'uncommitted'}, workspace={payload.workspace_root or settings.workspace_root})")
                    try:
                        mcp_mgr = await ensure_mcp_manager(
                            mcp_config_path=(
                                payload.mcp_config_path or settings.mcp_config_path or None
                            ),
                            workspace_root=Path(payload.workspace_root or settings.workspace_root),
                        )
                        
                        if mcp_mgr:
                            logger.info(f"MCP manager obtained for review: {type(mcp_mgr).__name__}")
                            review_diff_data = await get_review_diff(
                                mcp_mgr,
                                Path(payload.workspace_root or settings.workspace_root),
                                review_commit_hash
                            )
                            if review_diff_data:
                                if not review_diff_data.get("has_changes", False):
                                    # No changes to review - set a clear message that will be returned
                                    messages[-1]["content"] = "I checked your repository, but there are no uncommitted changes to review. All files are up to date. If you want to review a specific commit, use `/review commit` or `/review <commit-hash>`."
                                    logger.info(f"Review command: no changes found (commit={review_commit_hash or 'uncommitted'})")
                                    # Mark that we've handled this case so RAG doesn't try to process it
                                    review_diff_data = None
                                else:
                                    changed_files = review_diff_data.get('changed_files', [])
                                    diff_length = len(review_diff_data.get('diff', ''))
                                    logger.info(f"Review diff retrieved successfully: {len(changed_files)} files changed, diff_length={diff_length} chars, commit={review_commit_hash or 'uncommitted'}")
                                    # Update message to indicate we're ready for review
                                    messages[-1]["content"] = "Please review the following code changes."
                            else:
                                logger.warning(f"Failed to retrieve review diff: review_diff_data is None (commit={review_commit_hash or 'uncommitted'})")
                                # Set helpful error message but keep it as a review request
                                messages[-1]["content"] = "I couldn't retrieve the git diff for review. Please make sure you're in a git repository and have uncommitted changes, or specify a commit hash like `/review commit` or `/review HEAD~1`."
                        else:
                            logger.warning("MCP manager is None - cannot retrieve git diff")
                    except Exception as e:
                        logger.error(f"Failed to get review diff: {e}", exc_info=True)
                        # Continue - will handle error in review flow
                
                # Check for /help command
                elif user_query.strip().lower().startswith("/help"):
                    is_help_command = True
                    original_query = user_query
                    user_query = extract_help_query(user_query)
                    logger.info(f"/help command detected: '{original_query}' -> '{user_query}'")
                    # Update the user message with extracted query for RAG search
                    messages[-1]["content"] = user_query
                    is_project_related = True
                    # For /help, we want to search in RAG with the extracted question
                    # The query will be used for RAG retrieval below
                else:
                    # Check if question is about the project
                    is_project_related = is_project_question(user_query)
                
                # Always set system prompt for /review and /help commands, even if not project-related
                # If project-related, get git context and set system prompt
                if is_review_command or is_help_command or is_project_related:
                    # Get MCP manager for git context (always try builtin manager for git server)
                    try:
                        # Always try to get builtin MCP manager (includes git server)
                        mcp_mgr = await ensure_mcp_manager(
                            mcp_config_path=(
                                payload.mcp_config_path or settings.mcp_config_path or None
                            ),
                            workspace_root=Path(payload.workspace_root or settings.workspace_root),
                        )
                        
                        if mcp_mgr:
                            git_context = await get_git_context(mcp_mgr, Path(payload.workspace_root or settings.workspace_root))
                            if git_context:
                                git_context_str = format_git_context(git_context)
                                logger.debug(f"Git context retrieved: branch={git_context.get('branch')}")
                    except Exception as e:
                        logger.warning(f"Failed to get git context for developer assistant: {e}", exc_info=True)
                        # Continue without git context - not critical
                    
                    # Set developer assistant system prompt
                    if is_review_command:
                        logger.info("Setting Staff Engineer system prompt for /review command")
                        # Staff engineer system prompt for code review
                        dev_assistant_system_prompt = (
                            "Ты Staff Engineer, проводящий code review. "
                            "Твоя задача - найти РЕАЛЬНЫЕ проблемы в коде и указать КОНКРЕТНЫЕ места с примерами из diff.\n\n"
                            "ВАЖНЫЕ ПРАВИЛА:\n"
                            "1. Указывай ТОЛЬКО те категории, где есть РЕАЛЬНЫЕ проблемы\n"
                            "2. Для каждой проблемы указывай:\n"
                            "   - Точное место в коде (файл, строка, функция)\n"
                            "   - Фрагмент кода из diff с проблемой\n"
                            "   - Конкретное объяснение проблемы\n"
                            "   - Предложение исправления с примером кода\n"
                            "3. Если по категории нет проблем - НЕ упоминай её вообще\n"
                            "4. Используй формат diff для показа проблемных мест\n\n"
                            "КАТЕГОРИИ ДЛЯ ПРОВЕРКИ (указывай только если есть проблемы):\n\n"
                            "АРХИТЕКТУРА:\n"
                            "- Нарушение паттернов проекта\n"
                            "- Неправильная структура модулей\n"
                            "- Нарушение SOLID/DRY/KISS\n"
                            "- Проблемы интеграции\n\n"
                            "СТИЛЬ КОДА:\n"
                            "- Несоответствие конвенциям\n"
                            "- Плохое именование\n"
                            "- Отсутствие/неправильные комментарии\n\n"
                            "БАГИ:\n"
                            "- Отсутствие обработки ошибок\n"
                            "- Edge cases не обработаны\n"
                            "- Race conditions\n"
                            "- Null/undefined проблемы\n\n"
                            "ПРОИЗВОДИТЕЛЬНОСТЬ:\n"
                            "- Неэффективные алгоритмы\n"
                            "- N+1 queries\n"
                            "- Лишние операции\n\n"
                            "БЕЗОПАСНОСТЬ:\n"
                            "- SQL injection, XSS риски\n"
                            "- Отсутствие валидации\n"
                            "- Секреты в коде\n\n"
                            "ФОРМАТ ОТВЕТА:\n"
                            "Для каждой проблемы используй такой формат:\n"
                            "```\n"
                            "📁 файл.py:123\n"
                            "```diff\n"
                            "- старый_код\n"
                            "+ новый_код\n"
                            "```\n"
                            "❌ Проблема: [описание]\n"
                            "✅ Исправление: [предложение]\n\n"
                            "Используй предоставленный контекст из RAG для проверки соответствия "
                            "архитектуре и стилю проекта. Цитируй источники как [doc_name:doc_id:chunk_index]. "
                            "Если проблем нет - скажи кратко, что код выглядит хорошо."
                        )
                    elif is_help_command:
                        # Enhanced prompt for /help command - focus on code search
                        dev_assistant_system_prompt = (
                            "Ты ассистент разработчика для этого проекта. "
                            "Пользователь задал вопрос через команду /help. "
                            "Используй предоставленный контекст из RAG для поиска релевантных классов, функций, моделей и кода. "
                            "Найди конкретные файлы, классы, функции и их реализации, которые относятся к вопросу. "
                            "Укажи точные пути к файлам, имена классов и функций. "
                            "Если в контексте есть примеры кода, включи их в ответ. "
                            "Цитируй источники как [doc_name:doc_id:chunk_index]. "
                            "Если нужно больше информации, можешь использовать MCP инструменты для чтения файлов."
                        )
                    else:
                        # Standard prompt for automatic project detection
                        dev_assistant_system_prompt = (
                            "Ты ассистент разработчика для этого проекта. "
                            "Используй предоставленную документацию и Git контекст для ответов. "
                            "Отвечай на основе документации проекта. "
                            "Если информации нет в документации, используй Git контекст (ветка, измененные файлы). "
                            "Цитируй источники как [doc_name:doc_id:chunk_index]. "
                            "Если вопрос касается кода, можешь использовать MCP инструменты для чтения файлов."
                        )
                    
                    # Inject system prompt if not already present
                    system_messages = [m for m in messages if m.get("role") == "system"]
                    if not system_messages:
                        messages.insert(0, {"role": "system", "content": dev_assistant_system_prompt})
                        logger.info(f"System prompt injected for {'/review' if is_review_command else '/help' if is_help_command else 'project question'}")
                    else:
                        # Replace existing system message for commands to ensure they take precedence
                        if is_review_command or is_help_command:
                            messages[0]["content"] = dev_assistant_system_prompt
                            logger.info(f"System prompt replaced for {'/review' if is_review_command else '/help'}")
                        else:
                            # Append to existing system message for project questions
                            existing_system = system_messages[0].get("content", "")
                            messages[0]["content"] = f"{existing_system}\n\n{dev_assistant_system_prompt}"
    
    # RAG retrieval (if enabled)
    if settings.rag_enabled:
        # Special handling for /review command
        if is_review_command and review_diff_data and review_diff_data.get("has_changes", False):
            # Build RAG queries from diff and changed files
            changed_files = review_diff_data.get("changed_files", [])
            diff = review_diff_data.get("diff", "")
            rag_queries = build_review_rag_queries(changed_files, diff)
            
            # Retrieve chunks for each query and merge
            all_chunks = []
            seen_chunk_ids = set()
            
            for rag_query in rag_queries:
                # Use higher top_k for review (15-20 chunks per query)
                review_top_k = max(15, settings.rag_top_k * 3)
                logger.debug(f"Review RAG query: '{rag_query[:50]}...' top_k={review_top_k}")
                
                query_chunks = await retrieve_chunks(
                    query=rag_query,
                    top_k=review_top_k,
                    base_url=settings.chunkenizer_api_url,
                )
                
                # Deduplicate chunks by document_id + chunk_index
                for chunk in query_chunks:
                    chunk_id = f"{chunk.get('document_id', '')}:{chunk.get('chunk_index', 0)}"
                    if chunk_id not in seen_chunk_ids:
                        seen_chunk_ids.add(chunk_id)
                        all_chunks.append(chunk)
            
            logger.info(f"Review RAG: retrieved {len(all_chunks)} unique chunks from {len(rag_queries)} queries")
            
            # Build review context with diff + RAG chunks (even if no RAG chunks, we still have the diff)
            review_context = build_review_context(
                diff=diff,
                changed_files=changed_files,
                rag_chunks=all_chunks if all_chunks else [],
                git_context=git_context,
                commit_hash=review_commit_hash,
                max_chars=settings.rag_max_context_chars * 2,  # More space for review
            )
            
            if review_context:
                # Update user message with review request
                messages[-1]["content"] = "Please review the following code changes:\n\n" + review_context
                logger.info(f"Review context built and injected into messages (diff_len={len(diff)}, rag_chunks={len(all_chunks)})")
            else:
                logger.warning("Review context is empty - this should not happen if diff exists")
                # Fallback: at least include the diff
                if diff:
                    messages[-1]["content"] = "Please review the following code changes:\n\nCODE DIFF:\n\n" + diff
                    logger.info("Using diff-only fallback for review")
        elif is_review_command:
            # review_diff_data is None or has_changes is False
            # This case should have been handled earlier - message content already set to error/info
            # Don't run standard RAG on the error message
            logger.info(f"Review command completed (no diff to process): review_diff_data={review_diff_data is not None}, message_content_len={len(messages[-1].get('content', '')) if messages else 0}")
        else:
            # Standard RAG retrieval for /help and other queries
            user_messages = [m for m in messages if m.get("role") == "user"]
            if user_messages:
                query = user_messages[-1].get("content", "")
                if query and query.strip():
                    # For /help commands, use higher top_k to get more relevant results
                    top_k = settings.rag_top_k * 2 if is_help_command else settings.rag_top_k
                    logger.info(
                        "RAG retrieval starting query_len=%d top_k=%d help_mode=%s",
                        len(query),
                        top_k,
                        is_help_command,
                    )
                    chunks = await retrieve_chunks(
                        query=query,
                        top_k=top_k,
                        base_url=settings.chunkenizer_api_url,
                    )
                    if chunks:
                        # Store baseline messages for comparison mode (before filtering/reranking)
                        if settings.rag_compare_mode:
                            baseline_messages = [m.copy() for m in messages]
                            baseline_context = build_context_block(chunks, settings.rag_max_context_chars)
                            if baseline_context:
                                baseline_messages = inject_rag_context(baseline_messages, baseline_context)
                            logger.debug("RAG comparison mode: baseline messages prepared chunks=%d", len(chunks))
                        
                        # Collect initial chunk scores for metadata
                        initial_scores = [chunk.get("score", 0.0) for chunk in chunks]
                        
                        # Second-stage filtering by similarity threshold
                        filtered_chunks, filter_metadata = filter_by_similarity(
                            chunks,
                            threshold=settings.rag_min_similarity,
                            min_chunks=settings.rag_min_chunks,
                        )
                        
                        # Collect filtered chunk scores
                        filtered_scores = [chunk.get("score", 0.0) for chunk in filtered_chunks]
                        
                        # Reranking (if enabled)
                        reranker_applied = False
                        if settings.rag_reranker_enabled:
                            reranker = get_reranker(settings.rag_reranker_type)
                            filtered_chunks = await reranker.rerank(query, filtered_chunks)
                            reranker_applied = True
                            logger.debug(
                                "RAG reranker applied type=%s chunks=%d",
                                settings.rag_reranker_type,
                                len(filtered_chunks),
                            )
                        
                        # Build context from filtered/reranked chunks
                        context = build_context_block(filtered_chunks, settings.rag_max_context_chars)
                        if context:
                            # Add git context if available (for developer assistant mode)
                            if git_context_str:
                                context = f"{git_context_str}\n\n{context}"
                            messages = inject_rag_context(messages, context)
                            
                            # Build RAG metadata for UI
                            rag_metadata = {
                                "enabled": True,
                                "initial_chunks": len(chunks),
                                "filtered_chunks": filter_metadata["filtered_count"],
                                "final_chunks": len(filtered_chunks),
                                "threshold": settings.rag_min_similarity,
                                "fallback_triggered": filter_metadata["fallback_triggered"],
                                "reranker_enabled": settings.rag_reranker_enabled,
                                "reranker_type": settings.rag_reranker_type if settings.rag_reranker_enabled else None,
                                "scores_range": filter_metadata["scores_range"],
                                "initial_scores": initial_scores,
                                "filtered_scores": filtered_scores,
                                "context_size": len(context),
                                "compare_mode": settings.rag_compare_mode,
                            }
                            
                            logger.info(
                                "RAG context injected initial_k=%d filtered_k=%d final_k=%d "
                                "threshold=%.3f fallback=%s reranker=%s context_size=%d",
                                len(chunks),
                                filter_metadata["filtered_count"],
                                len(filtered_chunks),
                                settings.rag_min_similarity,
                                filter_metadata["fallback_triggered"],
                                settings.rag_reranker_type if settings.rag_reranker_enabled else "none",
                                len(context),
                            )
                        else:
                            rag_metadata = {"enabled": True, "initial_chunks": len(chunks), "error": "Context block empty"}
                            logger.debug("RAG context block empty after formatting")
                    else:
                        rag_metadata = {"enabled": True, "initial_chunks": 0, "error": "No chunks retrieved"}
                        logger.debug("RAG retrieval returned no chunks")
                else:
                    logger.debug("RAG skipped: empty user query")
            else:
                logger.debug("RAG skipped: no user messages found")
    else:
        logger.debug("RAG disabled")
    
    mcp_enabled = bool(payload.mcp_enabled) if payload.mcp_enabled is not None else bool(
        payload.mcp_config_path or settings.mcp_config_path
    )
    mgr = await ensure_mcp_manager(
        mcp_config_path=(
            (payload.mcp_config_path or settings.mcp_config_path or None) if mcp_enabled else None
        ),
        workspace_root=Path(payload.workspace_root or settings.workspace_root),
    )
    tools = mgr.openai_tools() if mgr is not None else []
    resp_tools = _tools_to_responses_api(tools) if tools else []

    # Comparison mode: generate baseline and enhanced answers
    if settings.rag_compare_mode and settings.rag_enabled and baseline_messages:
        logger.info("RAG comparison mode: generating baseline and enhanced answers")
        try:
            baseline_response = await _generate_single_answer(
                payload, baseline_messages, settings, headers, mgr, resp_tools
            )
            enhanced_response = await _generate_single_answer(
                payload, messages, settings, headers, mgr, resp_tools
            )
            # Add comparison metadata
            if rag_metadata:
                rag_metadata["baseline_answer"] = baseline_response.choices[0].message.content
                rag_metadata["enhanced_answer"] = enhanced_response.choices[0].message.content
            return enhanced_response, rag_metadata
        except Exception as e:
            logger.error("RAG comparison mode error: %s", e, exc_info=True)
            # Fall back to normal mode
            logger.warning("Falling back to normal mode due to comparison error")
    
    # Normal mode: generate single answer
    response = await _generate_single_answer(payload, messages, settings, headers, mgr, resp_tools)
    return response, rag_metadata


async def stream_chatgpt(payload: ChatRequest):
    """
    Yields decoded streaming chunks from OpenAI chat.completions.
    Each yielded item is a dict like the non-streaming response chunks:
    - {"choices":[{"delta":{"content":"..."}, ...}], ...}
    """
    settings = get_settings()

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }

    base_messages = _prepare_messages(payload)
    
    # Developer assistant mode: detect project questions and /help command
    is_help_command = False
    is_review_command = False
    review_commit_hash = None
    is_project_related = False
    git_context_str = ""
    git_context = None
    dev_assistant_system_prompt = None
    review_diff_data = None
    
    if settings.dev_assistant_mode:
        user_messages = [m for m in base_messages if m.get("role") == "user"]
        if user_messages:
            user_query = user_messages[-1].get("content", "")
            if user_query and user_query.strip():
                # Check for /review command
                if user_query.strip().lower().startswith("/review"):
                    is_review_command = True
                    original_query = user_query
                    _, review_commit_hash = extract_review_query(user_query)
                    logger.info(f"/review command detected (stream): '{original_query}' -> commit={review_commit_hash}")
                    # For /review, we'll get diff and build RAG queries from it
                    is_project_related = True
                    
                    # Get MCP manager for git diff
                    logger.info(f"Review command (stream): getting git diff (commit={review_commit_hash or 'uncommitted'}, workspace={payload.workspace_root or settings.workspace_root})")
                    try:
                        mcp_mgr = await ensure_mcp_manager(
                            mcp_config_path=(
                                payload.mcp_config_path or settings.mcp_config_path or None
                            ),
                            workspace_root=Path(payload.workspace_root or settings.workspace_root),
                        )
                        
                        if mcp_mgr:
                            logger.info(f"MCP manager obtained for review (stream): {type(mcp_mgr).__name__}")
                            review_diff_data = await get_review_diff(
                                mcp_mgr,
                                Path(payload.workspace_root or settings.workspace_root),
                                review_commit_hash
                            )
                            if review_diff_data:
                                if not review_diff_data.get("has_changes", False):
                                    # No changes to review - set a clear message that will be returned
                                    base_messages[-1]["content"] = "I checked your repository, but there are no uncommitted changes to review. All files are up to date. If you want to review a specific commit, use `/review commit` or `/review <commit-hash>`."
                                    logger.info(f"Review command (stream): no changes found (commit={review_commit_hash or 'uncommitted'})")
                                    # Mark that we've handled this case so RAG doesn't try to process it
                                    review_diff_data = None
                                else:
                                    changed_files = review_diff_data.get('changed_files', [])
                                    diff_length = len(review_diff_data.get('diff', ''))
                                    logger.info(f"Review diff retrieved successfully (stream): {len(changed_files)} files changed, diff_length={diff_length} chars, commit={review_commit_hash or 'uncommitted'}")
                                    # Update message to indicate we're ready for review
                                    base_messages[-1]["content"] = "Please review the following code changes."
                            else:
                                logger.warning(f"Failed to retrieve review diff (stream): review_diff_data is None (commit={review_commit_hash or 'uncommitted'})")
                                # Set helpful error message but keep it as a review request
                                base_messages[-1]["content"] = "I couldn't retrieve the git diff for review. Please make sure you're in a git repository and have uncommitted changes, or specify a commit hash like `/review commit` or `/review HEAD~1`."
                        else:
                            logger.warning("MCP manager is None (stream) - cannot retrieve git diff")
                    except Exception as e:
                        logger.error(f"Failed to get review diff (stream): {e}", exc_info=True)
                        # Continue - will handle error in review flow
                
                # Check for /help command
                elif user_query.strip().lower().startswith("/help"):
                    is_help_command = True
                    original_query = user_query
                    user_query = extract_help_query(user_query)
                    logger.info(f"/help command detected (stream): '{original_query}' -> '{user_query}'")
                    # Update the user message with extracted query for RAG search
                    base_messages[-1]["content"] = user_query
                    is_project_related = True
                    # For /help, we want to search in RAG with the extracted question
                    # The query will be used for RAG retrieval below
                else:
                    # Check if question is about the project
                    is_project_related = is_project_question(user_query)
                
                # Always set system prompt for /review and /help commands, even if not project-related
                # If project-related, get git context and set system prompt
                if is_review_command or is_help_command or is_project_related:
                    # Get MCP manager for git context (always try builtin manager for git server)
                    try:
                        # Always try to get builtin MCP manager (includes git server)
                        mcp_mgr = await ensure_mcp_manager(
                            mcp_config_path=(
                                payload.mcp_config_path or settings.mcp_config_path or None
                            ),
                            workspace_root=Path(payload.workspace_root or settings.workspace_root),
                        )
                        
                        if mcp_mgr:
                            git_context = await get_git_context(mcp_mgr, Path(payload.workspace_root or settings.workspace_root))
                            if git_context:
                                git_context_str = format_git_context(git_context)
                                logger.debug(f"Git context retrieved (stream): branch={git_context.get('branch')}")
                    except Exception as e:
                        logger.warning(f"Failed to get git context for developer assistant (stream): {e}", exc_info=True)
                        # Continue without git context - not critical
                    
                    # Set developer assistant system prompt
                    if is_review_command:
                        logger.info("Setting Staff Engineer system prompt for /review command (stream)")
                        # Staff engineer system prompt for code review
                        dev_assistant_system_prompt = (
                            "Ты Staff Engineer, проводящий code review. "
                            "Твоя задача - найти РЕАЛЬНЫЕ проблемы в коде и указать КОНКРЕТНЫЕ места с примерами из diff.\n\n"
                            "ВАЖНЫЕ ПРАВИЛА:\n"
                            "1. Указывай ТОЛЬКО те категории, где есть РЕАЛЬНЫЕ проблемы\n"
                            "2. Для каждой проблемы указывай:\n"
                            "   - Точное место в коде (файл, строка, функция)\n"
                            "   - Фрагмент кода из diff с проблемой\n"
                            "   - Конкретное объяснение проблемы\n"
                            "   - Предложение исправления с примером кода\n"
                            "3. Если по категории нет проблем - НЕ упоминай её вообще\n"
                            "4. Используй формат diff для показа проблемных мест\n\n"
                            "КАТЕГОРИИ ДЛЯ ПРОВЕРКИ (указывай только если есть проблемы):\n\n"
                            "АРХИТЕКТУРА:\n"
                            "- Нарушение паттернов проекта\n"
                            "- Неправильная структура модулей\n"
                            "- Нарушение SOLID/DRY/KISS\n"
                            "- Проблемы интеграции\n\n"
                            "СТИЛЬ КОДА:\n"
                            "- Несоответствие конвенциям\n"
                            "- Плохое именование\n"
                            "- Отсутствие/неправильные комментарии\n\n"
                            "БАГИ:\n"
                            "- Отсутствие обработки ошибок\n"
                            "- Edge cases не обработаны\n"
                            "- Race conditions\n"
                            "- Null/undefined проблемы\n\n"
                            "ПРОИЗВОДИТЕЛЬНОСТЬ:\n"
                            "- Неэффективные алгоритмы\n"
                            "- N+1 queries\n"
                            "- Лишние операции\n\n"
                            "БЕЗОПАСНОСТЬ:\n"
                            "- SQL injection, XSS риски\n"
                            "- Отсутствие валидации\n"
                            "- Секреты в коде\n\n"
                            "ФОРМАТ ОТВЕТА:\n"
                            "Для каждой проблемы используй такой формат:\n"
                            "```\n"
                            "📁 файл.py:123\n"
                            "```diff\n"
                            "- старый_код\n"
                            "+ новый_код\n"
                            "```\n"
                            "❌ Проблема: [описание]\n"
                            "✅ Исправление: [предложение]\n\n"
                            "Используй предоставленный контекст из RAG для проверки соответствия "
                            "архитектуре и стилю проекта. Цитируй источники как [doc_name:doc_id:chunk_index]. "
                            "Если проблем нет - скажи кратко, что код выглядит хорошо."
                        )
                    elif is_help_command:
                        # Enhanced prompt for /help command - focus on code search
                        dev_assistant_system_prompt = (
                            "Ты ассистент разработчика для этого проекта. "
                            "Пользователь задал вопрос через команду /help. "
                            "Используй предоставленный контекст из RAG для поиска релевантных классов, функций, моделей и кода. "
                            "Найди конкретные файлы, классы, функции и их реализации, которые относятся к вопросу. "
                            "Укажи точные пути к файлам, имена классов и функций. "
                            "Если в контексте есть примеры кода, включи их в ответ. "
                            "Цитируй источники как [doc_name:doc_id:chunk_index]. "
                            "Если нужно больше информации, можешь использовать MCP инструменты для чтения файлов."
                        )
                    else:
                        # Standard prompt for automatic project detection
                        dev_assistant_system_prompt = (
                            "Ты ассистент разработчика для этого проекта. "
                            "Используй предоставленную документацию и Git контекст для ответов. "
                            "Отвечай на основе документации проекта. "
                            "Если информации нет в документации, используй Git контекст (ветка, измененные файлы). "
                            "Цитируй источники как [doc_name:doc_id:chunk_index]. "
                            "Если вопрос касается кода, можешь использовать MCP инструменты для чтения файлов."
                        )
                    
                    # Inject system prompt if not already present
                    system_messages = [m for m in base_messages if m.get("role") == "system"]
                    if not system_messages:
                        base_messages.insert(0, {"role": "system", "content": dev_assistant_system_prompt})
                        logger.info(f"System prompt injected (stream) for {'/review' if is_review_command else '/help' if is_help_command else 'project question'}")
                    else:
                        # Replace existing system message for commands to ensure they take precedence
                        if is_review_command or is_help_command:
                            base_messages[0]["content"] = dev_assistant_system_prompt
                            logger.info(f"System prompt replaced (stream) for {'/review' if is_review_command else '/help'}")
                        else:
                            # Append to existing system message for project questions
                            existing_system = system_messages[0].get("content", "")
                            base_messages[0]["content"] = f"{existing_system}\n\n{dev_assistant_system_prompt}"
    
    # RAG retrieval (if enabled)
    if settings.rag_enabled:
        # Special handling for /review command
        if is_review_command and review_diff_data and review_diff_data.get("has_changes", False):
            # Build RAG queries from diff and changed files
            changed_files = review_diff_data.get("changed_files", [])
            diff = review_diff_data.get("diff", "")
            rag_queries = build_review_rag_queries(changed_files, diff)
            
            # Retrieve chunks for each query and merge
            all_chunks = []
            seen_chunk_ids = set()
            
            for rag_query in rag_queries:
                # Use higher top_k for review (15-20 chunks per query)
                review_top_k = max(15, settings.rag_top_k * 3)
                logger.debug(f"Review RAG query (stream): '{rag_query[:50]}...' top_k={review_top_k}")
                
                query_chunks = await retrieve_chunks(
                    query=rag_query,
                    top_k=review_top_k,
                    base_url=settings.chunkenizer_api_url,
                )
                
                # Deduplicate chunks by document_id + chunk_index
                for chunk in query_chunks:
                    chunk_id = f"{chunk.get('document_id', '')}:{chunk.get('chunk_index', 0)}"
                    if chunk_id not in seen_chunk_ids:
                        seen_chunk_ids.add(chunk_id)
                        all_chunks.append(chunk)
            
            logger.info(f"Review RAG (stream): retrieved {len(all_chunks)} unique chunks from {len(rag_queries)} queries")
            
            # Build review context with diff + RAG chunks (even if no RAG chunks, we still have the diff)
            review_context = build_review_context(
                diff=diff,
                changed_files=changed_files,
                rag_chunks=all_chunks if all_chunks else [],
                git_context=git_context,
                commit_hash=review_commit_hash,
                max_chars=settings.rag_max_context_chars * 2,  # More space for review
            )
            
            if review_context:
                # Update user message with review request
                base_messages[-1]["content"] = "Please review the following code changes:\n\n" + review_context
                logger.info(f"Review context built and injected into messages (stream) (diff_len={len(diff)}, rag_chunks={len(all_chunks)})")
            else:
                logger.warning("Review context is empty (stream) - this should not happen if diff exists")
                # Fallback: at least include the diff
                if diff:
                    base_messages[-1]["content"] = "Please review the following code changes:\n\nCODE DIFF:\n\n" + diff
                    logger.info("Using diff-only fallback for review (stream)")
        elif is_review_command:
            # review_diff_data is None or has_changes is False
            # This case should have been handled earlier - message content already set to error/info
            # Don't run standard RAG on the error message
            logger.info(f"Review command completed (stream, no diff to process): review_diff_data={review_diff_data is not None}, message_content_len={len(base_messages[-1].get('content', '')) if base_messages else 0}")
        else:
            # Standard RAG retrieval for /help and other queries
            user_messages = [m for m in base_messages if m.get("role") == "user"]
            if user_messages:
                query = user_messages[-1].get("content", "")
                if query and query.strip():
                    # For /help commands, use higher top_k to get more relevant results
                    top_k = settings.rag_top_k * 2 if is_help_command else settings.rag_top_k
                    logger.info(
                        "RAG retrieval starting (stream) query_len=%d top_k=%d help_mode=%s",
                        len(query),
                        top_k,
                        is_help_command,
                    )
                    chunks = await retrieve_chunks(
                        query=query,
                        top_k=top_k,
                        base_url=settings.chunkenizer_api_url,
                    )
                    if chunks:
                        # Store baseline chunks for comparison mode
                        baseline_chunks = chunks.copy() if settings.rag_compare_mode else None
                        
                        # Second-stage filtering by similarity threshold
                        filtered_chunks, filter_metadata = filter_by_similarity(
                            chunks,
                            threshold=settings.rag_min_similarity,
                            min_chunks=settings.rag_min_chunks,
                        )
                        
                        # Reranking (if enabled)
                        if settings.rag_reranker_enabled:
                            reranker = get_reranker(settings.rag_reranker_type)
                            filtered_chunks = await reranker.rerank(query, filtered_chunks)
                            logger.debug(
                                "RAG reranker applied (stream) type=%s chunks=%d",
                                settings.rag_reranker_type,
                                len(filtered_chunks),
                            )
                        
                        # Build context from filtered/reranked chunks
                        context = build_context_block(filtered_chunks, settings.rag_max_context_chars)
                        if context:
                            # Add git context if available (for developer assistant mode)
                            if git_context_str:
                                context = f"{git_context_str}\n\n{context}"
                            base_messages = inject_rag_context(base_messages, context)
                            logger.info(
                                "RAG context injected (stream) initial_k=%d filtered_k=%d final_k=%d "
                                "threshold=%.3f fallback=%s reranker=%s context_size=%d",
                                len(chunks),
                                filter_metadata["filtered_count"],
                                len(filtered_chunks),
                                settings.rag_min_similarity,
                                filter_metadata["fallback_triggered"],
                                settings.rag_reranker_type if settings.rag_reranker_enabled else "none",
                                len(context),
                            )
                        else:
                            logger.debug("RAG context block empty after formatting (stream)")
                    else:
                        logger.debug("RAG retrieval returned no chunks (stream)")
                else:
                    logger.debug("RAG skipped: empty user query (stream)")
            else:
                logger.debug("RAG skipped: no user messages found (stream)")
    else:
        logger.debug("RAG disabled (stream)")
    
    base_input = _messages_to_responses_input(base_messages)
    mcp_enabled = bool(payload.mcp_enabled) if payload.mcp_enabled is not None else bool(
        payload.mcp_config_path or settings.mcp_config_path
    )
    mgr = await ensure_mcp_manager(
        mcp_config_path=(
            (payload.mcp_config_path or settings.mcp_config_path or None) if mcp_enabled else None
        ),
        workspace_root=Path(payload.workspace_root or settings.workspace_root),
    )
    tools = mgr.openai_tools() if mgr is not None else []
    resp_tools = _tools_to_responses_api(tools) if tools else []

    # Streaming mode uses the Responses API event stream and currently does not
    # support the server-side tool loop used by the old chat.completions stream.
    # We keep max_rounds for parity but will exit after one stream.
    max_rounds = 8

    async with httpx.AsyncClient(timeout=None) as client:
        for _ in range(max_rounds):
            body: Dict[str, Any] = {
                "model": payload.model or settings.openai_model,
                "input": base_input,
                "stream": True,
            }
            # NOTE: We intentionally do NOT send `stream_options`.
            # Many OpenAI-compatible backends (and some proxies/gateways) reject
            # unknown fields with HTTP 400.
            if resp_tools:
                body["tools"] = resp_tools
                body["tool_choice"] = "auto"
            if payload.temperature is not None:
                body["temperature"] = payload.temperature
            if payload.max_tokens is not None:
                body["max_tokens"] = payload.max_tokens

            finish_reason: Optional[str] = None

            base = str(settings.openai_api_base).rstrip("/")
            path = str(getattr(settings, "openai_chat_path", "chat/responses")).lstrip("/")
            url = f"{base}/{path}"
            logger.debug(
                "stream_chatgpt upstream request url=%s model=%s input_items=%d tools=%d temperature=%s max_tokens=%s",
                url,
                body.get("model"),
                len(base_input),
                len(resp_tools) if resp_tools else 0,
                body.get("temperature"),
                body.get("max_tokens"),
            )
            async with client.stream(
                "POST",
                url,
                json=body,
                headers=headers,
            ) as response:
                # IMPORTANT: For streaming requests, httpx raises on status *before* the body is read.
                # Many upstreams return a useful JSON error body (e.g. invalid model/param),
                # so we must consume it first to make it available in the HTTPStatusError handler.
                if response.status_code >= 400:
                    await response.aread()
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if not line.startswith("data:"):
                        continue

                    data = line[len("data:") :].strip()
                    if data == "[DONE]":
                        break

                    event = json.loads(data)

                    # Responses API emits different event shapes; we normalize deltas
                    # into Chat Completions-like chunks for the rest of the app.
                    # Common delta event:
                    #   {"type":"response.output_text.delta","delta":"..."}
                    if isinstance(event, dict):
                        et = event.get("type")
                        if et == "response.created":
                            resp = event.get("response") or {}
                            if isinstance(resp, dict):
                                yield {"id": resp.get("id"), "model": resp.get("model")}
                            continue
                        if et == "response.output_text.delta" and isinstance(event.get("delta"), str):
                            delta_text = event["delta"]
                            yield {"choices": [{"delta": {"content": delta_text}}]}
                            continue
                        if et == "response.completed":
                            # If usage is present on completed, pass it through for token stats.
                            resp = event.get("response") or {}
                            if isinstance(resp, dict):
                                usage_obj = _responses_usage_to_chat_usage(resp)
                                if usage_obj:
                                    yield {"usage": usage_obj}
                            finish_reason = "stop"
                            continue

            if finish_reason != "tool_calls":
                return
            raise RuntimeError("Tool calls are not supported in streaming mode for /v1/responses yet")
