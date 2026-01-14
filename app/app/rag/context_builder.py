"""Build context blocks from retrieved chunks with citations."""
from typing import List, Dict, Any, Optional


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
    
    def _best_doc_name(chunk: Dict[str, Any]) -> str:
        """
        Prefer an explicit document_name; otherwise try to derive something human-friendly
        from metadata so citations don't end up as placeholders.
        """
        doc_name = (chunk.get("document_name") or "").strip()
        if doc_name:
            return doc_name
        metadata = chunk.get("metadata") or {}
        if isinstance(metadata, dict):
            for key in ("document_name", "source", "filename", "file_name", "path", "file_path"):
                v = metadata.get(key)
                if isinstance(v, str) and v.strip():
                    # If it's a path, keep only basename for cleaner citations.
                    return v.strip().split("/")[-1]
        return "unknown"

    for chunk in chunks:
        chunk_text = chunk.get("chunk_text", "").strip()
        doc_id = chunk.get("document_id", "")
        doc_name = _best_doc_name(chunk)
        chunk_index = chunk.get("chunk_index", 0)
        
        if not chunk_text:
            continue
        
        # Always emit a 3-part citation so the model can copy it verbatim.
        citation = f"[{doc_name}:{doc_id}:{chunk_index}]"
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


def build_review_context(
    diff: str,
    changed_files: List[str],
    rag_chunks: List[Dict[str, Any]],
    git_context: Optional[Dict[str, Any]] = None,
    commit_hash: Optional[str] = None,
    max_chars: int = 16000
) -> str:
    """
    Build context block for code review.
    
    Format:
    - Git context (branch, commit info if applicable)
    - Changed files list
    - Full diff
    - RAG chunks (architecture guides, codestyle, related code)
    - Citations for all sources
    
    Args:
        diff: Git diff content
        changed_files: List of changed file paths
        rag_chunks: List of RAG chunks with architecture/codestyle info
        git_context: Optional git context dict (branch, etc.)
        commit_hash: Optional commit hash being reviewed
        max_chars: Maximum total characters (truncates if exceeded)
    
    Returns:
        Formatted review context string
    """
    parts = []
    total_chars = 0
    
    # 1. Git context section
    if git_context:
        git_lines = ["GIT CONTEXT:"]
        branch = git_context.get("branch")
        if branch:
            git_lines.append(f"Branch: {branch}")
        if commit_hash:
            git_lines.append(f"Reviewing commit: {commit_hash}")
        else:
            git_lines.append("Reviewing: Uncommitted changes")
        git_section = "\n".join(git_lines)
        parts.append(git_section)
        total_chars += len(git_section) + 2  # +2 for newlines
    
    # 2. Changed files section
    if changed_files:
        files_section = f"CHANGED FILES ({len(changed_files)}):\n" + "\n".join(f"  - {f}" for f in changed_files)
        parts.append(files_section)
        total_chars += len(files_section) + 2
    
    # 3. Diff section
    if diff:
        # Truncate diff if needed to leave room for RAG chunks
        remaining_for_rag = max(2000, max_chars - total_chars - 2000)  # Reserve at least 2000 for RAG
        remaining_for_diff = max_chars - remaining_for_rag - total_chars
        
        if len(diff) > remaining_for_diff:
            truncated_diff = diff[:remaining_for_diff] + f"\n\n[... diff truncated, {len(diff) - remaining_for_diff} chars remaining ...]"
            diff_section = f"CODE DIFF:\n\n{truncated_diff}"
        else:
            diff_section = f"CODE DIFF:\n\n{diff}"
        
        parts.append(diff_section)
        total_chars += len(diff_section) + 2
    
    # 4. RAG chunks section (architecture, codestyle, related code)
    if rag_chunks:
        # Format RAG chunks with citations
        formatted_rag = []
        rag_chars = 0
        remaining = max_chars - total_chars - len("REFERENCE DOCUMENTATION:\n\n")
        
        for chunk in rag_chunks:
            chunk_text = chunk.get("chunk_text", "").strip()
            doc_id = chunk.get("document_id", "")
            doc_name = chunk.get("document_name", "")
            chunk_index = chunk.get("chunk_index", 0)
            
            if not chunk_text:
                continue
            
            # Format citation
            if doc_name:
                citation = f"[{doc_name}:{doc_id}:{chunk_index}]"
            else:
                citation = f"[{doc_id}:{chunk_index}]"
            
            chunk_line = f"{chunk_text} {citation}"
            chunk_size = len(chunk_line) + 2  # +2 for newlines
            
            if rag_chars + chunk_size > remaining:
                # Truncate this chunk if needed
                remaining_for_chunk = remaining - rag_chars - len(citation) - 3
                if remaining_for_chunk > 20:
                    truncated_text = chunk_text[:remaining_for_chunk] + "..."
                    chunk_line = f"{truncated_text} {citation}"
                    formatted_rag.append(chunk_line)
                break
            
            formatted_rag.append(chunk_line)
            rag_chars += chunk_size
        
        if formatted_rag:
            rag_section = "REFERENCE DOCUMENTATION:\n\n" + "\n\n".join(formatted_rag)
            parts.append(rag_section)
            total_chars += len(rag_section) + 2
    
    # Combine all parts
    if not parts:
        return ""
    
    return "\n\n".join(parts)

