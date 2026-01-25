"""
Redis client utility for async status tracking.

Provides get_status, set_status, delete_status methods for managing
task/export/analysis status with automatic 24-hour expiration.
"""

import json
from typing import Any

import redis.asyncio as redis

from app.core.config import get_settings

# Status key prefixes for different types
STATUS_PREFIX_EXPORT = "export_status"
STATUS_PREFIX_ANALYSIS = "analysis_status"
STATUS_PREFIX_COLLECTION = "collection_status"

# Default TTL: 24 hours in seconds
DEFAULT_TTL = 24 * 60 * 60


class RedisClient:
    """Async Redis client for status tracking."""

    _instance: "RedisClient | None" = None
    _redis: redis.Redis | None = None

    def __new__(cls) -> "RedisClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self) -> None:
        """Initialize Redis connection."""
        if self._redis is None:
            settings = get_settings()
            self._redis = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis is not None:
            await self._redis.close()
            self._redis = None

    def _get_key(self, prefix: str, key_id: str) -> str:
        """Build a Redis key with prefix."""
        return f"{prefix}:{key_id}"

    async def get_status(
        self,
        key_id: str,
        prefix: str = STATUS_PREFIX_EXPORT,
    ) -> dict[str, Any] | None:
        """
        Get status data by ID.

        Args:
            key_id: The unique identifier for the status entry
            prefix: The key prefix (export_status, analysis_status, collection_status)

        Returns:
            The status data as a dict, or None if not found
        """
        await self.connect()
        key = self._get_key(prefix, key_id)
        data = await self._redis.get(key)
        if data is None:
            return None
        return json.loads(data)

    async def set_status(
        self,
        key_id: str,
        data: dict[str, Any],
        prefix: str = STATUS_PREFIX_EXPORT,
        ttl: int = DEFAULT_TTL,
    ) -> None:
        """
        Set status data with auto-expiration.

        Args:
            key_id: The unique identifier for the status entry
            data: The status data to store
            prefix: The key prefix (export_status, analysis_status, collection_status)
            ttl: Time-to-live in seconds (default: 24 hours)
        """
        await self.connect()
        key = self._get_key(prefix, key_id)
        await self._redis.set(key, json.dumps(data, default=str), ex=ttl)

    async def delete_status(
        self,
        key_id: str,
        prefix: str = STATUS_PREFIX_EXPORT,
    ) -> bool:
        """
        Delete status data by ID.

        Args:
            key_id: The unique identifier for the status entry
            prefix: The key prefix

        Returns:
            True if the key was deleted, False if it didn't exist
        """
        await self.connect()
        key = self._get_key(prefix, key_id)
        result = await self._redis.delete(key)
        return result > 0

    async def update_status(
        self,
        key_id: str,
        updates: dict[str, Any],
        prefix: str = STATUS_PREFIX_EXPORT,
        ttl: int = DEFAULT_TTL,
    ) -> dict[str, Any] | None:
        """
        Update specific fields in status data.

        Args:
            key_id: The unique identifier for the status entry
            updates: Dictionary of fields to update
            prefix: The key prefix
            ttl: Time-to-live in seconds (default: 24 hours)

        Returns:
            The updated status data, or None if not found
        """
        await self.connect()
        existing = await self.get_status(key_id, prefix)
        if existing is None:
            return None
        existing.update(updates)
        await self.set_status(key_id, existing, prefix, ttl)
        return existing

    async def exists(
        self,
        key_id: str,
        prefix: str = STATUS_PREFIX_EXPORT,
    ) -> bool:
        """
        Check if a status entry exists.

        Args:
            key_id: The unique identifier for the status entry
            prefix: The key prefix

        Returns:
            True if the key exists, False otherwise
        """
        await self.connect()
        key = self._get_key(prefix, key_id)
        return await self._redis.exists(key) > 0


# Global client instance
_redis_client: RedisClient | None = None


def get_redis_client() -> RedisClient:
    """Get the global Redis client instance."""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client


async def close_redis_client() -> None:
    """Close the global Redis client connection."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
