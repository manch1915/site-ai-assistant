import hashlib
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.chunking import chunk_text
from app.domain.enums import SourceKind, SourceStatus
from app.infra.crawler import Crawler
from app.infra.db.models import Chunk, Document, FaqItem, Source
from app.infra.embeddings import Embedder
from app.infra.parsers import RawDocument, parse_file
from app.infra.storage import FileStorage

log = logging.getLogger(__name__)

FAQ_SOURCE_TITLE = "FAQ"


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def faq_text(question: str, answer: str) -> str:
    return f"{question.strip()}\n\n{answer.strip()}"


class IndexingService:
    def __init__(
        self,
        session: AsyncSession,
        embedder: Embedder,
        crawler: Crawler,
        storage: FileStorage,
    ) -> None:
        self.session = session
        self.embedder = embedder
        self.crawler = crawler
        self.storage = storage

    async def index_source(self, source_id: uuid.UUID) -> None:
        source = await self.session.get(Source, source_id)
        if source is None:
            return
        source.status = SourceStatus.INDEXING
        source.error = None
        await self.session.commit()

        try:
            if source.kind == SourceKind.FAQ:
                await self._rebuild_faq(source)
            else:
                await self._sync_documents(source, self._load(source))
        except Exception as exc:
            log.exception("Indexing failed for source %s", source_id)
            await self.session.rollback()
            source = await self.session.get(Source, source_id)
            if source is None:
                return
            source.status = SourceStatus.FAILED
            source.error = str(exc)[:500]
            await self.session.commit()
            return

        await self._refresh_counts(source)
        source.status = SourceStatus.READY
        source.indexed_at = datetime.now(UTC)
        await self.session.commit()

    async def ingest_documents(self, source: Source, documents: list[RawDocument]) -> None:
        """Index already-loaded documents (used by the seed command)."""

        async def iterate() -> AsyncIterator[RawDocument]:
            for document in documents:
                yield document

        await self._sync_documents(source, iterate())
        await self._refresh_counts(source)
        source.status = SourceStatus.READY
        source.indexed_at = datetime.now(UTC)
        await self.session.commit()

    async def _load(self, source: Source) -> AsyncIterator[RawDocument]:
        if source.kind == SourceKind.SITEMAP:
            assert source.url
            async for document in self.crawler.crawl_sitemap(source.url):
                yield document
        elif source.kind == SourceKind.URL:
            assert source.url
            yield await self.crawler.fetch_page(source.url)
        elif source.kind == SourceKind.FILE:
            assert source.file_path
            raw = parse_file(source.title, self.storage.read(source.file_path))
            yield RawDocument(title=source.title, text=raw.text)

    async def _rebuild_faq(self, source: Source) -> None:
        await self.session.execute(delete(Document).where(Document.source_id == source.id))
        items = await self.session.scalars(select(FaqItem).where(FaqItem.site_id == source.site_id))
        for item in items:
            text = faq_text(item.question, item.answer)
            raw = RawDocument(title=item.question, text=text)
            await self._store(source, raw, content_hash(text), faq_item_id=item.id)
        await self.session.flush()

    async def _sync_documents(self, source: Source, documents: AsyncIterator[RawDocument]) -> None:
        """Re-embeds only documents whose text changed and drops the ones that disappeared."""
        existing = {
            (doc.url or doc.title): doc
            for doc in await self.session.scalars(
                select(Document).where(Document.source_id == source.id)
            )
        }
        seen: set[str] = set()
        async for raw in documents:
            key = raw.url or raw.title
            if key in seen or not raw.text.strip():
                continue
            seen.add(key)
            digest = content_hash(raw.text)
            current = existing.get(key)
            if current is not None and current.content_hash == digest:
                continue
            if current is not None:
                await self.session.delete(current)
            await self._store(source, raw, digest)
            await self.session.flush()

        for key, document in existing.items():
            if key not in seen:
                await self.session.delete(document)
        await self.session.flush()

    async def _store(
        self,
        source: Source,
        raw: RawDocument,
        digest: str,
        faq_item_id: uuid.UUID | None = None,
    ) -> Document:
        pieces = chunk_text(raw.text)
        vectors = await self.embedder.embed_passages([f"{raw.title}\n{p}" for p in pieces])
        document = Document(
            site_id=source.site_id,
            source_id=source.id,
            faq_item_id=faq_item_id,
            title=raw.title[:500],
            url=raw.url,
            content_hash=digest,
        )
        document.chunks = [
            Chunk(site_id=source.site_id, ordinal=i, text=piece, embedding=vector)
            for i, (piece, vector) in enumerate(zip(pieces, vectors, strict=True))
        ]
        self.session.add(document)
        return document

    async def _refresh_counts(self, source: Source) -> None:
        source.documents_count = (
            await self.session.scalar(
                select(func.count()).select_from(Document).where(Document.source_id == source.id)
            )
            or 0
        )
        source.chunks_count = (
            await self.session.scalar(
                select(func.count())
                .select_from(Chunk)
                .join(Document, Chunk.document_id == Document.id)
                .where(Document.source_id == source.id)
            )
            or 0
        )

    async def faq_source(self, site_id: uuid.UUID) -> Source:
        source = await self.session.scalar(
            select(Source).where(Source.site_id == site_id, Source.kind == SourceKind.FAQ)
        )
        if source is None:
            source = Source(
                site_id=site_id,
                kind=SourceKind.FAQ,
                title=FAQ_SOURCE_TITLE,
                status=SourceStatus.READY,
            )
            self.session.add(source)
            await self.session.flush()
        return source

    async def upsert_faq(self, item: FaqItem) -> None:
        source = await self.faq_source(item.site_id)
        await self.session.execute(delete(Document).where(Document.faq_item_id == item.id))
        text = faq_text(item.question, item.answer)
        raw = RawDocument(title=item.question, text=text)
        await self._store(source, raw, content_hash(text), faq_item_id=item.id)
        await self.session.flush()
        await self._refresh_counts(source)
        source.indexed_at = datetime.now(UTC)

    async def remove_faq(self, item: FaqItem) -> None:
        source = await self.faq_source(item.site_id)
        await self.session.delete(item)
        await self.session.flush()
        await self._refresh_counts(source)
