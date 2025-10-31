"""Mirror of conversations in the managers' Telegram chat."""

import html
import secrets
import uuid
from typing import Protocol

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import MessageRole
from app.infra.db.models import Conversation, Lead, Message, Site, TelegramThread

TRANSCRIPT_MESSAGES = 8
ROLE_LABELS = {
    MessageRole.VISITOR: "Visitor",
    MessageRole.BOT: "Bot",
    MessageRole.MANAGER: "Manager",
}


class CloseChat(CallbackData, prefix="close"):
    conversation_id: uuid.UUID


class SentMessage(Protocol):
    @property
    def message_id(self) -> int: ...


class TelegramSender(Protocol):
    async def send_message(
        self,
        chat_id: int,
        text: str,
        *,
        reply_to_message_id: int | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> SentMessage: ...


def close_keyboard(conversation_id: uuid.UUID) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Close chat", callback_data=CloseChat(conversation_id=conversation_id))
    return builder.as_markup()


def _clip(text: str, limit: int = 600) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


class ManagerChat:
    def __init__(self, session: AsyncSession, sender: TelegramSender) -> None:
        self.session = session
        self.sender = sender

    async def track(self, chat_id: int, message_id: int, conversation_id: uuid.UUID) -> None:
        self.session.add(
            TelegramThread(chat_id=chat_id, message_id=message_id, conversation_id=conversation_id)
        )
        await self.session.commit()

    async def _context(self, conversation_id: uuid.UUID) -> tuple[Conversation, Site] | None:
        conversation = await self.session.get(Conversation, conversation_id)
        if conversation is None:
            return None
        site = await self.session.get(Site, conversation.site_id)
        if site is None or site.telegram_chat_id is None:
            return None
        return conversation, site

    async def announce_handoff(self, conversation_id: uuid.UUID) -> bool:
        context = await self._context(conversation_id)
        if context is None:
            return False
        conversation, site = context
        assert site.telegram_chat_id is not None
        rows = await self.session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id, Message.role.in_(ROLE_LABELS))
            .order_by(Message.id.desc())
            .limit(TRANSCRIPT_MESSAGES)
        )
        lines = [
            f"<b>{ROLE_LABELS[m.role]}:</b> {html.escape(_clip(m.content, 400))}"
            for m in reversed(list(rows))
        ]
        page = f"\nPage: {html.escape(conversation.page_url)}" if conversation.page_url else ""
        lead = await self.session.scalar(
            select(Lead)
            .where(Lead.conversation_id == conversation.id)
            .order_by(Lead.created_at.desc())
            .limit(1)
        )
        contact = (
            f"\nContact: {html.escape(lead.name)}, {html.escape(lead.contact)}" if lead else ""
        )
        text = (
            f"<b>{html.escape(site.name)}</b> · a visitor asked for a person{page}{contact}\n\n"
            + "\n".join(lines)
            + "\n\n<i>Reply to this message and the visitor will see your answer in the chat.</i>"
        )
        sent = await self.sender.send_message(
            site.telegram_chat_id, text, reply_markup=close_keyboard(conversation.id)
        )
        await self.track(site.telegram_chat_id, sent.message_id, conversation.id)
        return True

    async def forward_visitor_message(self, conversation_id: uuid.UUID, message_id: int) -> bool:
        context = await self._context(conversation_id)
        message = await self.session.get(Message, message_id)
        if context is None or message is None:
            return False
        conversation, site = context
        assert site.telegram_chat_id is not None
        last_thread = await self.session.scalar(
            select(TelegramThread.message_id)
            .where(TelegramThread.conversation_id == conversation.id)
            .order_by(TelegramThread.id.desc())
            .limit(1)
        )
        sent = await self.sender.send_message(
            site.telegram_chat_id,
            f"<b>Visitor:</b> {html.escape(_clip(message.content))}",
            reply_to_message_id=last_thread,
            reply_markup=close_keyboard(conversation.id),
        )
        await self.track(site.telegram_chat_id, sent.message_id, conversation.id)
        return True

    async def announce_lead(self, lead_id: uuid.UUID) -> bool:
        lead = await self.session.get(Lead, lead_id)
        if lead is None:
            return False
        site = await self.session.get(Site, lead.site_id)
        if site is None or site.telegram_chat_id is None:
            return False
        question = f"\n{html.escape(_clip(lead.question))}" if lead.question else ""
        await self.sender.send_message(
            site.telegram_chat_id,
            f"<b>{html.escape(site.name)}</b> · new request\n"
            f"<b>{html.escape(lead.name)}</b>, {html.escape(lead.contact)}{question}",
        )
        return True

    async def conversation_for_reply(
        self, chat_id: int, replied_message_id: int
    ) -> Conversation | None:
        thread = await self.session.scalar(
            select(TelegramThread).where(
                TelegramThread.chat_id == chat_id, TelegramThread.message_id == replied_message_id
            )
        )
        return await self.session.get(Conversation, thread.conversation_id) if thread else None

    async def link_chat(self, token: str, chat_id: int, title: str) -> Site | None:
        site = await self.session.scalar(select(Site).where(Site.telegram_link_token == token))
        if site is None:
            return None
        site.telegram_chat_id = chat_id
        site.telegram_chat_title = title[:255]
        # One link, one chat: a leaked link can't silently move the inbox somewhere else.
        site.telegram_link_token = secrets.token_urlsafe(12)
        await self.session.commit()
        return site

    async def chat_owns_conversation(self, chat_id: int, conversation_id: uuid.UUID) -> bool:
        thread = await self.session.scalar(
            select(TelegramThread.id).where(
                TelegramThread.chat_id == chat_id,
                TelegramThread.conversation_id == conversation_id,
            )
        )
        return thread is not None
