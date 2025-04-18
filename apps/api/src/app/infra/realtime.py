import json
import time
from collections.abc import AsyncIterator
from typing import Any

from redis.asyncio import Redis


class RateLimiter:
    """Fixed one-minute window in Redis. Simple and good enough for a chat widget."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def allow(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        bucket = int(time.time() // window_seconds)
        redis_key = f"rl:{key}:{bucket}"
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.incr(redis_key)
            pipe.expire(redis_key, window_seconds * 2)
            count, _ = await pipe.execute()
        return int(count) <= limit

    async def count(self, key: str, window_seconds: int = 60) -> int:
        bucket = int(time.time() // window_seconds)
        value = await self.redis.get(f"rl:{key}:{bucket}")
        return int(value or 0)


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
