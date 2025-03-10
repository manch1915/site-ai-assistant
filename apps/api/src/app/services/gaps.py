import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import GapStatus
from app.infra.db.models import KnowledgeGap

# Two questions this close in embedding space are treated as the same gap.
SAME_QUESTION_DISTANCE = 0.12


class GapService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self, site_id: uuid.UUID, question: str, embedding: list[float]
    ) -> KnowledgeGap:
        distance = KnowledgeGap.embedding.cosine_distance(embedding)
        nearest = (
            await self.session.execute(
                select(KnowledgeGap, distance.label("distance"))
                .where(KnowledgeGap.site_id == site_id, KnowledgeGap.status == GapStatus.OPEN)
                .order_by(distance)
                .limit(1)
            )
        ).first()
        if nearest is not None and nearest.distance <= SAME_QUESTION_DISTANCE:
            gap: KnowledgeGap = nearest[0]
            gap.times_asked += 1
            gap.last_asked_at = datetime.now(UTC)
            return gap

        gap = KnowledgeGap(site_id=site_id, question=question[:1000], embedding=embedding)
        self.session.add(gap)
        return gap
