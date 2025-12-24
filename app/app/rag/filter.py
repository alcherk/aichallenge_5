"""Similarity-based filtering for RAG chunks."""
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger("app.rag.filter")


def filter_by_similarity(
    chunks: List[Dict[str, Any]],
    threshold: float,
    min_chunks: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Filter chunks by similarity score threshold.
    
    Args:
        chunks: List of chunk dicts with 'score' field
        threshold: Minimum similarity score (0.0-1.0 for cosine)
        min_chunks: Minimum chunks to keep (fallback if filtering removes too many)
    
    Returns:
        Tuple of (filtered_chunks, metadata)
        metadata includes: original_count, filtered_count, fallback_triggered, scores_range
    """
    if not chunks:
        return [], {
            "original_count": 0,
            "filtered_count": 0,
            "fallback_triggered": False,
            "scores_range": None,
        }
    
    original_count = len(chunks)
    
    # Extract scores for logging
    scores = [chunk.get("score", 0.0) for chunk in chunks]
    min_score = min(scores) if scores else 0.0
    max_score = max(scores) if scores else 0.0
    
    # Filter chunks by threshold
    filtered_chunks = [chunk for chunk in chunks if chunk.get("score", 0.0) >= threshold]
    filtered_count = len(filtered_chunks)
    
    # Fallback: if filtering removed too many chunks, keep top min_chunks by score
    fallback_triggered = False
    if filtered_count < min_chunks and original_count >= min_chunks:
        # Sort by score (descending) and take top min_chunks
        sorted_chunks = sorted(chunks, key=lambda c: c.get("score", 0.0), reverse=True)
        filtered_chunks = sorted_chunks[:min_chunks]
        filtered_count = len(filtered_chunks)
        fallback_triggered = True
        logger.warning(
            "RAG filter fallback triggered threshold=%.3f filtered=%d min_chunks=%d "
            "using_top_n=%d",
            threshold,
            len([c for c in chunks if c.get("score", 0.0) >= threshold]),
            min_chunks,
            filtered_count,
        )
    
    metadata = {
        "original_count": original_count,
        "filtered_count": filtered_count,
        "fallback_triggered": fallback_triggered,
        "scores_range": (min_score, max_score) if scores else None,
        "threshold": threshold,
    }
    
    logger.info(
        "RAG filter applied threshold=%.3f original=%d filtered=%d fallback=%s "
        "scores_range=[%.3f,%.3f]",
        threshold,
        original_count,
        filtered_count,
        fallback_triggered,
        min_score,
        max_score,
    )
    
    return filtered_chunks, metadata

