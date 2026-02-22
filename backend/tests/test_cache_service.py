"""
Tests for the CacheService.

Verifies cache behavior:
- Cache miss triggers factory, caches result
- Cache hit returns cached value without calling factory
- Graceful degradation when Redis is None
- Key invalidation
- JSON serialization/deserialization

These are unit tests -- no database or real Redis needed.
"""

import json

import pytest
from unittest.mock import AsyncMock

from app.services.cache import CacheService


# --- get_or_set ---


@pytest.mark.asyncio
async def test_get_or_set_calls_factory_on_miss():
    """get_or_set should call factory and cache the result on cache miss."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()

    cache = CacheService(mock_redis)
    factory = AsyncMock(return_value={"count": 42})

    result = await cache.get_or_set("test:key", 60, factory)

    assert result == {"count": 42}
    factory.assert_awaited_once()
    # set should have been called to cache the result
    mock_redis.set.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_or_set_returns_cached_on_hit():
    """get_or_set should return cached value without calling factory on cache hit."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=json.dumps({"count": 42}))

    cache = CacheService(mock_redis)
    factory = AsyncMock(return_value={"count": 99})

    result = await cache.get_or_set("test:key", 60, factory)

    assert result == {"count": 42}
    factory.assert_not_awaited()


# --- Graceful degradation ---


@pytest.mark.asyncio
async def test_get_returns_none_when_redis_is_none():
    """CacheService.get with None redis should return None, not crash."""
    cache = CacheService(None)
    result = await cache.get("some:key")
    assert result is None


@pytest.mark.asyncio
async def test_set_returns_false_when_redis_is_none():
    """CacheService.set with None redis should return False, not crash."""
    cache = CacheService(None)
    success = await cache.set("some:key", "value", 60)
    assert success is False


@pytest.mark.asyncio
async def test_get_or_set_falls_through_when_redis_is_none():
    """get_or_set with None redis should call factory directly."""
    cache = CacheService(None)
    factory = AsyncMock(return_value={"data": "fresh"})

    result = await cache.get_or_set("some:key", 60, factory)

    assert result == {"data": "fresh"}
    factory.assert_awaited_once()


@pytest.mark.asyncio
async def test_invalidate_returns_zero_when_redis_is_none():
    """invalidate with None redis should return 0."""
    cache = CacheService(None)
    count = await cache.invalidate("test:*")
    assert count == 0


@pytest.mark.asyncio
async def test_invalidate_key_returns_false_when_redis_is_none():
    """invalidate_key with None redis should return False."""
    cache = CacheService(None)
    result = await cache.invalidate_key("test:key")
    assert result is False


# --- get / set basics ---


@pytest.mark.asyncio
async def test_get_returns_stored_value():
    """get should return the value stored by set."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value="hello")

    cache = CacheService(mock_redis)
    result = await cache.get("greeting")

    assert result == "hello"
    mock_redis.get.assert_awaited_once_with("greeting")


@pytest.mark.asyncio
async def test_set_calls_redis_with_ttl():
    """set should pass the key, value, and TTL to redis."""
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock()

    cache = CacheService(mock_redis)
    result = await cache.set("my:key", "my_value", 120)

    assert result is True
    mock_redis.set.assert_awaited_once_with("my:key", "my_value", ex=120)


# --- invalidate_key ---


@pytest.mark.asyncio
async def test_invalidate_key_deletes_key():
    """invalidate_key should call redis.delete with the key."""
    mock_redis = AsyncMock()
    mock_redis.delete = AsyncMock()

    cache = CacheService(mock_redis)
    result = await cache.invalidate_key("test:key")

    assert result is True
    mock_redis.delete.assert_awaited_once_with("test:key")


# --- JSON round-trip ---


@pytest.mark.asyncio
async def test_set_json_and_get_json_round_trip():
    """set_json and get_json should correctly serialize/deserialize JSON."""
    # Use a real dict to track stored values (instead of mocking return values)
    stored = {}

    mock_redis = AsyncMock()

    async def mock_set(key, value, ex=None):
        stored[key] = value

    async def mock_get(key):
        return stored.get(key)

    mock_redis.set = mock_set
    mock_redis.get = mock_get

    cache = CacheService(mock_redis)

    # Store JSON
    await cache.set_json("test:json", {"name": "Kwame", "age": 25}, 300)

    # Retrieve JSON
    result = await cache.get_json("test:json")

    assert result == {"name": "Kwame", "age": 25}


@pytest.mark.asyncio
async def test_get_json_returns_none_on_invalid_json():
    """get_json should return None when stored value is not valid JSON."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value="not-valid-json{{{")

    cache = CacheService(mock_redis)
    result = await cache.get_json("broken:key")

    assert result is None


@pytest.mark.asyncio
async def test_get_json_returns_none_on_miss():
    """get_json should return None when key does not exist."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)

    cache = CacheService(mock_redis)
    result = await cache.get_json("missing:key")

    assert result is None


# --- Error handling ---


@pytest.mark.asyncio
async def test_get_handles_redis_exception():
    """get should return None (not raise) when Redis throws an exception."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))

    cache = CacheService(mock_redis)
    result = await cache.get("failing:key")

    assert result is None


@pytest.mark.asyncio
async def test_set_handles_redis_exception():
    """set should return False (not raise) when Redis throws an exception."""
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(side_effect=ConnectionError("Redis down"))

    cache = CacheService(mock_redis)
    result = await cache.set("failing:key", "value", 60)

    assert result is False


@pytest.mark.asyncio
async def test_invalidate_key_handles_redis_exception():
    """invalidate_key should return False when Redis throws an exception."""
    mock_redis = AsyncMock()
    mock_redis.delete = AsyncMock(side_effect=ConnectionError("Redis down"))

    cache = CacheService(mock_redis)
    result = await cache.invalidate_key("failing:key")

    assert result is False
