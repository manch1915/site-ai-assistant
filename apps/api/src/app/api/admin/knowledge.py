import secrets
import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from sqlalchemy import select

from app.api.admin.deps import SiteDep, UserDep, forbid_in_demo
from app.api.deps import ContainerDep, IndexingServiceDep, SessionDep
from app.domain.enums import SourceKind, SourceStatus
from app.domain.widget import WidgetSettings
from app.infra.db.models import FaqItem, Site, Source
from app.infra.parsers import SUPPORTED_EXTENSIONS

router = APIRouter(prefix="/v1/admin", tags=["admin: knowledge"])

DEMO_UPLOAD_LIMIT = 2 * 1024 * 1024


class SiteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    public_key: str
    allowed_domains: list[str]
    widget: WidgetSettings
    instructions: str
    confidence_threshold: float
    monthly_token_budget: int
    telegram_chat_title: str | None
    created_at: datetime


class SiteCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    domain: str = Field(min_length=3, max_length=253)


class SiteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    allowed_domains: list[Annotated[str, Field(max_length=253)]] | None = Field(
        default=None, max_length=20
    )
    widget: WidgetSettings | None = None
    instructions: str | None = Field(default=None, max_length=2000)
    confidence_threshold: float | None = Field(default=None, ge=0, le=1)
    monthly_token_budget: int | None = Field(default=None, ge=0, le=50_000_000)


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: SourceKind
    title: str
    url: str | None
    status: SourceStatus
    error: str | None
    documents_count: int
    chunks_count: int
    indexed_at: datetime | None
    created_at: datetime


class SourceCreate(BaseModel):
    kind: Literal["sitemap", "url"]
    url: HttpUrl


class FaqOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question: str
    answer: str
    updated_at: datetime


class FaqIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    answer: str = Field(min_length=1, max_length=4000)


class TelegramOut(BaseModel):
    enabled: bool
    connected: bool
    chat_title: str | None
    connect_link: str | None


def site_out(site: Site) -> SiteOut:
    return SiteOut.model_validate(
        {**{c: getattr(site, c) for c in SiteOut.model_fields}, "widget": site.widget or {}}
    )


@router.get("/sites/{site_id}")
async def get_site(site: SiteDep) -> SiteOut:
    return site_out(site)


@router.post("/sites", status_code=status.HTTP_201_CREATED)
async def create_site(body: SiteCreate, user: UserDep, session: SessionDep) -> SiteOut:
    forbid_in_demo(user, "Creating sites")
    domain = body.domain.strip().lower().removeprefix("https://").removeprefix("http://")
    site = Site(
        workspace_id=user.workspace_id,
        name=body.name.strip(),
        public_key=f"pk_{secrets.token_urlsafe(12)}",
        telegram_link_token=secrets.token_urlsafe(12),
        allowed_domains=[domain.split("/")[0]],
        widget=WidgetSettings(title=body.name.strip()[:40]).model_dump(),
    )
    session.add(site)
    await session.commit()
    return site_out(site)


@router.patch("/sites/{site_id}")
async def update_site(
    body: SiteUpdate, site: SiteDep, user: UserDep, session: SessionDep
) -> SiteOut:
    # Anyone can open the demo, so it can't change what the public bot says or where it runs.
    locked = {"allowed_domains", "instructions", "monthly_token_budget"}
    if user.is_demo and locked & body.model_fields_set:
        forbid_in_demo(user, "Changing domains, bot instructions or budget")
    changes = body.model_dump(exclude_unset=True, exclude={"widget"})
    for field, value in changes.items():
        setattr(site, field, value)
    if body.widget is not None:
        site.widget = body.widget.model_dump()
    if body.allowed_domains is not None:
        site.allowed_domains = [d.strip().lower() for d in body.allowed_domains if d.strip()]
    await session.commit()
    return site_out(site)


@router.delete("/sites/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_site(site: SiteDep, user: UserDep, session: SessionDep) -> None:
    forbid_in_demo(user, "Deleting sites")
    await session.delete(site)
    await session.commit()


@router.get("/sites/{site_id}/sources")
async def list_sources(site: SiteDep, session: SessionDep) -> list[SourceOut]:
    rows = await session.scalars(
        select(Source).where(Source.site_id == site.id).order_by(Source.created_at.desc())
    )
    return [SourceOut.model_validate(s) for s in rows]


@router.post("/sites/{site_id}/sources", status_code=status.HTTP_201_CREATED)
async def add_source(
    body: SourceCreate,
    site: SiteDep,
    user: UserDep,
    session: SessionDep,
    container: ContainerDep,
) -> SourceOut:
    forbid_in_demo(user, "Crawling external sites")
    url = str(body.url)
    source = Source(
        site_id=site.id,
        kind=SourceKind(body.kind),
        title=url if body.kind == "url" else f"Sitemap · {body.url.host}",
        url=url,
    )
    session.add(source)
    await session.commit()
    await container.queue.enqueue("index_source", source_id=str(source.id), timeout=900)
    return SourceOut.model_validate(source)


@router.post("/sites/{site_id}/sources/upload", status_code=status.HTTP_201_CREATED)
async def upload_source(
    site: SiteDep,
    user: UserDep,
    session: SessionDep,
    container: ContainerDep,
    file: Annotated[UploadFile, File()],
) -> SourceOut:
    filename = file.filename or "document.txt"
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Use PDF, DOCX, TXT, MD or HTML")
    limit = DEMO_UPLOAD_LIMIT if user.is_demo else container.settings.upload_max_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE, f"File is larger than {limit // 1024 // 1024} MB"
        )
    path = container.storage.save(site.id, filename, data)
    source = Source(site_id=site.id, kind=SourceKind.FILE, title=filename[:300], file_path=path)
    session.add(source)
    await session.commit()
    await container.queue.enqueue("index_source", source_id=str(source.id), timeout=600)
    return SourceOut.model_validate(source)


async def owned_source(source_id: uuid.UUID, site: Site, session: SessionDep) -> Source:
    source = await session.get(Source, source_id)
    if source is None or source.site_id != site.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    return source


@router.post("/sites/{site_id}/sources/{source_id}/reindex")
async def reindex_source(
    source_id: uuid.UUID, site: SiteDep, session: SessionDep, container: ContainerDep
) -> SourceOut:
    source = await owned_source(source_id, site, session)
    source.status = SourceStatus.QUEUED
    await session.commit()
    await container.queue.enqueue("index_source", source_id=str(source.id), timeout=900)
    return SourceOut.model_validate(source)


@router.delete("/sites/{site_id}/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: uuid.UUID, site: SiteDep, session: SessionDep, container: ContainerDep
) -> None:
    source = await owned_source(source_id, site, session)
    if source.kind == SourceKind.FAQ:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Edit FAQ entries instead")
    if source.file_path:
        container.storage.delete(source.file_path)
    await session.delete(source)
    await session.commit()


@router.get("/sites/{site_id}/faq")
async def list_faq(site: SiteDep, session: SessionDep) -> list[FaqOut]:
    rows = await session.scalars(
        select(FaqItem).where(FaqItem.site_id == site.id).order_by(FaqItem.updated_at.desc())
    )
    return [FaqOut.model_validate(f) for f in rows]


@router.post("/sites/{site_id}/faq", status_code=status.HTTP_201_CREATED)
async def create_faq(
    body: FaqIn, site: SiteDep, session: SessionDep, indexing: IndexingServiceDep
) -> FaqOut:
    item = FaqItem(site_id=site.id, question=body.question.strip(), answer=body.answer.strip())
    session.add(item)
    await session.flush()
    await indexing.upsert_faq(item)
    await session.commit()
    return FaqOut.model_validate(item)


async def owned_faq(faq_id: uuid.UUID, site: Site, session: SessionDep) -> FaqItem:
    item = await session.get(FaqItem, faq_id)
    if item is None or item.site_id != site.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "FAQ entry not found")
    return item


@router.put("/sites/{site_id}/faq/{faq_id}")
async def update_faq(
    faq_id: uuid.UUID,
    body: FaqIn,
    site: SiteDep,
    session: SessionDep,
    indexing: IndexingServiceDep,
) -> FaqOut:
    item = await owned_faq(faq_id, site, session)
    item.question = body.question.strip()
    item.answer = body.answer.strip()
    await indexing.upsert_faq(item)
    await session.commit()
    await session.refresh(item)
    return FaqOut.model_validate(item)


@router.delete("/sites/{site_id}/faq/{faq_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_faq(
    faq_id: uuid.UUID, site: SiteDep, session: SessionDep, indexing: IndexingServiceDep
) -> None:
    item = await owned_faq(faq_id, site, session)
    await indexing.remove_faq(item)
    await session.commit()


@router.get("/sites/{site_id}/telegram")
async def telegram_status(site: SiteDep, user: UserDep, container: ContainerDep) -> TelegramOut:
    settings = container.settings
    username = settings.telegram_bot_username.lstrip("@")
    link = (
        f"https://t.me/{username}?startgroup={site.telegram_link_token}"
        if settings.telegram_enabled and username and not user.is_demo
        else None
    )
    return TelegramOut(
        enabled=settings.telegram_enabled,
        connected=site.telegram_chat_id is not None,
        chat_title=site.telegram_chat_title,
        connect_link=link,
    )
