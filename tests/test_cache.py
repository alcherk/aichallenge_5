"""Tests for Response Cache Service."""
import pytest
import pytest_asyncio
import tempfile
import os
from pathlib import Path

from app.app.services.cache import ResponseCache, CachedResponse, CacheStats


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield os.path.join(tmpdir, "cache", "test_responses.db")


@pytest_asyncio.fixture
async def cache(temp_db_path):
    """Create a ResponseCache instance with temporary database."""
    cache = ResponseCache(db_path=temp_db_path)
    await cache._init_db()
    yield cache
    # Cleanup is handled by temp directory fixture


@pytest.mark.asyncio
async def test_cache_init_creates_database(temp_db_path):
    """Test that initialization creates the database file and tables."""
    cache = ResponseCache(db_path=temp_db_path)
    await cache._init_db()

    # Check database file was created
    assert Path(temp_db_path).exists()

    # Check parent directory was created
    assert Path(temp_db_path).parent.exists()


@pytest.mark.asyncio
async def test_cache_init_is_idempotent(cache):
    """Test that _init_db can be called multiple times safely."""
    # First init happens in fixture
    # Call again - should not raise
    await cache._init_db()
    await cache._init_db()

    # Should still work
    stats = await cache.get_stats()
    assert stats.entries == 0


@pytest.mark.asyncio
async def test_cache_key_deterministic():
    """Test that cache_key produces consistent results for same input."""
    cache = ResponseCache()

    model = "gpt-4"
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello"},
    ]
    params = {"temperature": 0.7, "max_tokens": 100}

    key1 = cache.cache_key(model, messages, params)
    key2 = cache.cache_key(model, messages, params)

    assert key1 == key2
    assert len(key1) == 64  # SHA-256 produces 64 hex chars


@pytest.mark.asyncio
async def test_cache_key_different_for_different_input():
    """Test that cache_key produces different results for different input."""
    cache = ResponseCache()

    messages1 = [{"role": "user", "content": "Hello"}]
    messages2 = [{"role": "user", "content": "Hi"}]

    key1 = cache.cache_key("gpt-4", messages1, {})
    key2 = cache.cache_key("gpt-4", messages2, {})

    assert key1 != key2


@pytest.mark.asyncio
async def test_cache_key_different_for_different_model():
    """Test that cache_key differs when model changes."""
    cache = ResponseCache()

    messages = [{"role": "user", "content": "Hello"}]

    key1 = cache.cache_key("gpt-4", messages, {})
    key2 = cache.cache_key("gpt-3.5-turbo", messages, {})

    assert key1 != key2


@pytest.mark.asyncio
async def test_cache_key_different_for_different_params():
    """Test that cache_key differs when params change."""
    cache = ResponseCache()

    messages = [{"role": "user", "content": "Hello"}]

    key1 = cache.cache_key("gpt-4", messages, {"temperature": 0.5})
    key2 = cache.cache_key("gpt-4", messages, {"temperature": 0.7})

    assert key1 != key2


@pytest.mark.asyncio
async def test_cache_set_and_get(cache):
    """Test storing and retrieving a response."""
    key = "test_key_123"
    content = "This is a test response."
    model = "gpt-4"
    provider = "cloud"
    metadata = {"tokens": 10}

    # Store
    await cache.set(key, content, model, provider, metadata)

    # Retrieve
    result = await cache.get(key)

    assert result is not None
    assert isinstance(result, CachedResponse)
    assert result.content == content
    assert result.model == model
    assert result.provider == provider
    assert result.metadata == metadata
    assert result.created_at > 0


@pytest.mark.asyncio
async def test_cache_get_nonexistent_key(cache):
    """Test that getting a nonexistent key returns None."""
    result = await cache.get("nonexistent_key")
    assert result is None


@pytest.mark.asyncio
async def test_cache_hit_miss_stats(cache):
    """Test that hit/miss statistics are tracked correctly."""
    # Initial stats
    stats = await cache.get_stats()
    assert stats.hits == 0
    assert stats.misses == 0

    # Cache miss
    await cache.get("nonexistent_key")
    stats = await cache.get_stats()
    assert stats.misses == 1
    assert stats.hits == 0

    # Store a value
    await cache.set("key1", "value1", "gpt-4", "cloud", {})

    # Cache hit
    await cache.get("key1")
    stats = await cache.get_stats()
    assert stats.hits == 1
    assert stats.misses == 1

    # Another hit
    await cache.get("key1")
    stats = await cache.get_stats()
    assert stats.hits == 2
    assert stats.misses == 1


@pytest.mark.asyncio
async def test_cache_stats_entries_count(cache):
    """Test that entry count is tracked correctly."""
    stats = await cache.get_stats()
    assert stats.entries == 0

    await cache.set("key1", "value1", "gpt-4", "cloud", {})
    stats = await cache.get_stats()
    assert stats.entries == 1

    await cache.set("key2", "value2", "gpt-4", "cloud", {})
    stats = await cache.get_stats()
    assert stats.entries == 2


@pytest.mark.asyncio
async def test_cache_stats_size_tracking(cache):
    """Test that size is estimated correctly."""
    stats = await cache.get_stats()
    assert stats.size == 0

    content = "A" * 1000
    await cache.set("key1", content, "gpt-4", "cloud", {"test": "data"})

    stats = await cache.get_stats()
    # Size should include content length + metadata length
    assert stats.size >= 1000


@pytest.mark.asyncio
async def test_cache_clear(cache):
    """Test clearing all cached entries."""
    # Add some entries
    await cache.set("key1", "value1", "gpt-4", "cloud", {})
    await cache.set("key2", "value2", "gpt-4", "cloud", {})

    # Generate some stats
    await cache.get("key1")  # hit
    await cache.get("nonexistent")  # miss

    stats = await cache.get_stats()
    assert stats.entries == 2
    assert stats.hits == 1
    assert stats.misses == 1

    # Clear
    await cache.clear()

    # Check everything is reset
    stats = await cache.get_stats()
    assert stats.entries == 0
    assert stats.hits == 0
    assert stats.misses == 0

    # Previous entries should be gone
    assert await cache.get("key1") is None


@pytest.mark.asyncio
async def test_cache_set_overwrites_existing(cache):
    """Test that setting a key that exists updates the value."""
    key = "test_key"

    await cache.set(key, "original", "gpt-3", "cloud", {"v": 1})
    result = await cache.get(key)
    assert result.content == "original"
    assert result.model == "gpt-3"

    await cache.set(key, "updated", "gpt-4", "local", {"v": 2})
    result = await cache.get(key)
    assert result.content == "updated"
    assert result.model == "gpt-4"
    assert result.provider == "local"
    assert result.metadata == {"v": 2}

    # Entry count should still be 1
    stats = await cache.get_stats()
    assert stats.entries == 1


@pytest.mark.asyncio
async def test_cache_delete(cache):
    """Test deleting a specific entry."""
    await cache.set("key1", "value1", "gpt-4", "cloud", {})
    await cache.set("key2", "value2", "gpt-4", "cloud", {})

    stats = await cache.get_stats()
    assert stats.entries == 2

    # Delete one
    deleted = await cache.delete("key1")
    assert deleted is True

    # Check it's gone
    assert await cache.get("key1") is None

    # Other entry still exists
    result = await cache.get("key2")
    assert result is not None

    stats = await cache.get_stats()
    assert stats.entries == 1


@pytest.mark.asyncio
async def test_cache_delete_nonexistent(cache):
    """Test deleting a nonexistent key returns False."""
    deleted = await cache.delete("nonexistent")
    assert deleted is False


@pytest.mark.asyncio
async def test_cache_prune_old(cache):
    """Test pruning old entries."""
    import time

    # Add entries
    await cache.set("key1", "value1", "gpt-4", "cloud", {})
    await cache.set("key2", "value2", "gpt-4", "cloud", {})

    # Prune entries older than 0 seconds (should delete all)
    time.sleep(0.1)  # Small delay to ensure entries are "old"
    deleted = await cache.prune_old(max_age_seconds=0.01)

    assert deleted == 2

    stats = await cache.get_stats()
    assert stats.entries == 0


@pytest.mark.asyncio
async def test_cache_persists_across_instances(temp_db_path):
    """Test that cache persists when creating new instance."""
    # Create first instance and add data
    cache1 = ResponseCache(db_path=temp_db_path)
    await cache1.set("persist_key", "persist_value", "gpt-4", "cloud", {"test": True})

    # Verify it's there
    result = await cache1.get("persist_key")
    assert result is not None
    assert result.content == "persist_value"

    # Create new instance pointing to same database
    cache2 = ResponseCache(db_path=temp_db_path)
    cache2._initialized = False  # Force re-init

    # Data should still be there
    result = await cache2.get("persist_key")
    assert result is not None
    assert result.content == "persist_value"
    assert result.metadata == {"test": True}


@pytest.mark.asyncio
async def test_cache_handles_special_characters(cache):
    """Test caching content with special characters."""
    content = 'Test with "quotes" and \'apostrophes\' and\nnewlines\tand\ttabs'
    metadata = {"key": "value with spaces and 'quotes'"}

    await cache.set("special_key", content, "gpt-4", "cloud", metadata)
    result = await cache.get("special_key")

    assert result.content == content
    assert result.metadata == metadata


@pytest.mark.asyncio
async def test_cache_handles_unicode(cache):
    """Test caching content with unicode characters."""
    content = "Unicode test: Hello World!"
    metadata = {"greeting": "Hello!"}

    await cache.set("unicode_key", content, "gpt-4", "cloud", metadata)
    result = await cache.get("unicode_key")

    assert result.content == content
    assert result.metadata == metadata


@pytest.mark.asyncio
async def test_cache_handles_empty_metadata(cache):
    """Test caching with None/empty metadata."""
    await cache.set("key1", "value1", "gpt-4", "cloud", None)
    result = await cache.get("key1")
    assert result.metadata == {}

    await cache.set("key2", "value2", "gpt-4", "cloud", {})
    result = await cache.get("key2")
    assert result.metadata == {}
