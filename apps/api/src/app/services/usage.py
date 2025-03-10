import uuid
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models import Site, UsageDaily


def today() -> date:
    return datetime.now(UTC).date()


class UsageService:
    """Token accounting behind the per-site monthly budget and the global daily cap."""

    def __init__(self, session: AsyncSession, daily_limit: int) -> None:
        self.session = session
        self.daily_limit = daily_limit

    async def record(self, site_id: uuid.UUID, tokens_in: int, tokens_out: int) -> None:
        stmt = insert(UsageDaily).values(
            site_id=site_id, day=today(), requests=1, tokens_in=tokens_in, tokens_out=tokens_out
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[UsageDaily.site_id, UsageDaily.day],
            set_={
                "requests": UsageDaily.requests + 1,
                "tokens_in": UsageDaily.tokens_in + tokens_in,
                "tokens_out": UsageDaily.tokens_out + tokens_out,
            },
        )
        await self.session.execute(stmt)

    async def month_tokens(self, site_id: uuid.UUID) -> int:
        start = today().replace(day=1)
        total = await self.session.scalar(
            select(func.coalesce(func.sum(UsageDaily.tokens_in + UsageDaily.tokens_out), 0)).where(
                UsageDaily.site_id == site_id, UsageDaily.day >= start
            )
        )
        return int(total or 0)

    async def day_tokens(self) -> int:
        total = await self.session.scalar(
            select(func.coalesce(func.sum(UsageDaily.tokens_in + UsageDaily.tokens_out), 0)).where(
                UsageDaily.day == today()
            )
        )
        return int(total or 0)

    async def can_spend(self, site: Site) -> bool:
        if await self.month_tokens(site.id) >= site.monthly_token_budget:
            return False
        return await self.day_tokens() < self.daily_limit
