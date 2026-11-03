"""Distributed idempotency checks for incoming review webhooks."""

from typing import Protocol

from redis.asyncio import Redis


class _RedisSetClient(Protocol):
    async def set(
        self,
        name: str,
        value: str,
        *,
        ex: int,
        nx: bool,
    ) -> object:
        """Set a key with Redis expiration and NX options."""


class RedisDeduplicator:
    """Prevent processing duplicate platform events across application workers."""

    def __init__(self, redis_client: Redis | _RedisSetClient) -> None:
        self._redis = redis_client

    async def is_duplicate(
        self,
        platform: str,
        external_id: str,
        ttl_seconds: int = 300,
    ) -> bool:
        """Return whether the platform event's idempotency key already exists."""
        normalized_platform = platform.strip().lower()
        normalized_external_id = external_id.strip()
        if not normalized_platform or not normalized_external_id:
            raise ValueError("platform and external_id must not be empty")
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int):
            raise ValueError("ttl_seconds must be a positive integer")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be a positive integer")

        key = f"dedup:review:{normalized_platform}:{normalized_external_id}"
        created = await self._redis.set(
            key,
            "1",
            nx=True,
            ex=ttl_seconds,
        )
        return not bool(created)
