import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import ConversationStatus, MessageRole
from app.domain.excerpt import best_passage
from app.domain.guard import inspect_message
from app.domain.language import detect_language
from app.domain.prompting import (
    ChatMessage,
    build_messages,
    cited_indexes,
    could_become_no_answer,
    looks_like_no_answer,
    quote_excerpt,
    renumber_citations,
)
from app.domain.replies import reply
from app.domain.retrieval import Hit
from app.infra.db.models import Conversation, Message, Site
from app.infra.llm import ChatModel, Usage
from app.services.gaps import GapService
from app.services.notifications import ManagerNotifier
from app.services.retrieval import Retrieval, RetrievalService
from app.services.usage import UsageService

log = logging.getLogger(__name__)

EventType = Literal["start", "token", "done"]
Mode = Literal["llm", "quote", "no_answer", "human"]

# Short follow-ups ("and for Samsung?") are searched together with the previous question.
FOLLOW_UP_WORDS = 5


@dataclass(slots=True)
class ChatEvent:
    type: EventType
    data: dict[str, Any] = field(default_factory=dict)


class EmptyMessageError(ValueError):
    pass


@dataclass(slots=True)
class _Answer:
    text: str
    mode: Mode
    sources: list[dict[str, Any]]
    usage: Usage | None = None


def source_cards(hits: list[Hit]) -> tuple[list[dict[str, Any]], dict[int, int]]:
    """One chip per document; maps passage numbers (1-based) to chip numbers."""
    cards: list[dict[str, Any]] = []
    by_document: dict[str, int] = {}
    mapping: dict[int, int] = {}
    for index, hit in enumerate(hits, start=1):
        if hit.document_id not in by_document:
            cards.append(
                {"title": hit.title, "url": hit.url, "snippet": quote_excerpt(hit.text, 160)}
            )
            by_document[hit.document_id] = len(cards)
        mapping[index] = by_document[hit.document_id]
    return cards, mapping


def estimate_usage(messages: list[ChatMessage], output: str) -> Usage:
    # About three characters per token: a bit more than real, so the budget errs safe.
    prompt_chars = sum(len(m.content) for m in messages)
    return Usage(tokens_in=prompt_chars // 3 + 1, tokens_out=len(output) // 3 + 1)


class ChatService:
    def __init__(
        self,
        session: AsyncSession,
        retrieval: RetrievalService,
        usage: UsageService,
        gaps: GapService,
        notifier: ManagerNotifier,
        llm: ChatModel | None,
    ) -> None:
        self.session = session
        self.retrieval = retrieval
        self.usage = usage
        self.gaps = gaps
        self.notifier = notifier
        self.llm = llm

    async def handle(
        self, site: Site, conversation: Conversation, raw_text: str
    ) -> AsyncIterator[ChatEvent]:
        guard = inspect_message(raw_text)
        if not guard.text:
            raise EmptyMessageError("Message is empty")

        history = await self._history(conversation)
        conversation.language = detect_language(guard.text, fallback=conversation.language)
        visitor = Message(
            conversation_id=conversation.id,
            role=MessageRole.VISITOR,
            content=guard.text,
            flagged=guard.flagged,
        )
        self.session.add(visitor)
        conversation.last_message_at = datetime.now(UTC)
        await self.session.commit()
        yield ChatEvent("start", {"visitor_message_id": visitor.id})

        if conversation.status in (ConversationStatus.WAITING, ConversationStatus.HUMAN):
            await self.notifier.visitor_message(conversation.id, visitor.id)
            yield ChatEvent("done", {"mode": "human"})
            return
        if conversation.status == ConversationStatus.CLOSED:
            conversation.status = ConversationStatus.BOT

        query = self._search_query(guard.text, history)
        found = await self.retrieval.search(site.id, query)
        answer: _Answer | None = None

        if found.hits and found.confidence >= site.confidence_threshold:
            if self.llm is not None and await self.usage.can_spend(site):
                messages = build_messages(
                    site_name=site.name,
                    instructions=site.instructions,
                    language=conversation.language,
                    question=guard.text,
                    hits=found.hits,
                    history=history,
                    flagged=guard.flagged,
                )
                async for item in self._stream_llm(messages, found.hits):
                    if isinstance(item, ChatEvent):
                        yield item
                    else:
                        answer = item
            else:
                answer = self._quote(site, conversation.language, guard.text, found.hits)
                yield ChatEvent("token", {"text": answer.text})

        if answer is None or answer.mode == "no_answer":
            spent = answer.usage if answer else None
            answer = await self._no_answer(site, conversation, guard.text, found)
            answer.usage = spent
            yield ChatEvent("token", {"text": answer.text})

        bot = Message(
            conversation_id=conversation.id,
            role=MessageRole.BOT,
            content=answer.text,
            sources=answer.sources,
            confidence=found.confidence,
            answered=answer.mode != "no_answer",
            tokens_in=answer.usage.tokens_in if answer.usage else 0,
            tokens_out=answer.usage.tokens_out if answer.usage else 0,
        )
        self.session.add(bot)
        if answer.usage:
            await self.usage.record(site.id, answer.usage.tokens_in, answer.usage.tokens_out)
        conversation.last_message_at = datetime.now(UTC)
        await self.session.commit()

        yield ChatEvent(
            "done",
            {
                "message_id": bot.id,
                "mode": answer.mode,
                "text": answer.text,
                "sources": answer.sources,
                "confidence": found.confidence,
                "actions": ["handoff", "lead"] if answer.mode == "no_answer" else [],
            },
        )

    async def _history(self, conversation: Conversation) -> list[ChatMessage]:
        rows = await self.session.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation.id,
                Message.role.in_([MessageRole.VISITOR, MessageRole.BOT, MessageRole.MANAGER]),
            )
            .order_by(Message.id.desc())
            .limit(6)
        )
        return [
            ChatMessage("user" if m.role == MessageRole.VISITOR else "assistant", m.content)
            for m in reversed(list(rows))
        ]

    @staticmethod
    def _search_query(text: str, history: list[ChatMessage]) -> str:
        if len(text.split()) >= FOLLOW_UP_WORDS:
            return text
        previous = next((m.content for m in reversed(history) if m.role == "user"), None)
        return f"{previous}\n{text}" if previous else text

    async def _stream_llm(
        self, messages: list[ChatMessage], hits: list[Hit]
    ) -> AsyncIterator[ChatEvent | _Answer]:
        assert self.llm is not None
        parts: list[str] = []
        pending = ""
        streaming = False
        silenced = False
        usage: Usage | None = None
        try:
            async for delta in self.llm.stream(messages):
                if delta.usage:
                    usage = delta.usage
                if not delta.text:
                    continue
                parts.append(delta.text)
                # After NO_ANSWER keep reading quietly: the usage chunk comes last.
                if silenced:
                    continue
                if streaming:
                    yield ChatEvent("token", {"text": delta.text})
                    continue
                # Hold the first characters back: the model may be about to say NO_ANSWER.
                pending += delta.text
                if not pending.strip() or could_become_no_answer(pending):
                    continue
                if looks_like_no_answer(pending):
                    silenced = True
                    continue
                streaming = True
                yield ChatEvent("token", {"text": pending})
        except Exception:
            log.exception("LLM call failed")
            if not streaming:
                spent = usage or estimate_usage(messages, "".join(parts))
                yield _Answer(text="", mode="no_answer", sources=[], usage=spent)
                return

        raw = "".join(parts).strip()
        # Providers that omit usage in streams still have to count against the budget.
        usage = usage or estimate_usage(messages, raw)
        if not streaming or looks_like_no_answer(raw):
            yield _Answer(text="", mode="no_answer", sources=[], usage=usage)
            return

        cited = cited_indexes(raw, len(hits))
        used = [hits[i - 1] for i in cited] or hits[:1]
        cards, mapping = source_cards(used)
        mapping = {old: mapping[new] for new, old in enumerate(cited, start=1)} if cited else {}
        yield _Answer(
            text=renumber_citations(raw, mapping),
            mode="llm",
            sources=cards,
            usage=usage,
        )

    def _quote(self, site: Site, language: str, question: str, hits: list[Hit]) -> _Answer:
        top = hits[:3]
        index, lines = best_passage([h.text for h in top], question, [h.title for h in top])
        best = hits[index]
        intro = reply("quote_intro", language, site=site.name)
        lines = lines or [quote_excerpt(best.text)]
        quoted = "\n".join(f"> {quote_excerpt(line, 240)}" for line in lines)
        cards, _ = source_cards([best])
        return _Answer(text=f"{intro}\n\n{quoted} [1]", mode="quote", sources=cards)

    async def _no_answer(
        self, site: Site, conversation: Conversation, question: str, found: Retrieval
    ) -> _Answer:
        await self.gaps.record(site.id, question, found.query_embedding)
        return _Answer(
            text=reply("no_answer", conversation.language, site=site.name),
            mode="no_answer",
            sources=[],
        )
