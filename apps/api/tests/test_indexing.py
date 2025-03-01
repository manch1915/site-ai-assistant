from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.domain.enums import SourceKind, SourceStatus
from app.infra.crawler import Crawler
from app.infra.db.models import Chunk, Document, FaqItem
from app.infra.embeddings import HashEmbedder
from app.infra.parsers import RawDocument
from app.infra.storage import FileStorage
from app.services.indexing import IndexingService
from tests.factories import make_site, make_source


def service(session: AsyncSession, tmp_path: object = "storage-test") -> IndexingService:
    return IndexingService(
        session,
        HashEmbedder(get_settings().embedding_dim),
        Crawler(max_pages=5),
        FileStorage(str(tmp_path)),
    )


async def count(session: AsyncSession, model: type) -> int:
    return await session.scalar(select(func.count()).select_from(model)) or 0


async def test_ingest_creates_documents_and_chunks(session: AsyncSession) -> None:
    site = await make_site(session)
    source = await make_source(session, site)
    docs = [
        RawDocument("Prices", "Screen replacement 189 EUR. " * 60, "https://x.test/prices"),
        RawDocument("Hours", "Open Monday to Saturday.", "https://x.test/hours"),
    ]

    await service(session).ingest_documents(source, docs)

    assert source.status == SourceStatus.READY
    assert source.documents_count == 2
    assert source.chunks_count == await count(session, Chunk)
    assert source.chunks_count > 2


async def test_resync_reembeds_only_changed_documents(session: AsyncSession) -> None:
    site = await make_site(session)
    source = await make_source(session, site)
    indexer = service(session)
    await indexer.ingest_documents(
        source,
        [
            RawDocument("A", "Alpha text.", "https://x.test/a"),
            RawDocument("B", "Beta.", "https://x.test/b"),
        ],
    )
    before = {d.url: d.id for d in await session.scalars(select(Document))}

    await indexer.ingest_documents(
        source,
        [
            RawDocument("A", "Alpha text.", "https://x.test/a"),
            RawDocument("B", "Beta v2.", "https://x.test/b"),
        ],
    )
    after = {d.url: d.id for d in await session.scalars(select(Document))}

    assert after["https://x.test/a"] == before["https://x.test/a"]
    assert after["https://x.test/b"] != before["https://x.test/b"]


async def test_resync_drops_pages_that_disappeared(session: AsyncSession) -> None:
    site = await make_site(session)
    source = await make_source(session, site)
    indexer = service(session)
    await indexer.ingest_documents(
        source,
        [
            RawDocument("A", "One.", "https://x.test/a"),
            RawDocument("B", "Two.", "https://x.test/b"),
        ],
    )
    await indexer.ingest_documents(source, [RawDocument("A", "One.", "https://x.test/a")])

    assert source.documents_count == 1
    assert await count(session, Document) == 1


async def test_faq_upsert_replaces_previous_answer(session: AsyncSession) -> None:
    site = await make_site(session)
    indexer = service(session)
    item = FaqItem(site_id=site.id, question="Do you fix MacBooks?", answer="Yes, all models.")
    session.add(item)
    await session.flush()
    await indexer.upsert_faq(item)

    item.answer = "Yes, all models since 2016."
    await indexer.upsert_faq(item)
    await session.commit()

    chunks = list(await session.scalars(select(Chunk.text)))
    assert chunks == ["Do you fix MacBooks?\n\nYes, all models since 2016."]
    faq = await indexer.faq_source(site.id)
    assert faq.kind == SourceKind.FAQ
    assert faq.chunks_count == 1


async def test_failed_source_keeps_error_message(session: AsyncSession) -> None:
    site = await make_site(session)
    source = await make_source(session, site, kind=SourceKind.URL)
    source.url = "http://127.0.0.1:9/never"
    await session.commit()

    await service(session).index_source(source.id)

    await session.refresh(source)
    assert source.status == SourceStatus.FAILED
    assert source.error and "private" in source.error
