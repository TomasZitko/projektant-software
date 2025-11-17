"""
Rate limiting middleware for API endpoints.

Implements token bucket algorithm with Redis backend.
Prevents API abuse and ensures fair resource allocation.
"""
import time
from typing import Optional, Callable
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger

from app.services.cache import cache_service


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using token bucket algorithm.

    Configuration:
    - Max requests per minute per IP: 60
    - Burst capacity: 10
    - Compliance endpoint: 100/min (higher limit)
    """

    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled
        self.default_limit = 60  # requests per minute
        self.burst_capacity = 10  # additional burst requests
        self.compliance_limit = 100  # higher limit for compliance checks

        # Endpoint-specific limits
        self.endpoint_limits = {
            "/api/v1/compliance/check": self.compliance_limit,
            "/health": 300,  # Health checks can be frequent
            "/metrics": 60,
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        if not self.enabled:
            return await call_next(request)

        # Skip rate limiting for certain paths
        if self._should_skip(request.url.path):
            return await call_next(request)

        # Get client identifier (IP address)
        client_ip = self._get_client_ip(request)

        # Get rate limit for this endpoint
        limit = self._get_limit_for_path(request.url.path)

        # Check rate limit
        allowed, retry_after = await self._check_rate_limit(client_ip, request.url.path, limit)

        if not allowed:
            logger.warning(f"Rate limit exceeded for {client_ip} on {request.url.path}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Please try again in {retry_after} seconds.",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(
            await self._get_remaining(client_ip, request.url.path, limit)
        )

        return response

    def _should_skip(self, path: str) -> bool:
        """Check if path should skip rate limiting."""
        skip_paths = [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/",  # Root endpoint
        ]
        return path in skip_paths

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address."""
        # Check X-Forwarded-For header (for proxies)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct connection
        if request.client:
            return request.client.host

        return "unknown"

    def _get_limit_for_path(self, path: str) -> int:
        """Get rate limit for specific path."""
        for endpoint, limit in self.endpoint_limits.items():
            if path.startswith(endpoint):
                return limit
        return self.default_limit

    async def _check_rate_limit(
        self, client_id: str, path: str, limit: int
    ) -> tuple[bool, int]:
        """
        Check if request is within rate limit using token bucket algorithm.

        Returns:
            (allowed, retry_after_seconds)
        """
        if not cache_service._redis:
            # If Redis not available, allow request (fail open)
            logger.warning("Redis not available, rate limiting disabled")
            return True, 0

        # Create rate limit key
        window_start = int(time.time() / 60) * 60  # Start of current minute
        key = f"ratelimit:{client_id}:{path}:{window_start}"

        try:
            # Get current count
            current_count = await cache_service._redis.get(key)

            if current_count is None:
                # First request in this window
                await cache_service._redis.setex(key, 60, 1)
                return True, 0

            current_count = int(current_count)

            if current_count >= limit:
                # Rate limit exceeded
                ttl = await cache_service._redis.ttl(key)
                retry_after = max(ttl, 1)
                return False, retry_after

            # Increment counter
            await cache_service._redis.incr(key)
            return True, 0

        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fail open - allow request
            return True, 0

    async def _get_remaining(self, client_id: str, path: str, limit: int) -> int:
        """Get remaining requests in current window."""
        if not cache_service._redis:
            return limit

        window_start = int(time.time() / 60) * 60
        key = f"ratelimit:{client_id}:{path}:{window_start}"

        try:
            current_count = await cache_service._redis.get(key)
            if current_count is None:
                return limit

            return max(0, limit - int(current_count))
        except Exception:
            return limit


class RequestQueue:
    """
    Request queue for handling bursts of traffic.

    When rate limit is hit, requests can be queued and processed later.
    """

    def __init__(self, max_queue_size: int = 100):
        self.max_queue_size = max_queue_size
        self.queues: dict[str, list] = {}

    async def enqueue(self, client_id: str, request_data: dict) -> bool:
        """Add request to queue."""
        if client_id not in self.queues:
            self.queues[client_id] = []

        if len(self.queues[client_id]) >= self.max_queue_size:
            logger.warning(f"Queue full for client {client_id}")
            return False

        self.queues[client_id].append({
            "data": request_data,
            "timestamp": time.time(),
        })

        logger.info(f"Queued request for {client_id}. Queue size: {len(self.queues[client_id])}")
        return True

    async def dequeue(self, client_id: str) -> Optional[dict]:
        """Get next request from queue."""
        if client_id not in self.queues or not self.queues[client_id]:
            return None

        request = self.queues[client_id].pop(0)

        # Check if request is too old (>5 minutes)
        if time.time() - request["timestamp"] > 300:
            logger.warning(f"Dropping stale queued request for {client_id}")
            return None

        return request["data"]

    def get_queue_size(self, client_id: str) -> int:
        """Get current queue size for client."""
        return len(self.queues.get(client_id, []))

    def clear_queue(self, client_id: str):
        """Clear queue for client."""
        if client_id in self.queues:
            del self.queues[client_id]
            logger.info(f"Cleared queue for {client_id}")


# Global request queue instance
request_queue = RequestQueue(max_queue_size=100)
