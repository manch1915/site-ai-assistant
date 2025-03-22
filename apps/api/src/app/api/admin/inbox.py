import uuid
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select

from app.api.admin.deps import SiteDep, UserDep
from app.api.deps import ContainerDep, HandoffServiceDep, IndexingServiceDep, SessionDep
from app.domain.enums import ConversationStatus, GapStatus, LeadStatus, MessageRole
from app.infra.db.models import Conversation, FaqItem, KnowledgeGap, Lead, Message, Site
from app.services.analytics import AnalyticsService
from app.services.usage import UsageService

router = APIRouter(prefix="/v1/admin/sites/{site_id}", tags=["admin: inbox"])


class ConversationRow(BaseModel):
    id: uuid.UUID
    status: ConversationStatus
    language: str
    page_url: str | None
    created_at: datetime
    last_message_at: datetime
    preview: str
    messages: int
    unanswered: int
    rating: int | None
    has_lead: bool


class ConversationPage(BaseModel):
    items: list[ConversationRow]
    total: int


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: MessageRole
    content: str
    author_name: str | None
    sources: list[dict[str, object]]
    confidence: float | None
    answered: bool | None
    flagged: bool
    created_at: datetime


class ConversationDetail(BaseModel):
    id: uuid.UUID
    status: ConversationStatus
    language: str
    page_url: str | None
    rating: int | None
    manager_name: str | None
    created_at: datetime
    messages: list[MessageOut]


class ReplyIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    contact: str
    question: str
    status: LeadStatus
    conversation_id: uuid.UUID | None
    created_at: datetime


class LeadUpdate(BaseModel):
    status: LeadStatus


class GapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question: str
    times_asked: int
    status: GapStatus
    last_asked_at: datetime


class GapAnswer(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    answer: str = Field(min_length=1, max_length=4000)


class DayOut(BaseModel):
    day: date
    conversations: int
    handoffs: int


class GapBrief(BaseModel):
    id: uuid.UUID
    question: str
    times_asked: int


class OverviewOut(BaseModel):
    days: int
    conversations: int
    resolved_confirmed: int
    resolved_assumed: int
    handoffs: int
    leads: int
    unanswered_messages: int
    automation_rate: float
    series: list[DayOut]
    top_gaps: list[GapBrief]
    tokens_this_month: int
    token_budget: int
    llm_enabled: bool


async def owned_conversation(
    conversation_id: uuid.UUID, site: Site, session: SessionDep
) -> Conversation:
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None or conversation.site_id != site.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conversation


@router.get("/conversations")
async def list_conversations(
    site: SiteDep,
    session: SessionDep,
    status_filter: Annotated[ConversationStatus | None, Query(alias="status")] = None,
    needs_attention: bool = False,
    q: Annotated[str | None, Query(max_length=100)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> ConversationPage:
    visitor_count = (
        select(func.count())
        .where(Message.conversation_id == Conversation.id, Message.role == MessageRole.VISITOR)
        .scalar_subquery()
    )
    unanswered = (
        select(func.count())
        .where(Message.conversation_id == Conversation.id, Message.answered.is_(False))
        .scalar_subquery()
    )
    preview = (
        select(Message.content)
        .where(Message.conversation_id == Conversation.id, Message.role == MessageRole.VISITOR)
        .order_by(Message.id)
        .limit(1)
        .scalar_subquery()
    )
    has_lead = select(Lead.id).where(Lead.conversation_id == Conversation.id).exists()

    query = select(Conversation, visitor_count, unanswered, preview, has_lead).where(
        Conversation.site_id == site.id, visitor_count > 0
    )
    if status_filter is not None:
        query = query.where(Conversation.status == status_filter)
    if needs_attention:
        query = query.where(
            or_(
                Conversation.status.in_([ConversationStatus.WAITING, ConversationStatus.HUMAN]),
                unanswered > 0,
            )
        )
    if q:
        matching = select(Message.conversation_id).where(Message.content.ilike(f"%{q}%"))
        query = query.where(Conversation.id.in_(matching))

    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = await session.execute(
        query.order_by(Conversation.last_message_at.desc()).offset(offset).limit(limit)
    )
    items = [
        ConversationRow(
            id=c.id,
            status=c.status,
            language=c.language,
            page_url=c.page_url,
            created_at=c.created_at,
            last_message_at=c.last_message_at,
            preview=(text or "")[:140],
            messages=count,
            unanswered=missed,
            rating=c.rating,
            has_lead=lead,
        )
        for c, count, missed, text, lead in rows
    ]
    return ConversationPage(items=items, total=total)


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: uuid.UUID, site: SiteDep, session: SessionDep
) -> ConversationDetail:
    conversation = await owned_conversation(conversation_id, site, session)
    messages = await session.scalars(
        select(Message).where(Message.conversation_id == conversation.id).order_by(Message.id)
    )
    return ConversationDetail(
        id=conversation.id,
        status=conversation.status,
        language=conversation.language,
        page_url=conversation.page_url,
        rating=conversation.rating,
        manager_name=conversation.manager_name,
        created_at=conversation.created_at,
        messages=[MessageOut.model_validate(m) for m in messages],
    )


@router.post("/conversations/{conversation_id}/reply")
async def reply_to_conversation(
    conversation_id: uuid.UUID,
    body: ReplyIn,
    site: SiteDep,
    user: UserDep,
    session: SessionDep,
    handoff: HandoffServiceDep,
) -> MessageOut:
    conversation = await owned_conversation(conversation_id, site, session)
    message = await handoff.manager_reply(conversation, body.text, user.name)
    return MessageOut.model_validate(message)


@router.post("/conversations/{conversation_id}/close", status_code=status.HTTP_204_NO_CONTENT)
async def close_conversation(
    conversation_id: uuid.UUID, site: SiteDep, session: SessionDep, handoff: HandoffServiceDep
) -> None:
    conversation = await owned_conversation(conversation_id, site, session)
    await handoff.close(conversation)


@router.get("/leads")
async def list_leads(site: SiteDep, session: SessionDep) -> list[LeadOut]:
    rows = await session.scalars(
        select(Lead).where(Lead.site_id == site.id).order_by(Lead.created_at.desc()).limit(200)
    )
    return [LeadOut.model_validate(lead) for lead in rows]


@router.patch("/leads/{lead_id}")
async def update_lead(
    lead_id: uuid.UUID, body: LeadUpdate, site: SiteDep, session: SessionDep
) -> LeadOut:
    lead = await session.get(Lead, lead_id)
    if lead is None or lead.site_id != site.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")
    lead.status = body.status
    await session.commit()
    return LeadOut.model_validate(lead)


@router.get("/gaps")
async def list_gaps(
    site: SiteDep,
    session: SessionDep,
    gap_status: Annotated[GapStatus, Query(alias="status")] = GapStatus.OPEN,
) -> list[GapOut]:
    rows = await session.scalars(
        select(KnowledgeGap)
        .where(KnowledgeGap.site_id == site.id, KnowledgeGap.status == gap_status)
        .order_by(KnowledgeGap.times_asked.desc(), KnowledgeGap.last_asked_at.desc())
        .limit(100)
    )
    return [GapOut.model_validate(g) for g in rows]


async def owned_gap(gap_id: uuid.UUID, site: Site, session: SessionDep) -> KnowledgeGap:
    gap = await session.get(KnowledgeGap, gap_id)
    if gap is None or gap.site_id != site.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gap not found")
    return gap


@router.post("/gaps/{gap_id}/answer")
async def answer_gap(
    gap_id: uuid.UUID,
    body: GapAnswer,
    site: SiteDep,
    session: SessionDep,
    indexing: IndexingServiceDep,
) -> GapOut:
    """Turns an unanswered question into a FAQ entry the bot can use right away."""
    gap = await owned_gap(gap_id, site, session)
    item = FaqItem(site_id=site.id, question=body.question.strip(), answer=body.answer.strip())
    session.add(item)
    await session.flush()
    await indexing.upsert_faq(item)
    gap.status = GapStatus.ANSWERED
    await session.commit()
    return GapOut.model_validate(gap)


@router.post("/gaps/{gap_id}/dismiss")
async def dismiss_gap(gap_id: uuid.UUID, site: SiteDep, session: SessionDep) -> GapOut:
    gap = await owned_gap(gap_id, site, session)
    gap.status = GapStatus.DISMISSED
    await session.commit()
    return GapOut.model_validate(gap)


@router.get("/analytics")
async def analytics(
    site: SiteDep,
    session: SessionDep,
    container: ContainerDep,
    days: Annotated[int, Query(ge=7, le=90)] = 30,
) -> OverviewOut:
    service = AnalyticsService(session, UsageService(session, container.settings.daily_token_limit))
    overview = await service.overview(site, days)
    return OverviewOut(
        days=overview.days,
        conversations=overview.conversations,
        resolved_confirmed=overview.resolved_confirmed,
        resolved_assumed=overview.resolved_assumed,
        handoffs=overview.handoffs,
        leads=overview.leads,
        unanswered_messages=overview.unanswered_messages,
        automation_rate=overview.automation_rate,
        series=[
            DayOut(day=p.day, conversations=p.conversations, handoffs=p.handoffs)
            for p in overview.series
        ],
        top_gaps=[
            GapBrief(id=g.id, question=g.question, times_asked=g.times_asked)
            for g in overview.top_gaps
        ],
        tokens_this_month=overview.tokens_this_month,
        token_budget=overview.token_budget,
        llm_enabled=container.settings.llm_enabled,
    )
