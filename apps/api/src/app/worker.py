import logging
import uuid
from collections.abc import Awaitable, Callable
from functools import cache
from typing import Any

from aiogram import Bot

from app.container import get_container
from app.infra.telegram import AiogramSender, build_bot
from app.services.indexing import IndexingService
from app.services.manager_chat import ManagerChat

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger(__name__)

Context = dict[str, Any]


@cache
def _bot() -> Bot | None:
    settings = get_container().settings
    return build_bot(settings.telegram_bot_token) if settings.telegram_enabled else None


async def index_source(_: Context, *, source_id: str) -> None:
    container = get_container()
    async with container.database.session() as session:
        service = IndexingService(session, container.embedder, container.crawler, container.storage)
        await service.index_source(uuid.UUID(source_id))


async def _with_manager_chat(action: Callable[[ManagerChat], Awaitable[bool]]) -> None:
    bot = _bot()
    if bot is None:
        return  # no Telegram configured: the admin inbox is the only channel
    async with get_container().database.session() as session:
        await action(ManagerChat(session, AiogramSender(bot)))


async def notify_handoff(_: Context, *, conversation_id: str) -> None:
    await _with_manager_chat(lambda chat: chat.announce_handoff(uuid.UUID(conversation_id)))


async def forward_visitor_message(_: Context, *, conversation_id: str, message_id: int) -> None:
    await _with_manager_chat(
        lambda chat: chat.forward_visitor_message(uuid.UUID(conversation_id), message_id)
    )


async def notify_lead(_: Context, *, lead_id: str) -> None:
    await _with_manager_chat(lambda chat: chat.announce_lead(uuid.UUID(lead_id)))


settings = {
    "queue": get_container().queue,
    "functions": [index_source, notify_handoff, forward_visitor_message, notify_lead],
    "concurrency": 4,
}
