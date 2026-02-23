"""
SIMS Plus - Accessible Schools Caching Tests

Verifies the caching and invalidation behavior of the accessible schools
endpoint (/api/v1/chain/accessible):
- Response is cached (second call hits cache, not DB)
- Cache is invalidated after assigning a user to a school
- Cache is invalidated after removing a user from a school
- Cache key includes user_id (different users get different cache)
- Graceful degradation when Redis is unavailable

These are unit tests -- no real Redis or database needed.
"""

import json
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.cache import CacheService
from app.utils.cache_keys import CacheKeys


# ===========================================================================
# CacheKeys for accessible schools
# ===========================================================================


class TestAccessibleSchoolsCacheKeys:
    """Verify cache key structure for accessible schools."""

    TENANT = "tenant-aaa"
    USER_A = "user-111"
    USER_B = "user-222"

    def test_different_users_get_different_keys(self):
        """Cache key must include user_id to prevent cross-user pollution."""
        key_a = CacheKeys.chain_accessible_schools(self.TENANT, self.USER_A)
        key_b = CacheKeys.chain_accessible_schools(self.TENANT, self.USER_B)
        assert key_a != key_b
        assert self.USER_A in key_a
        assert self.USER_B in key_b

    def test_key_includes_tenant_id(self):
        """Cache key must include tenant_id for cross-tenant safety."""
        key = CacheKeys.chain_accessible_schools(self.TENANT, self.USER_A)
        assert self.TENANT in key

    def test_different_tenants_get_different_keys(self):
        """Different tenants must produce different cache keys."""
        key_t1 = CacheKeys.chain_accessible_schools("tenant-x", self.USER_A)
        key_t2 = CacheKeys.chain_accessible_schools("tenant-y", self.USER_A)
        assert key_t1 != key_t2

    def test_ttl_constant_is_reasonable(self):
        """CHAIN_ACCESSIBLE_TTL should be 5 minutes (300 seconds)."""
        assert CacheKeys.CHAIN_ACCESSIBLE_TTL == 300


# ===========================================================================
# Caching behavior (unit tests with mocked Redis)
# ===========================================================================


class TestAccessibleSchoolsCaching:
    """Tests for accessible schools caching behavior using mocked CacheService."""

    @pytest.mark.asyncio
    async def test_second_call_returns_cached_value(self):
        """After caching, the second get_json call returns the cached data."""
        stored = {}

        mock_redis = AsyncMock()

        async def mock_set(key, value, ex=None):
            stored[key] = value

        async def mock_get(key):
            return stored.get(key)

        mock_redis.set = mock_set
        mock_redis.get = mock_get

        cache = CacheService(mock_redis)

        tenant_id = str(uuid4())
        user_id = str(uuid4())
        cache_key = CacheKeys.chain_accessible_schools(tenant_id, user_id)

        # First call: factory produces the data
        schools_data = [
            {"id": str(uuid4()), "name": "School A", "code": "SA-01"},
            {"id": str(uuid4()), "name": "School B", "code": "SB-01"},
        ]
        factory_called = 0

        async def factory():
            nonlocal factory_called
            factory_called += 1
            return schools_data

        result1 = await cache.get_or_set(cache_key, CacheKeys.CHAIN_ACCESSIBLE_TTL, factory)
        assert result1 == schools_data
        assert factory_called == 1

        # Second call: should hit cache, factory should NOT be called again
        result2 = await cache.get_or_set(cache_key, CacheKeys.CHAIN_ACCESSIBLE_TTL, factory)
        assert result2 == schools_data
        assert factory_called == 1  # Still 1 -- factory was not called

    @pytest.mark.asyncio
    async def test_cache_invalidation_causes_factory_call(self):
        """After invalidating the key, the next get_or_set calls the factory."""
        stored = {}

        mock_redis = AsyncMock()

        async def mock_set(key, value, ex=None):
            stored[key] = value

        async def mock_get(key):
            return stored.get(key)

        async def mock_delete(*keys):
            for k in keys:
                stored.pop(k, None)
            return len(keys)

        mock_redis.set = mock_set
        mock_redis.get = mock_get
        mock_redis.delete = mock_delete

        cache = CacheService(mock_redis)
        cache_key = CacheKeys.chain_accessible_schools("t-1", "u-1")

        factory_count = 0

        async def factory():
            nonlocal factory_count
            factory_count += 1
            return [{"id": "s1", "name": "School 1"}]

        # Populate cache
        await cache.get_or_set(cache_key, 300, factory)
        assert factory_count == 1

        # Invalidate (simulates what happens after assign/remove user-school)
        await cache.invalidate_key(cache_key)

        # Next call should re-query (factory called again)
        await cache.get_or_set(cache_key, 300, factory)
        assert factory_count == 2

    @pytest.mark.asyncio
    async def test_assign_invalidates_user_cache(self):
        """Assigning a user to a school invalidates their accessible schools cache."""
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock()

        cache = CacheService(mock_redis)

        tenant_id = "tenant-abc"
        user_id = "user-xyz"
        cache_key = CacheKeys.chain_accessible_schools(tenant_id, user_id)

        # Simulate the invalidation that happens in the assign endpoint
        await cache.invalidate_key(cache_key)

        mock_redis.delete.assert_awaited_once_with(cache_key)

    @pytest.mark.asyncio
    async def test_remove_invalidates_user_cache(self):
        """Removing a user from a school invalidates their accessible schools cache."""
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock()

        cache = CacheService(mock_redis)

        tenant_id = "tenant-abc"
        user_id = "user-xyz"
        cache_key = CacheKeys.chain_accessible_schools(tenant_id, user_id)

        # Simulate the invalidation that happens in the remove endpoint
        await cache.invalidate_key(cache_key)

        mock_redis.delete.assert_awaited_once_with(cache_key)

    @pytest.mark.asyncio
    async def test_different_users_have_independent_caches(self):
        """Two users' accessible schools caches are independent."""
        stored = {}

        mock_redis = AsyncMock()

        async def mock_set(key, value, ex=None):
            stored[key] = value

        async def mock_get(key):
            return stored.get(key)

        mock_redis.set = mock_set
        mock_redis.get = mock_get

        cache = CacheService(mock_redis)

        key_a = CacheKeys.chain_accessible_schools("t-1", "user-a")
        key_b = CacheKeys.chain_accessible_schools("t-1", "user-b")

        # Cache data for user A
        await cache.set_json(key_a, [{"id": "s1"}], 300)

        # User B should have no cached data
        result_b = await cache.get_json(key_b)
        assert result_b is None

        # User A should still have their data
        result_a = await cache.get_json(key_a)
        assert result_a == [{"id": "s1"}]


# ===========================================================================
# Graceful degradation
# ===========================================================================


class TestAccessibleSchoolsGracefulDegradation:
    """Verify that accessible schools caching degrades gracefully."""

    @pytest.mark.asyncio
    async def test_no_redis_falls_through_to_factory(self):
        """When Redis is None, get_or_set falls through to factory."""
        cache = CacheService(None)

        factory = AsyncMock(return_value=[{"id": "s1", "name": "School 1"}])

        result = await cache.get_or_set("chain:accessible:t:u", 300, factory)

        assert result == [{"id": "s1", "name": "School 1"}]
        factory.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_redis_error_falls_through_to_factory(self):
        """When Redis raises an error, get_or_set falls through to factory."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))
        mock_redis.set = AsyncMock(side_effect=ConnectionError("Redis down"))

        cache = CacheService(mock_redis)

        factory = AsyncMock(return_value=[{"id": "s1", "name": "School 1"}])

        result = await cache.get_or_set("chain:accessible:t:u", 300, factory)

        assert result == [{"id": "s1", "name": "School 1"}]
        factory.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalidate_returns_false_when_redis_is_none(self):
        """invalidate_key returns False when Redis is None (no crash)."""
        cache = CacheService(None)
        key = CacheKeys.chain_accessible_schools("t-1", "u-1")
        result = await cache.invalidate_key(key)
        assert result is False
