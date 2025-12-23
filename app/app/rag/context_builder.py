"""Build context blocks from retrieved chunks with citations."""
from typing import List, Dict, Any


def build_context_block(chunks: List[Dict[str, Any]], max_chars: int = 8000) -> str:
    """
    Build formatted context block with citations.
    
    Format:
    CONTEXT:
    
    [chunk_text] [doc_name:doc_id:chunk_index]
    
    [chunk_text] [doc_name:doc_id:chunk_index]
    ...
    
    Args:
        chunks: List of chunk dicts with keys: chunk_text, document_id, document_name, chunk_index
        max_chars: Maximum total characters (truncates if exceeded)
    
    Returns:
        Formatted context string
    """
    if not chunks:
        return ""
    
    # Format each chunk with citation
    formatted_chunks = []
    total_chars = len("CONTEXT:\n\n")
    
    for chunk in chunks:
        chunk_text = chunk.get("chunk_text", "").strip()
        doc_id = chunk.get("document_id", "")
        doc_name = chunk.get("document_name", "")
        chunk_index = chunk.get("chunk_index", 0)
        
        if not chunk_text:
            continue
        
        # Format: [chunk_text] [doc_name:doc_id:chunk_index]
        # If document_name is not available, fall back to just doc_id:chunk_index
        if doc_name:
            citation = f"[{doc_name}:{doc_id}:{chunk_index}]"
        else:
            citation = f"[{doc_id}:{chunk_index}]"
        chunk_line = f"{chunk_text} {citation}"
        
        # Check if adding this chunk would exceed limit
        chunk_size = len(chunk_line) + 2  # +2 for newlines
        if total_chars + chunk_size > max_chars:
            # Truncate this chunk if needed
            remaining = max_chars - total_chars - len(citation) - 3  # -3 for " " and newlines
            if remaining > 20:  # Only truncate if we have meaningful space
                truncated_text = chunk_text[:remaining] + "..."
                chunk_line = f"{truncated_text} {citation}"
                formatted_chunks.append(chunk_line)
            # Stop adding chunks if we're at the limit
            break
        
        formatted_chunks.append(chunk_line)
        total_chars += chunk_size
    
    if not formatted_chunks:
        return ""
    
    # Combine into context block
    context = "CONTEXT:\n\n" + "\n\n".join(formatted_chunks)
    
    return context

