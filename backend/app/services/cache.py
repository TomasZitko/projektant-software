"""
Redis caching service for compliance checks.
"""
import json
import hashlib
from typing import Any, Optional
from redis.asyncio import Redis
from loguru import logger

from app.config import settings


class CacheService:
    """Redis cache service with automatic serialization."""

    def __init__(self):
        self._redis: Optional[Redis] = None

    async def connect(self):
        """Initialize Redis connection."""
        try:
            self._redis = Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
            )
            await self._redis.ping()
            logger.info("Redis cache connected successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._redis = None

    async def disconnect(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            logger.info("Redis cache disconnected")

    def _generate_cache_key(self, prefix: str, data: dict) -> str:
        """Generate deterministic cache key from request data."""
        # Sort keys for consistent hashing
        json_str = json.dumps(data, sort_keys=True)
        hash_key = hashlib.sha256(json_str.encode()).hexdigest()[:16]
        return f"{prefix}:{hash_key}"

    async def get(self, prefix: str, data: dict) -> Optional[dict]:
        """
        Get cached compliance result.

        Args:
            prefix: Cache key prefix (e.g., 'compliance')
            data: Request data for generating cache key

        Returns:
            Cached data or None if not found/Redis unavailable
        """
        if not self._redis or not settings.ENABLE_CACHE:
            return None

        try:
            cache_key = self._generate_cache_key(prefix, data)
            cached = await self._redis.get(cache_key)

            if cached:
                logger.debug(f"Cache HIT: {cache_key}")
                return json.loads(cached)

            logger.debug(f"Cache MISS: {cache_key}")
            return None

        except Exception as e:
            logger.warning(f"Cache get failed: {e}")
            return None

    async def set(
        self, prefix: str, data: dict, value: dict, ttl: Optional[int] = None
    ) -> bool:
        """
        Cache compliance result.

        Args:
            prefix: Cache key prefix
            data: Request data for generating cache key
            value: Data to cache
            ttl: Time to live in seconds (default: from config)

        Returns:
            True if cached successfully, False otherwise
        """
        if not self._redis or not settings.ENABLE_CACHE:
            return False

        try:
            cache_key = self._generate_cache_key(prefix, data)
            ttl = ttl or settings.CACHE_TTL

            await self._redis.setex(
                cache_key, ttl, json.dumps(value, default=str)
            )
            logger.debug(f"Cache SET: {cache_key} (TTL: {ttl}s)")
            return True

        except Exception as e:
            logger.warning(f"Cache set failed: {e}")
            return False

    async def delete(self, prefix: str, data: dict) -> bool:
        """Delete cached value."""
        if not self._redis:
            return False

        try:
            cache_key = self._generate_cache_key(prefix, data)
            await self._redis.delete(cache_key)
            logger.debug(f"Cache DELETE: {cache_key}")
            return True

        except Exception as e:
            logger.warning(f"Cache delete failed: {e}")
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern."""
        if not self._redis:
            return 0

        try:
            keys = await self._redis.keys(pattern)
            if keys:
                deleted = await self._redis.delete(*keys)
                logger.info(f"Cleared {deleted} cache keys matching '{pattern}'")
                return deleted
            return 0

        except Exception as e:
            logger.warning(f"Cache clear failed: {e}")
            return 0

    async def health_check(self) -> dict:
        """Check Redis connection health."""
        if not self._redis:
            return {"status": "disconnected", "error": "Redis not initialized"}

        try:
            await self._redis.ping()
            info = await self._redis.info()
            return {
                "status": "healthy",
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "uptime_in_seconds": info.get("uptime_in_seconds", 0),
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


# Global cache instance
cache_service = CacheService()
