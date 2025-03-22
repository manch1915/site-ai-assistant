import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import Date, and_, case, cast, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import GapStatus, MessageRole
from app.infra.db.models import Conversation, KnowledgeGap, Lead, Message, Site
from app.services.usage import UsageService


@dataclass(frozen=True, slots=True)
class DayPoint:
    day: date
    conversations: int
    handoffs: int


@dataclass(frozen=True, slots=True)
class GapRow:
    id: uuid.UUID
    question: str
    times_asked: int
    last_asked_at: datetime


@dataclass(frozen=True, slots=True)
class Overview:
    days: int
    conversations: int
    resolved_confirmed: int
    resolved_assumed: int
    handoffs: int
    leads: int
    unanswered_messages: int
    automation_rate: float
    series: list[DayPoint]
    top_gaps: list[GapRow]
    tokens_this_month: int
    token_budget: int


class AnalyticsService:
    def __init__(self, session: AsyncSession, usage: UsageService) -> None:
        self.session = session
        self.usage = usage

    async def overview(self, site: Site, days: int = 30) -> Overview:
        since = datetime.now(UTC) - timedelta(days=days)
        has_visitor_message = exists().where(
            Message.conversation_id == Conversation.id, Message.role == MessageRole.VISITOR
        )
        has_answer = exists().where(
            Message.conversation_id == Conversation.id,
            Message.role == MessageRole.BOT,
            Message.answered.is_(True),
        )
        has_lead = exists().where(Lead.conversation_id == Conversation.id)
        # A conversation counts as solved by the bot when it got an answer, nobody asked for a
        # human, no contact was left and the visitor didn't vote it down. A thumbs-up confirms it.
        bot_solved = and_(
            has_answer,
            Conversation.handoff_requested_at.is_(None),
            ~has_lead,
            func.coalesce(Conversation.rating, 0) >= 0,
        )
        row = (
            await self.session.execute(
                select(
                    func.count(),
                    func.count().filter(bot_solved, Conversation.rating == 1),
                    func.count().filter(bot_solved, Conversation.rating.is_(None)),
                    func.count().filter(Conversation.handoff_requested_at.is_not(None)),
                ).where(
                    Conversation.site_id == site.id,
                    Conversation.created_at >= since,
                    has_visitor_message,
                )
            )
        ).one()
        total, confirmed, assumed, handoffs = (int(v) for v in row)

        leads = await self.session.scalar(
            select(func.count()).where(Lead.site_id == site.id, Lead.created_at >= since)
        )
        unanswered = await self.session.scalar(
            select(func.count())
            .select_from(Message)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(
                Conversation.site_id == site.id,
                Message.role == MessageRole.BOT,
                Message.answered.is_(False),
                Message.created_at >= since,
            )
        )

        day = cast(Conversation.created_at, Date)
        series_rows = await self.session.execute(
            select(
                day,
                func.count(),
                func.sum(case((Conversation.handoff_requested_at.is_not(None), 1), else_=0)),
            )
            .where(
                Conversation.site_id == site.id,
                Conversation.created_at >= since,
                has_visitor_message,
            )
            .group_by(day)
        )
        by_day = {r[0]: (int(r[1]), int(r[2] or 0)) for r in series_rows}
        start = since.date()
        series = [
            DayPoint(d, *by_day.get(d, (0, 0)))
            for d in (start + timedelta(days=i) for i in range(1, days + 1))
        ]

        gaps = await self.session.scalars(
            select(KnowledgeGap)
            .where(KnowledgeGap.site_id == site.id, KnowledgeGap.status == GapStatus.OPEN)
            .order_by(KnowledgeGap.times_asked.desc(), KnowledgeGap.last_asked_at.desc())
            .limit(5)
        )
        return Overview(
            days=days,
            conversations=total,
            resolved_confirmed=confirmed,
            resolved_assumed=assumed,
            handoffs=handoffs,
            leads=int(leads or 0),
            unanswered_messages=int(unanswered or 0),
            automation_rate=round((confirmed + assumed) / total, 3) if total else 0.0,
            series=series,
            top_gaps=[GapRow(g.id, g.question, g.times_asked, g.last_asked_at) for g in gaps],
            tokens_this_month=await self.usage.month_tokens(site.id),
            token_budget=site.monthly_token_budget,
        )
