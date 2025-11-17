"""
Redis caching service with optimized performance for RAG queries.

Target: 70%+ cache hit rate, <10ms cache operations
"""

import hashlib
import json
from typing import Any, Optional
from datetime import timedelta

import redis.asyncio as redis
from loguru import logger

from app.config import settings


class CacheService:
    """High-performance Redis cache with async support."""

    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._hits = 0
        self._misses = 0

    async def connect(self):
        """Establish Redis connection pool."""
        try:
            self._redis = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                max_connections=50,
                socket_keepalive=True,
                socket_connect_timeout=5,
                health_check_interval=30,
            )
            # Test connection
            await self._redis.ping()
            logger.info(f"✓ Connected to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        except Exception as e:
            logger.error(f"✗ Redis connection failed: {e}")
            raise

    async def disconnect(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            logger.info("Redis connection closed")

    def _generate_key(self, prefix: str, data: dict) -> str:
        """Generate deterministic cache key from data."""
        # Sort keys for consistency
        sorted_data = json.dumps(data, sort_keys=True, ensure_ascii=False)
        hash_digest = hashlib.sha256(sorted_data.encode('utf-8')).hexdigest()[:16]
        return f"{prefix}:{hash_digest}"

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self._redis:
            return None

        try:
            value = await self._redis.get(key)
            if value:
                self._hits += 1
                logger.debug(f"Cache HIT: {key}")
                return json.loads(value)
            else:
                self._misses += 1
                logger.debug(f"Cache MISS: {key}")
                return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = None
    ) -> bool:
        """Set value in cache with TTL."""
        if not self._redis:
            return False

        ttl = ttl or settings.CACHE_TTL

        try:
            serialized = json.dumps(value, ensure_ascii=False)
            await self._redis.set(key, serialized, ex=ttl)
            logger.debug(f"Cache SET: {key} (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False

    async def get_or_compute(
        self,
        key: str,
        compute_fn,
        ttl: int = None,
        *args,
        **kwargs
    ) -> Any:
        """Get from cache or compute and cache result."""
        # Try cache first
        cached = await self.get(key)
        if cached is not None:
            return cached

        # Compute result
        result = await compute_fn(*args, **kwargs) if hasattr(compute_fn, '__call__') else compute_fn

        # Cache result
        await self.set(key, result, ttl)
        return result

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self._redis:
            return False

        try:
            await self._redis.delete(key)
            logger.debug(f"Cache DELETE: {key}")
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern."""
        if not self._redis:
            return 0

        try:
            keys = []
            async for key in self._redis.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                deleted = await self._redis.delete(*keys)
                logger.info(f"Deleted {deleted} keys matching '{pattern}'")
                return deleted
            return 0
        except Exception as e:
            logger.error(f"Cache delete pattern error: {e}")
            return 0

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self._redis:
            return False

        try:
            return bool(await self._redis.exists(key))
        except Exception as e:
            logger.error(f"Cache exists error: {e}")
            return False

    def get_stats(self) -> dict:
        """Get cache performance statistics."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0

        return {
            "hits": self._hits,
            "misses": self._misses,
            "total_requests": total,
            "hit_rate_percent": round(hit_rate, 2),
        }

    def reset_stats(self):
        """Reset cache statistics."""
        self._hits = 0
        self._misses = 0
        logger.info("Cache stats reset")


# Global cache instance
cache_service = CacheService()


# Convenience functions
async def get_cache(key: str) -> Optional[Any]:
    """Get value from cache."""
    return await cache_service.get(key)


async def set_cache(key: str, value: Any, ttl: int = None) -> bool:
    """Set value in cache."""
    return await cache_service.set(key, value, ttl)


async def delete_cache(key: str) -> bool:
    """Delete key from cache."""
    return await cache_service.delete(key)


async def get_cache_stats() -> dict:
    """Get cache statistics."""
    return cache_service.get_stats()
