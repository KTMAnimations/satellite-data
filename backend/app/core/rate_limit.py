"""
Redis-based rate limiting middleware for FastAPI.

Implements sliding window rate limiting per IP address and/or API key.
Default limits: 100 requests/minute for anonymous, 1000 requests/minute for authenticated.
"""

import time
from typing import Callable

from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.redis import get_redis_client

logger = get_logger(__name__)

# Rate limit key prefix
RATE_LIMIT_PREFIX = "rate_limit"

# Default rate limits (requests per minute)
DEFAULT_RATE_LIMIT_ANONYMOUS = 100
DEFAULT_RATE_LIMIT_AUTHENTICATED = 1000
RATE_LIMIT_WINDOW_SECONDS = 60


class RateLimitExceeded(HTTPException):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please slow down.",
            headers={"Retry-After": str(retry_after)},
        )


async def check_rate_limit(
    identifier: str,
    limit: int = DEFAULT_RATE_LIMIT_ANONYMOUS,
    window: int = RATE_LIMIT_WINDOW_SECONDS,
) -> tuple[bool, int, int]:
    """
    Check if a request should be rate limited using sliding window algorithm.

    Args:
        identifier: Unique identifier for the client (IP or API key)
        limit: Maximum requests allowed in the window
        window: Time window in seconds

    Returns:
        Tuple of (allowed, remaining, reset_time)
    """
    redis_client = get_redis_client()
    await redis_client.connect()

    key = f"{RATE_LIMIT_PREFIX}:{identifier}"
    now = time.time()
    window_start = now - window

    # Use Redis pipeline for atomic operations
    redis = redis_client._redis
    if redis is None:
        # Redis not available, allow request but log warning
        logger.warning("Redis unavailable for rate limiting, allowing request")
        return True, limit, int(now + window)

    try:
        # Remove old entries outside the window
        await redis.zremrangebyscore(key, 0, window_start)

        # Count requests in current window
        current_count = await redis.zcard(key)

        if current_count >= limit:
            # Rate limit exceeded
            # Get oldest entry to calculate reset time
            oldest = await redis.zrange(key, 0, 0, withscores=True)
            if oldest:
                reset_time = int(oldest[0][1] + window)
            else:
                reset_time = int(now + window)
            return False, 0, reset_time

        # Add current request
        await redis.zadd(key, {str(now): now})

        # Set expiry on the key
        await redis.expire(key, window * 2)

        remaining = limit - current_count - 1
        reset_time = int(now + window)

        return True, remaining, reset_time

    except Exception as e:
        logger.error("Rate limit check failed", error=str(e))
        # On error, allow the request
        return True, limit, int(now + window)


def get_client_identifier(request: Request) -> tuple[str, bool]:
    """
    Get a unique identifier for the client.

    Returns:
        Tuple of (identifier, is_authenticated)
    """
    # Check for API key in header
    api_key = request.headers.get("X-API-Key")
    if api_key:
        # Use a hash prefix of the API key as identifier
        return f"key:{api_key[:16]}", True

    # Fall back to IP address
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"

    return f"ip:{ip}", False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware for rate limiting API requests.

    Applies different rate limits for anonymous vs authenticated requests.
    Adds rate limit headers to responses.
    """

    def __init__(
        self,
        app,
        anonymous_limit: int = DEFAULT_RATE_LIMIT_ANONYMOUS,
        authenticated_limit: int = DEFAULT_RATE_LIMIT_AUTHENTICATED,
        window_seconds: int = RATE_LIMIT_WINDOW_SECONDS,
        exempt_paths: list[str] | None = None,
    ):
        super().__init__(app)
        self.anonymous_limit = anonymous_limit
        self.authenticated_limit = authenticated_limit
        self.window_seconds = window_seconds
        self.exempt_paths = exempt_paths or [
            "/health",
            "/health/live",
            "/health/ready",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and apply rate limiting."""
        # Skip rate limiting for exempt paths
        if any(request.url.path.startswith(path) for path in self.exempt_paths):
            return await call_next(request)

        # Get client identifier and authentication status
        identifier, is_authenticated = get_client_identifier(request)

        # Determine rate limit based on authentication
        limit = self.authenticated_limit if is_authenticated else self.anonymous_limit

        # Check rate limit
        allowed, remaining, reset_time = await check_rate_limit(
            identifier, limit, self.window_seconds
        )

        if not allowed:
            retry_after = max(1, reset_time - int(time.time()))
            logger.warning(
                "Rate limit exceeded",
                identifier=identifier,
                limit=limit,
                retry_after=retry_after,
            )
            raise RateLimitExceeded(retry_after=retry_after)

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)

        return response


# Dependency for route-specific rate limiting
async def rate_limit_dependency(
    request: Request,
    limit: int = DEFAULT_RATE_LIMIT_ANONYMOUS,
    window: int = RATE_LIMIT_WINDOW_SECONDS,
) -> None:
    """
    Dependency for applying custom rate limits to specific routes.

    Usage:
        @router.post("/expensive-operation")
        async def expensive_op(
            _: None = Depends(lambda r: rate_limit_dependency(r, limit=10, window=60))
        ):
            ...
    """
    identifier, is_authenticated = get_client_identifier(request)

    allowed, remaining, reset_time = await check_rate_limit(identifier, limit, window)

    if not allowed:
        retry_after = max(1, reset_time - int(time.time()))
        raise RateLimitExceeded(retry_after=retry_after)
