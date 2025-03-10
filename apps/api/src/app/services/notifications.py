import uuid
from typing import Protocol

from saq import Queue


class ManagerNotifier(Protocol):
    """Tells the managers' chat (Telegram) about things that need a human."""

    async def handoff_requested(self, conversation_id: uuid.UUID) -> None: ...

    async def visitor_message(self, conversation_id: uuid.UUID, message_id: int) -> None: ...

    async def lead_created(self, lead_id: uuid.UUID) -> None: ...


class QueueNotifier:
    """Hands the work to the worker so a slow Telegram API never blocks the widget."""

    def __init__(self, queue: Queue) -> None:
        self.queue = queue

    async def handoff_requested(self, conversation_id: uuid.UUID) -> None:
        await self.queue.enqueue("notify_handoff", conversation_id=str(conversation_id))

    async def visitor_message(self, conversation_id: uuid.UUID, message_id: int) -> None:
        await self.queue.enqueue(
            "forward_visitor_message", conversation_id=str(conversation_id), message_id=message_id
        )

    async def lead_created(self, lead_id: uuid.UUID) -> None:
        await self.queue.enqueue("notify_lead", lead_id=str(lead_id))
