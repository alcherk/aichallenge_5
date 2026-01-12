"""Inject RAG context into chat messages."""
from typing import List, Dict, Any


def inject_rag_context(messages: List[Dict[str, Any]], context: str) -> List[Dict[str, Any]]:
    """
    Inject RAG context into messages.
    
    Strategy:
    - Find the last user message
    - Prepend context block and instruction to that message
    - Preserve all other messages
    
    Args:
        messages: List of message dicts with 'role' and 'content' keys
        context: Formatted context block from build_context_block()
    
    Returns:
        Modified messages list with context injected
    """
    if not context or not context.strip():
        return messages
    
    # Create a copy to avoid modifying the original
    modified_messages = [msg.copy() for msg in messages]
    
    # Find the last user message
    last_user_idx = None
    for i in range(len(modified_messages) - 1, -1, -1):
        if modified_messages[i].get("role") == "user":
            last_user_idx = i
            break
    
    if last_user_idx is None:
        # No user message found, add context as a new user message
        instruction = (
            "Answer ONLY using the provided context. If the information is not present in the context, "
            "say you don't know. Cite sources as [doc_name:doc_id:chunk_index].\n\n"
        )
        modified_messages.append({
            "role": "user",
            "content": instruction + context,
        })
        return modified_messages
    
    # Prepend context and instruction to the last user message
    original_content = modified_messages[last_user_idx].get("content", "")
    
    # Check if this is a /help command (question starts with specific patterns)
    is_help_query = (
        original_content.lower().strip().startswith("tell me about") or
        "how" in original_content.lower() or
        "what" in original_content.lower() or
        "where" in original_content.lower() or
        "implement" in original_content.lower() or
        "class" in original_content.lower() or
        "function" in original_content.lower()
    )
    
    if is_help_query:
        instruction = (
            "Используй предоставленный контекст для поиска релевантной информации. "
            "Найди конкретные классы, функции, модели, файлы и их реализации. "
            "Укажи точные пути к файлам и имена классов/функций. "
            "Если в контексте есть примеры кода, включи их. "
            "Цитируй источники как [doc_name:doc_id:chunk_index].\n\n"
        )
    else:
        instruction = (
            "Answer ONLY using the provided context. If the information is not present in the context, "
            "say you don't know. Cite sources as [doc_name:doc_id:chunk_index].\n\n"
        )
    
    # Format: instruction + context + original question
    new_content = f"{instruction}{context}\n\nQuestion: {original_content}"
    modified_messages[last_user_idx]["content"] = new_content
    
    return modified_messages

