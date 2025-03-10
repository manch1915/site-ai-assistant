import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.retrieval import Hit, build_tsquery, confidence, fuse
from app.infra.embeddings import Embedder

CANDIDATES = 12
TOP_K = 5

_VECTOR_SQL = text(
    """
    SELECT c.id, c.document_id, d.title, d.url, c.text,
           1 - (c.embedding <=> CAST(:embedding AS vector)) AS similarity
    FROM chunks c JOIN documents d ON d.id = c.document_id
    WHERE c.site_id = :site_id
    ORDER BY c.embedding <=> CAST(:embedding AS vector)
    LIMIT :limit
    """
)

_LEXICAL_SQL = text(
    """
    SELECT c.id, c.document_id, d.title, d.url, c.text,
           ts_rank_cd(c.tsv, to_tsquery('simple', :query)) AS rank
    FROM chunks c JOIN documents d ON d.id = c.document_id
    WHERE c.site_id = :site_id AND c.tsv @@ to_tsquery('simple', :query)
    ORDER BY rank DESC
    LIMIT :limit
    """
)


@dataclass(frozen=True, slots=True)
class Retrieval:
    hits: list[Hit]
    confidence: float
    query_embedding: list[float]


class RetrievalService:
    def __init__(
        self, session: AsyncSession, embedder: Embedder, floor: float, ceiling: float
    ) -> None:
        self.session = session
        self.embedder = embedder
        self.floor = floor
        self.ceiling = ceiling

    async def search(self, site_id: uuid.UUID, query: str) -> Retrieval:
        embedding = await self.embedder.embed_query(query)
        vector_hits = await self._vector(site_id, embedding)
        lexical_hits = await self._lexical(site_id, query)
        hits = fuse(vector_hits, lexical_hits, TOP_K)
        return Retrieval(
            hits=hits,
            confidence=confidence(hits, self.floor, self.ceiling),
            query_embedding=embedding,
        )

    async def _vector(self, site_id: uuid.UUID, embedding: list[float]) -> list[Hit]:
        # Filtering by site after the HNSW scan can starve results; iterative scan fixes that.
        await self.session.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
        rows = await self.session.execute(
            _VECTOR_SQL,
            {"embedding": str(embedding), "site_id": site_id, "limit": CANDIDATES},
        )
        return [
            Hit(
                chunk_id=row.id,
                document_id=str(row.document_id),
                title=row.title,
                url=row.url,
                text=row.text,
                similarity=float(row.similarity),
            )
            for row in rows
        ]

    async def _lexical(self, site_id: uuid.UUID, query: str) -> list[Hit]:
        tsquery = build_tsquery(query)
        if tsquery is None:
            return []
        rows = await self.session.execute(
            _LEXICAL_SQL, {"query": tsquery, "site_id": site_id, "limit": CANDIDATES}
        )
        return [
            Hit(
                chunk_id=row.id,
                document_id=str(row.document_id),
                title=row.title,
                url=row.url,
                text=row.text,
            )
            for row in rows
        ]
