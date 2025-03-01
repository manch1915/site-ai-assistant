import logging
import uuid
from typing import Any

from app.container import get_container
from app.services.indexing import IndexingService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

Context = dict[str, Any]


async def index_source(_: Context, *, source_id: str) -> None:
    container = get_container()
    async with container.database.session() as session:
        service = IndexingService(session, container.embedder, container.crawler, container.storage)
        await service.index_source(uuid.UUID(source_id))


settings = {
    "queue": get_container().queue,
    "functions": [index_source],
    "concurrency": 4,
}
