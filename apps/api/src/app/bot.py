"""Telegram bot for managers: links a chat to a site and relays replies to visitors."""

import asyncio
import html
import logging
import uuid

from aiogram import Dispatcher, F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, Message

from app.container import Container, get_container
from app.infra.db.models import Conversation
from app.infra.realtime import EventBus
from app.infra.telegram import AiogramSender, build_bot
from app.services.handoff import HandoffService
from app.services.manager_chat import CLOSE_PREFIX, ManagerChat

log = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart(deep_link=True))
async def link_chat(
    message: Message, command: CommandObject, container: Container, sender: AiogramSender
) -> None:
    title = message.chat.title or message.chat.full_name or "private chat"
    async with container.database.session() as session:
        site = await ManagerChat(session, sender).link_chat(
            command.args or "", message.chat.id, title
        )
    if site is None:
        await message.answer("This link has expired. Copy a fresh one from the admin panel.")
        return
    await message.answer(
        f"Done. Chats from <b>{html.escape(site.name)}</b> that need a person will show up "
        "here. Reply to a bot message to answer the visitor."
    )


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        "I pass website chats to managers. Open the admin panel, go to Settings, then Telegram, "
        "and use the connect link there."
    )


@router.message(F.reply_to_message, F.text)
async def manager_reply(message: Message, container: Container, sender: AiogramSender) -> None:
    assert message.reply_to_message is not None and message.text is not None
    async with container.database.session() as session:
        manager_chat = ManagerChat(session, sender)
        conversation = await manager_chat.conversation_for_reply(
            message.chat.id, message.reply_to_message.message_id
        )
        if conversation is None:
            return
        author = message.from_user.first_name if message.from_user else "Manager"
        handoff = HandoffService(session, container.notifier, EventBus(container.redis))
        await handoff.manager_reply(conversation, message.text, author)
        # Replying to the manager's own message should reach the same visitor too.
        await manager_chat.track(message.chat.id, message.message_id, conversation.id)


class CloseChat(CallbackData, prefix=CLOSE_PREFIX):
    conversation_id: uuid.UUID


@router.callback_query(CloseChat.filter())
async def close_chat(
    query: CallbackQuery, callback_data: CloseChat, container: Container, sender: AiogramSender
) -> None:
    chat_id = query.message.chat.id if query.message else None
    async with container.database.session() as session:
        owns = chat_id is not None and await ManagerChat(session, sender).chat_owns_conversation(
            chat_id, callback_data.conversation_id
        )
        conversation = await session.get(Conversation, callback_data.conversation_id)
        if conversation is not None and owns:
            handoff = HandoffService(session, container.notifier, EventBus(container.redis))
            await handoff.close(conversation)
    await query.answer("Chat closed. The bot answers this visitor again.")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    container = get_container()
    settings = container.settings
    if not settings.telegram_enabled or not settings.telegram_receive_updates:
        log.warning("Not reading Telegram updates (no token, or the token is shared)")
        await asyncio.Event().wait()
    bot = build_bot(settings.telegram_bot_token)
    dispatcher = Dispatcher(container=container, sender=AiogramSender(bot))
    dispatcher.include_router(router)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
