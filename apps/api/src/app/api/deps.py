from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.container import Container
from app.infra.realtime import EventBus, RateLimiter
from app.services.chat import ChatService
from app.services.gaps import GapService
from app.services.handoff import HandoffService, LeadService
from app.services.indexing import IndexingService
from app.services.retrieval import RetrievalService
from app.services.usage import UsageService


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


ContainerDep = Annotated[Container, Depends(get_container)]


async def get_session(container: ContainerDep) -> AsyncIterator[AsyncSession]:
    async with container.database.session() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_events(container: ContainerDep) -> EventBus:
    return EventBus(container.redis)


def get_rate_limiter(container: ContainerDep) -> RateLimiter:
    return RateLimiter(container.redis)


def get_chat_service(session: SessionDep, container: ContainerDep) -> ChatService:
    settings = container.settings
    return ChatService(
        session,
        RetrievalService(
            session, container.embedder, settings.similarity_floor, settings.similarity_ceiling
        ),
        UsageService(session, settings.daily_token_limit),
        GapService(session),
        container.notifier,
        container.llm,
    )


def get_handoff_service(session: SessionDep, container: ContainerDep) -> HandoffService:
    return HandoffService(session, container.notifier, EventBus(container.redis))


def get_lead_service(session: SessionDep, container: ContainerDep) -> LeadService:
    return LeadService(session, container.notifier, EventBus(container.redis))


def get_indexing_service(session: SessionDep, container: ContainerDep) -> IndexingService:
    return IndexingService(session, container.embedder, container.crawler, container.storage)


EventsDep = Annotated[EventBus, Depends(get_events)]
RateLimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]
ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
HandoffServiceDep = Annotated[HandoffService, Depends(get_handoff_service)]
LeadServiceDep = Annotated[LeadService, Depends(get_lead_service)]
IndexingServiceDep = Annotated[IndexingService, Depends(get_indexing_service)]
