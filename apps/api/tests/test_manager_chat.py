from dataclasses import dataclass, field

from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import MessageRole
from app.infra.db.models import Conversation, Lead, Message
from app.services.manager_chat import ManagerChat
from tests.factories import make_site

CHAT_ID = -1001234567890


@dataclass
class Sent:
    message_id: int


@dataclass
class FakeSender:
    sent: list[dict[str, object]] = field(default_factory=list)

    async def send_message(
        self,
        chat_id: int,
        text: str,
        *,
        reply_to_message_id: int | None = None,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> Sent:
        self.sent.append({"chat_id": chat_id, "text": text, "reply_to": reply_to_message_id})
        return Sent(message_id=100 + len(self.sent))


async def conversation_with_history(session: AsyncSession) -> Conversation:
    site = await make_site(session, telegram_chat_id=CHAT_ID)
    conversation = Conversation(
        site_id=site.id, visitor_token_hash="x" * 64, page_url="https://ohmsolder.test/prices"
    )
    session.add(conversation)
    await session.flush()
    session.add_all(
        [
            Message(conversation_id=conversation.id, role=MessageRole.VISITOR, content="<b>Hi</b>"),
            Message(conversation_id=conversation.id, role=MessageRole.BOT, content="Hello!"),
        ]
    )
    await session.commit()
    return conversation


async def test_handoff_posts_escaped_transcript_and_remembers_thread(session: AsyncSession) -> None:
    conversation = await conversation_with_history(session)
    sender = FakeSender()
    chat = ManagerChat(session, sender)

    assert await chat.announce_handoff(conversation.id)

    text = str(sender.sent[0]["text"])
    assert "&lt;b&gt;Hi&lt;/b&gt;" in text
    assert "Page: https://ohmsolder.test/prices" in text
    found = await chat.conversation_for_reply(CHAT_ID, 101)
    assert found is not None and found.id == conversation.id


async def test_visitor_follow_up_is_threaded_under_last_message(session: AsyncSession) -> None:
    conversation = await conversation_with_history(session)
    sender = FakeSender()
    chat = ManagerChat(session, sender)
    await chat.announce_handoff(conversation.id)
    follow_up = Message(
        conversation_id=conversation.id, role=MessageRole.VISITOR, content="Still there?"
    )
    session.add(follow_up)
    await session.commit()

    await chat.forward_visitor_message(conversation.id, follow_up.id)

    assert sender.sent[1]["reply_to"] == 101


async def test_lead_announcement_and_unlinked_sites(session: AsyncSession) -> None:
    conversation = await conversation_with_history(session)
    lead = Lead(site_id=conversation.site_id, name="Anna", contact="+374 91 000000", question="")
    session.add(lead)
    unlinked = await make_site(session)
    other = Lead(site_id=unlinked.id, name="Bob", contact="bob@example.com")
    session.add(other)
    await session.commit()
    sender = FakeSender()
    chat = ManagerChat(session, sender)

    assert await chat.announce_lead(lead.id)
    assert not await chat.announce_lead(other.id)
    assert len(sender.sent) == 1


async def test_link_chat_by_token(session: AsyncSession) -> None:
    site = await make_site(session)
    await session.commit()
    chat = ManagerChat(session, FakeSender())

    linked = await chat.link_chat(site.telegram_link_token, CHAT_ID, "Ohm & Solder managers")

    assert linked is not None and linked.telegram_chat_id == CHAT_ID
    assert await chat.link_chat("wrong", CHAT_ID, "x") is None
