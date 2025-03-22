import os

os.environ.update(
    {
        "ENV": "test",
        "DATABASE_URL": os.environ.get(
            "TEST_DATABASE_URL", "postgresql+asyncpg://relay:relay@127.0.0.1:5441/relay_test"
        ),
        "REDIS_URL": os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:6391/15"),
        "EMBEDDINGS_PROVIDER": "hash",
        "LLM_API_KEY": "",
        "TELEGRAM_BOT_TOKEN": "",
        "SIMILARITY_FLOOR": "0.05",
        "SIMILARITY_CEILING": "0.6",
    }
)

from collections.abc import AsyncIterator

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.infra.db.models import Base
from app.infra.db.session import Database, get_database


async def _ensure_database(url: str) -> None:
    parsed = make_url(url)
    conn = await asyncpg.connect(
        user=parsed.username,
        password=parsed.password,
        host=parsed.host,
        port=parsed.port,
        database="postgres",
    )
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", parsed.database
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{parsed.database}"')
    finally:
        await conn.close()


@pytest.fixture(scope="session")
async def database() -> AsyncIterator[Database]:
    settings = get_settings()
    await _ensure_database(settings.database_url)
    db = get_database()
    async with db.engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield db
    await db.engine.dispose()


@pytest.fixture
async def session(database: Database) -> AsyncIterator[AsyncSession]:
    async with database.session() as s:
        yield s
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    async with database.engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} CASCADE"))
