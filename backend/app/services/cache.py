"""
SIMS Plus - Cache Service

Generic Redis caching with graceful degradation.
All cache operations are wrapped in try/except to fall through to DB on failure.
"""

import json
from typing import Any, Callable, Optional

import structlog
from redis.asyncio import Redis

logger = structlog.get_logger()


class CacheService:
    """Redis cache service with graceful degradation."""

    def __init__(self, redis: Optional[Redis]):
        self.redis = redis

    async def get(self, key: str) -> Optional[str]:
        """Get a value from cache. Returns None on miss or error."""
        if not self.redis:
            return None
        try:
            return await self.redis.get(key)
        except Exception:
            logger.warning("cache_get_failed", key=key, exc_info=True)
            return None

    async def set(self, key: str, value: str, ttl: int = 300) -> bool:
        """Set a value in cache. Returns False on error."""
        if not self.redis:
            return False
        try:
            await self.redis.set(key, value, ex=ttl)
            return True
        except Exception:
            logger.warning("cache_set_failed", key=key, exc_info=True)
            return False

    async def get_json(self, key: str) -> Optional[Any]:
        """Get a JSON value from cache."""
        raw = await self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    async def set_json(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set a JSON value in cache."""
        try:
            return await self.set(key, json.dumps(value, default=str), ttl)
        except (TypeError, ValueError):
            return False

    async def get_or_set(
        self,
        key: str,
        ttl: int,
        factory: Callable,
    ) -> Any:
        """
        Get from cache or call factory to compute, then cache.

        Args:
            key: Cache key
            ttl: Time to live in seconds
            factory: Async callable that returns the value to cache
        """
        cached = await self.get_json(key)
        if cached is not None:
            return cached

        result = await factory()
        await self.set_json(key, result, ttl)
        return result

    async def invalidate(self, pattern: str) -> int:
        """Delete keys matching a glob pattern. Returns count deleted."""
        if not self.redis:
            return 0
        try:
            keys = []
            async for key in self.redis.scan_iter(match=pattern, count=100):
                keys.append(key)
            if keys:
                return await self.redis.delete(*keys)
            return 0
        except Exception:
            logger.warning("cache_invalidate_failed", pattern=pattern, exc_info=True)
            return 0

    async def invalidate_key(self, key: str) -> bool:
        """Delete a single cache key."""
        if not self.redis:
            return False
        try:
            await self.redis.delete(key)
            return True
        except Exception:
            logger.warning("cache_invalidate_key_failed", key=key, exc_info=True)
            return False
