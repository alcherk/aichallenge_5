"""Adapter for Chunkenizer API."""
import logging
import time
from typing import List, Dict, Any, Optional
import httpx

logger = logging.getLogger("app.rag.chunkenizer")


async def retrieve_chunks(
    query: str,
    top_k: int = 5,
    base_url: str = "http://localhost:8000",
    timeout: float = 10.0,
) -> List[Dict[str, Any]]:
    """
    Retrieve relevant document chunks from Chunkenizer API.
    
    Args:
        query: Search query text
        top_k: Number of top chunks to retrieve
        base_url: Chunkenizer API base URL
        timeout: Request timeout in seconds
    
    Returns:
        List of dicts with keys: chunk_text, document_id, document_name, chunk_index, score, metadata
        Returns empty list on error (with warning log)
    """
    if not query or not query.strip():
        logger.warning("Empty query provided to retrieve_chunks")
        return []
    
    start_time = time.time()
    search_url = f"{base_url.rstrip('/')}/search"
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                search_url,
                json={"query": query, "top_k": top_k, "filters": {}},
            )
            response.raise_for_status()
            data = response.json()
            
            results = data.get("results", [])
            retrieval_time_ms = (time.time() - start_time) * 1000
            
            logger.info(
                "Chunkenizer retrieval completed query_len=%d top_k=%d results=%d time_ms=%.2f",
                len(query),
                top_k,
                len(results),
                retrieval_time_ms,
            )
            
            # Format results to match expected structure
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "chunk_text": result.get("chunk_text", ""),
                    "document_id": result.get("document_id", ""),
                    "document_name": result.get("document_name", ""),
                    "chunk_index": result.get("chunk_index", 0),
                    "score": result.get("score", 0.0),
                    "metadata": result.get("metadata", {}),
                })
            
            return formatted_results
            
    except httpx.TimeoutException:
        logger.warning(
            "Chunkenizer API timeout query_len=%d base_url=%s timeout=%.1f",
            len(query),
            base_url,
            timeout,
        )
        return []
    except httpx.HTTPStatusError as e:
        logger.error(
            "Chunkenizer API error query_len=%d base_url=%s status=%d response=%s",
            len(query),
            base_url,
            e.response.status_code,
            e.response.text[:200] if e.response.text else "",
        )
        return []
    except Exception as e:
        logger.exception(
            "Unexpected error retrieving chunks query_len=%d base_url=%s error=%s",
            len(query),
            base_url,
            str(e),
        )
        return []

