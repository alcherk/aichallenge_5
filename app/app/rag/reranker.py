"""Reranker interface and implementations for RAG chunks."""
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any

logger = logging.getLogger("app.rag.reranker")


class Reranker(ABC):
    """Abstract base class for chunk rerankers."""
    
    @abstractmethod
    async def rerank(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Rerank chunks by relevance to query.
        
        Args:
            query: Search query text
            chunks: List of chunk dicts to rerank
        
        Returns:
            Reordered chunks (may include new rerank_score field)
        """
        pass


class NoOpReranker(Reranker):
    """Default reranker: no reranking, preserves original order."""
    
    async def rerank(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Passthrough: return chunks unchanged.
        
        This preserves the original order from vector search.
        """
        logger.debug("NoOpReranker: preserving original order chunks=%d", len(chunks))
        return chunks


def get_reranker(reranker_type: str = "noop") -> Reranker:
    """
    Factory function to get reranker instance.
    
    Args:
        reranker_type: Type of reranker ("noop", "cross_encoder", "llm", etc.)
    
    Returns:
        Reranker instance
    """
    if reranker_type == "noop":
        return NoOpReranker()
    else:
        logger.warning(
            "Unknown reranker type '%s', falling back to NoOpReranker",
            reranker_type,
        )
        return NoOpReranker()

