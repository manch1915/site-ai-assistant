import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import ConversationStatus, MessageRole
from app.domain.replies import reply
from app.infra.db.models import Conversation, Lead, Message
from app.infra.realtime import EventBus
from app.services.notifications import ManagerNotifier


def message_payload(message: Message) -> dict[str, object]:
    return {
        "id": message.id,
        "role": message.role.value,
        "content": message.content,
        "author": message.author_name,
        "sources": message.sources,
        "created_at": message.created_at.isoformat(),
    }


class HandoffService:
    def __init__(self, session: AsyncSession, notifier: ManagerNotifier, events: EventBus) -> None:
        self.session = session
        self.notifier = notifier
        self.events = events

    async def _system(self, conversation: Conversation, text: str) -> Message:
        message = Message(conversation_id=conversation.id, role=MessageRole.SYSTEM, content=text)
        self.session.add(message)
        conversation.last_message_at = datetime.now(UTC)
        await self.session.commit()
        await self.events.publish(
            str(conversation.id),
            {"type": "message", "message": message_payload(message), "status": conversation.status},
        )
        return message

    async def request(self, conversation: Conversation, name: str, contact: str) -> Message | None:
        if conversation.status in (ConversationStatus.WAITING, ConversationStatus.HUMAN):
            return None
        # Saved as a lead too: if nobody answers in the chat, the contact is still there.
        question = await self.session.scalar(
            select(Message.content)
            .where(
                Message.conversation_id == conversation.id,
                Message.role == MessageRole.VISITOR,
            )
            .order_by(Message.id.desc())
            .limit(1)
        )
        conversation.visitor_name = name.strip()[:120]
        self.session.add(
            Lead(
                site_id=conversation.site_id,
                conversation_id=conversation.id,
                name=conversation.visitor_name,
                contact=contact,
                question=(question or "")[:2000],
            )
        )
        conversation.status = ConversationStatus.WAITING
        conversation.handoff_requested_at = datetime.now(UTC)
        message = await self._system(conversation, reply("handoff_waiting", conversation.language))
        await self.notifier.handoff_requested(conversation.id)
        return message

    async def manager_reply(self, conversation: Conversation, text: str, author: str) -> Message:
        conversation.status = ConversationStatus.HUMAN
        conversation.manager_name = author
        conversation.handoff_requested_at = conversation.handoff_requested_at or datetime.now(UTC)
        message = Message(
            conversation_id=conversation.id,
            role=MessageRole.MANAGER,
            content=text.strip()[:4000],
            author_name=author,
        )
        self.session.add(message)
        conversation.last_message_at = datetime.now(UTC)
        await self.session.commit()
        await self.events.publish(
            str(conversation.id),
            {"type": "message", "message": message_payload(message), "status": conversation.status},
        )
        return message

    async def close(self, conversation: Conversation) -> None:
        if conversation.status == ConversationStatus.CLOSED:
            return
        conversation.status = ConversationStatus.CLOSED
        await self._system(conversation, reply("closed", conversation.language))


class LeadService:
    def __init__(self, session: AsyncSession, notifier: ManagerNotifier, events: EventBus) -> None:
        self.session = session
        self.notifier = notifier
        self.events = events

    async def create(
        self,
        *,
        site_id: uuid.UUID,
        name: str,
        contact: str,
        question: str,
        conversation: Conversation | None,
    ) -> Lead:
        lead = Lead(
            site_id=site_id,
            conversation_id=conversation.id if conversation else None,
            name=name.strip()[:120],
            contact=contact.strip()[:200],
            question=question.strip()[:2000],
        )
        self.session.add(lead)
        if conversation is not None:
            text = reply("lead_saved", conversation.language, name=lead.name)
            self.session.add(
                Message(conversation_id=conversation.id, role=MessageRole.SYSTEM, content=text)
            )
            conversation.last_message_at = datetime.now(UTC)
        await self.session.commit()
        await self.notifier.lead_created(lead.id)
        return lead
