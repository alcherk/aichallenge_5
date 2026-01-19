"""
Persistent response cache using SQLite.

Provides caching for LLM responses to avoid repeated API calls for identical queries.
Cache persists across restarts using SQLite storage.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import aiosqlite

logger = logging.getLogger("app.cache")


@dataclass
class CachedResponse:
    """Cached response data structure."""

    content: str
    model: str
    provider: str
    created_at: float
    metadata: dict


@dataclass
class CacheStats:
    """Cache statistics."""

    hits: int
    misses: int
    size: int  # Total size in bytes (approximate)
    entries: int


class ResponseCache:
    """
    Persistent response cache using SQLite.

    Stores LLM responses keyed by a deterministic hash of the request parameters.
    Tracks hit/miss statistics for monitoring cache effectiveness.
    """

    def __init__(self, db_path: str = "cache/responses.db"):
        """
        Initialize the response cache.

        Args:
            db_path: Path to the SQLite database file. Parent directories
                    will be created automatically.
        """
        self.db_path = Path(db_path)
        self._initialized = False

    async def _init_db(self) -> None:
        """
        Initialize database schema.

        Creates the necessary tables if they don't exist. This method is
        idempotent and safe to call multiple times.
        """
        if self._initialized:
            return

        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(str(self.db_path)) as db:
            # Create responses table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS responses (
                    cache_key TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    model TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    metadata TEXT
                )
            ''')

            # Create stats table (single row)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS stats (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    hits INTEGER DEFAULT 0,
                    misses INTEGER DEFAULT 0
                )
            ''')

            # Initialize stats row if not exists
            await db.execute(
                'INSERT OR IGNORE INTO stats (id, hits, misses) VALUES (1, 0, 0)'
            )

            # Create index for faster lookups
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_responses_created_at
                ON responses (created_at)
            ''')

            await db.commit()

        self._initialized = True
        logger.info("Cache database initialized at %s", self.db_path)

    def cache_key(self, model: str, messages: list[dict], params: dict) -> str:
        """
        Generate deterministic cache key from request parameters.

        Args:
            model: Model name
            messages: List of message dicts with 'role' and 'content'
            params: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            SHA-256 hash string as cache key
        """
        # Normalize messages to ensure consistent hashing
        normalized_messages = [
            {"role": m.get("role", ""), "content": m.get("content", "")}
            for m in messages
        ]

        data = json.dumps(
            {"model": model, "messages": normalized_messages, **params},
            sort_keys=True,
            ensure_ascii=True,
        )
        return hashlib.sha256(data.encode()).hexdigest()

    async def get(self, key: str) -> CachedResponse | None:
        """
        Get cached response by key.

        Updates hit/miss statistics automatically.

        Args:
            key: Cache key (from cache_key() method)

        Returns:
            CachedResponse if found, None otherwise
        """
        await self._init_db()

        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute(
                '''
                SELECT content, model, provider, created_at, metadata
                FROM responses WHERE cache_key = ?
                ''',
                (key,),
            )
            row = await cursor.fetchone()

            if row is None:
                # Cache miss - increment miss counter
                await db.execute('UPDATE stats SET misses = misses + 1 WHERE id = 1')
                await db.commit()
                logger.debug("Cache miss for key: %s", key[:16])
                return None

            # Cache hit - increment hit counter
            await db.execute('UPDATE stats SET hits = hits + 1 WHERE id = 1')
            await db.commit()

            # Parse metadata JSON
            metadata = {}
            if row["metadata"]:
                try:
                    metadata = json.loads(row["metadata"])
                except json.JSONDecodeError:
                    logger.warning("Invalid metadata JSON for key: %s", key[:16])

            logger.debug("Cache hit for key: %s", key[:16])

            return CachedResponse(
                content=row["content"],
                model=row["model"],
                provider=row["provider"],
                created_at=row["created_at"],
                metadata=metadata,
            )

    async def set(
        self,
        key: str,
        response: str,
        model: str,
        provider: str,
        metadata: dict | None = None,
    ) -> None:
        """
        Store response in cache.

        Args:
            key: Cache key (from cache_key() method)
            response: Response content to cache
            model: Model name used to generate the response
            provider: Provider name ("cloud" or "local")
            metadata: Optional metadata dict to store with the response
        """
        await self._init_db()

        metadata_json = json.dumps(metadata or {}, ensure_ascii=True)
        created_at = time.time()

        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute(
                '''
                INSERT OR REPLACE INTO responses
                (cache_key, content, model, provider, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (key, response, model, provider, created_at, metadata_json),
            )
            await db.commit()

        logger.debug("Cached response for key: %s (model=%s)", key[:16], model)

    async def clear(self) -> None:
        """
        Clear all cached responses.

        Resets the responses table and statistics counters.
        """
        await self._init_db()

        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute('DELETE FROM responses')
            await db.execute('UPDATE stats SET hits = 0, misses = 0 WHERE id = 1')
            await db.commit()

        logger.info("Cache cleared")

    async def get_stats(self) -> CacheStats:
        """
        Get cache statistics.

        Returns:
            CacheStats with hits, misses, approximate size in bytes,
            and number of entries
        """
        await self._init_db()

        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row

            # Get hit/miss counts
            cursor = await db.execute('SELECT hits, misses FROM stats WHERE id = 1')
            stats_row = await cursor.fetchone()
            hits = stats_row["hits"] if stats_row else 0
            misses = stats_row["misses"] if stats_row else 0

            # Get entry count
            cursor = await db.execute('SELECT COUNT(*) as count FROM responses')
            count_row = await cursor.fetchone()
            entries = count_row["count"] if count_row else 0

            # Estimate size (sum of content lengths + overhead)
            cursor = await db.execute(
                '''
                SELECT COALESCE(SUM(LENGTH(content) + LENGTH(COALESCE(metadata, ''))), 0) as size
                FROM responses
                '''
            )
            size_row = await cursor.fetchone()
            size = size_row["size"] if size_row else 0

        return CacheStats(
            hits=hits,
            misses=misses,
            size=size,
            entries=entries,
        )

    async def delete(self, key: str) -> bool:
        """
        Delete a specific cached response.

        Args:
            key: Cache key to delete

        Returns:
            True if entry was deleted, False if not found
        """
        await self._init_db()

        async with aiosqlite.connect(str(self.db_path)) as db:
            cursor = await db.execute(
                'DELETE FROM responses WHERE cache_key = ?',
                (key,),
            )
            await db.commit()
            deleted = cursor.rowcount > 0

        if deleted:
            logger.debug("Deleted cached response for key: %s", key[:16])

        return deleted

    async def prune_old(self, max_age_seconds: float) -> int:
        """
        Delete cached responses older than specified age.

        Args:
            max_age_seconds: Maximum age in seconds

        Returns:
            Number of entries deleted
        """
        await self._init_db()

        cutoff_time = time.time() - max_age_seconds

        async with aiosqlite.connect(str(self.db_path)) as db:
            cursor = await db.execute(
                'DELETE FROM responses WHERE created_at < ?',
                (cutoff_time,),
            )
            await db.commit()
            deleted_count = cursor.rowcount

        if deleted_count > 0:
            logger.info("Pruned %d old cache entries", deleted_count)

        return deleted_count


# Module-level singleton for convenience
_cache: ResponseCache | None = None


def get_response_cache(db_path: str | None = None) -> ResponseCache:
    """
    Get or create the global ResponseCache instance.

    Args:
        db_path: Optional path to database. Only used when creating
                the first instance.

    Returns:
        Singleton ResponseCache instance
    """
    global _cache
    if _cache is None:
        _cache = ResponseCache(db_path=db_path or "cache/responses.db")
    return _cache
