import hashlib
import hmac
import secrets
import uuid
from collections.abc import AsyncIterable
from dataclasses import dataclass
from typing import Annotated, Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.api.deps import (
    ChatServiceDep,
    ContainerDep,
    EventsDep,
    HandoffServiceDep,
    LeadServiceDep,
    RateLimiterDep,
    SessionDep,
)
from app.domain.enums import ConversationStatus
from app.domain.widget import WidgetSettings, origin_allowed
from app.infra.db.models import Conversation, Message, Site
from app.services.chat import EmptyMessageError
from app.services.handoff import message_payload

router = APIRouter(prefix="/v1/widget", tags=["widget"])


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def check_origin(request: Request, site: Site, container: ContainerDep) -> None:
    # Pages served by the API itself (the demo shop) are always allowed.
    always = [
        container.settings.admin_origin,
        container.settings.public_api_url,
        str(request.base_url),
    ]
    if not origin_allowed(request.headers.get("origin"), site.allowed_domains, always):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This site is not allowed to use the widget")


async def get_site(
    key: str, request: Request, session: SessionDep, container: ContainerDep
) -> Site:
    site = await session.scalar(select(Site).where(Site.public_key == key))
    if site is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown widget key")
    check_origin(request, site, container)
    return site


SiteDep = Annotated[Site, Depends(get_site)]


@dataclass
class VisitorContext:
    site: Site
    conversation: Conversation


async def get_visitor(
    conversation_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    container: ContainerDep,
    x_visitor_token: Annotated[str, Header()],
) -> VisitorContext:
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None or not hmac.compare_digest(
        conversation.visitor_token_hash, hash_token(x_visitor_token)
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    site = await session.get(Site, conversation.site_id)
    assert site is not None
    check_origin(request, site, container)
    return VisitorContext(site=site, conversation=conversation)


VisitorDep = Annotated[VisitorContext, Depends(get_visitor)]


class WidgetConfigOut(BaseModel):
    site_name: str
    settings: WidgetSettings
    handoff_available: bool


class ConversationIn(BaseModel):
    page_url: str | None = Field(default=None, max_length=2048)
    language: str | None = Field(default=None, max_length=8)

    @field_validator("page_url")
    @classmethod
    def http_only(cls, value: str | None) -> str | None:
        # The admin shows this link to managers, so anything but http(s) is dropped.
        if value and urlparse(value).scheme in {"http", "https"}:
            return value
        return None


class ConversationOut(BaseModel):
    id: uuid.UUID
    token: str


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    author: str | None
    sources: list[dict[str, object]]
    created_at: str


class TranscriptOut(BaseModel):
    status: ConversationStatus
    messages: list[MessageOut]


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class RatingIn(BaseModel):
    value: Literal[-1, 1]


class LeadIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    contact: str = Field(min_length=3, max_length=200)
    question: str = Field(default="", max_length=2000)
    conversation_id: uuid.UUID | None = None


class Ok(BaseModel):
    ok: bool = True


@router.get("/{key}/config")
async def widget_config(site: SiteDep) -> WidgetConfigOut:
    settings = WidgetSettings.model_validate(site.widget)
    # Without Telegram the request still lands in the admin inbox, so handoff only depends
    # on the owner's switch.
    return WidgetConfigOut(
        site_name=site.name, settings=settings, handoff_available=settings.handoff_enabled
    )


@router.post("/{key}/conversations", status_code=status.HTTP_201_CREATED)
async def start_conversation(
    body: ConversationIn,
    site: SiteDep,
    session: SessionDep,
    request: Request,
    limiter: RateLimiterDep,
) -> ConversationOut:
    if not await limiter.allow(f"conv:{client_ip(request)}", limit=10):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many new conversations")
    token = secrets.token_urlsafe(32)
    settings = WidgetSettings.model_validate(site.widget)
    language = settings.language if settings.language != "auto" else (body.language or "en")[:2]
    conversation = Conversation(
        site_id=site.id,
        visitor_token_hash=hash_token(token),
        page_url=body.page_url,
        language=language if language in {"en", "ru"} else "en",
    )
    session.add(conversation)
    await session.commit()
    return ConversationOut(id=conversation.id, token=token)


@router.get("/conversations/{conversation_id}/messages")
async def transcript(visitor: VisitorDep, session: SessionDep) -> TranscriptOut:
    rows = await session.scalars(
        select(Message)
        .where(Message.conversation_id == visitor.conversation.id)
        .order_by(Message.id)
        .limit(200)
    )
    return TranscriptOut(
        status=visitor.conversation.status,
        messages=[MessageOut.model_validate(message_payload(m)) for m in rows],
    )


@router.post("/conversations/{conversation_id}/messages", response_class=EventSourceResponse)
async def send_message(
    body: MessageIn,
    visitor: VisitorDep,
    chat: ChatServiceDep,
    limiter: RateLimiterDep,
    container: ContainerDep,
    request: Request,
) -> AsyncIterable[ServerSentEvent]:
    limit = container.settings.widget_rate_per_minute
    key = f"msg:{visitor.site.id}:{client_ip(request)}"
    if not await limiter.allow(key, limit=limit):
        yield ServerSentEvent(event="error", data={"code": "rate_limited"})
        return
    try:
        async for event in chat.handle(visitor.site, visitor.conversation, body.text):
            yield ServerSentEvent(event=event.type, data=event.data)
    except EmptyMessageError:
        yield ServerSentEvent(event="error", data={"code": "empty"})


@router.get("/conversations/{conversation_id}/events", response_class=EventSourceResponse)
async def conversation_events(
    visitor: VisitorDep, events: EventsDep
) -> AsyncIterable[ServerSentEvent]:
    """Manager replies and status changes, pushed while the widget is open."""
    async for event in events.listen(str(visitor.conversation.id)):
        if event is None:
            yield ServerSentEvent(comment="ping")
        else:
            yield ServerSentEvent(event=event.get("type", "message"), data=event)


@router.post("/conversations/{conversation_id}/handoff")
async def request_handoff(visitor: VisitorDep, handoff: HandoffServiceDep) -> TranscriptOut:
    message = await handoff.request(visitor.conversation)
    messages = [MessageOut.model_validate(message_payload(message))] if message else []
    return TranscriptOut(status=visitor.conversation.status, messages=messages)


@router.post("/conversations/{conversation_id}/rating")
async def rate(body: RatingIn, visitor: VisitorDep, session: SessionDep) -> Ok:
    visitor.conversation.rating = body.value
    await session.commit()
    return Ok()


@router.post("/{key}/leads", status_code=status.HTTP_201_CREATED)
async def create_lead(
    body: LeadIn,
    site: SiteDep,
    session: SessionDep,
    leads: LeadServiceDep,
    limiter: RateLimiterDep,
    request: Request,
    x_visitor_token: Annotated[str | None, Header()] = None,
) -> Ok:
    if not await limiter.allow(f"lead:{client_ip(request)}", limit=5):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests")
    conversation = None
    if body.conversation_id and x_visitor_token:
        candidate = await session.get(Conversation, body.conversation_id)
        if (
            candidate
            and candidate.site_id == site.id
            and hmac.compare_digest(candidate.visitor_token_hash, hash_token(x_visitor_token))
        ):
            conversation = candidate
    await leads.create(
        site_id=site.id,
        name=body.name,
        contact=body.contact,
        question=body.question,
        conversation=conversation,
    )
    return Ok()
