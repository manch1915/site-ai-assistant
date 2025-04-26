import json
import time
from collections.abc import AsyncIterator, Awaitable
from typing import Any, cast

from redis.asyncio import Redis

_RELEASE = """
local value = tonumber(redis.call("GET", KEYS[1]) or "0")
if value > 0 then redis.call("DECR", KEYS[1]) end
return value
"""


class RateLimiter:
    """Fixed one-minute window in Redis. Simple and good enough for a chat widget."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def reserve(self, key: str, limit: int, window_seconds: int = 60) -> str | None:
        """Takes one slot; returns the bucket key to release later, or None when over limit."""
        bucket = int(time.time() // window_seconds)
        redis_key = f"rl:{key}:{bucket}"
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.incr(redis_key)
            pipe.expire(redis_key, window_seconds * 2)
            count, _ = await pipe.execute()
        return redis_key if int(count) <= limit else None

    async def allow(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        return await self.reserve(key, limit, window_seconds) is not None

    async def release(self, redis_key: str) -> None:
        """Gives a reserved slot back, e.g. after a successful login. Never goes below zero."""
        await cast(Awaitable[Any], self.redis.eval(_RELEASE, 1, redis_key))


class EventBus:
    """Pushes manager replies and status changes to open widget connections."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    @staticmethod
    def channel(conversation_id: str) -> str:
        return f"conv:{conversation_id}"

    async def publish(self, conversation_id: str, event: dict[str, Any]) -> None:
        await self.redis.publish(self.channel(conversation_id), json.dumps(event, default=str))

    async def listen(
        self, conversation_id: str, heartbeat_seconds: float = 15
    ) -> AsyncIterator[dict[str, Any] | None]:
        """Yields events, or None every heartbeat so the caller can ping the client."""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(self.channel(conversation_id))
        try:
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=heartbeat_seconds
                )
                if message is None:
                    yield None
                    continue
                yield json.loads(message["data"])
        finally:
            await pubsub.unsubscribe()
            await pubsub.aclose()  # type: ignore[no-untyped-call]
