from dataclasses import dataclass
from functools import cached_property, lru_cache

from redis.asyncio import Redis
from saq import Queue

from app.config import Settings, get_settings
from app.infra.crawler import Crawler
from app.infra.db.session import Database, get_database
from app.infra.embeddings import Embedder, build_embedder
from app.infra.llm import ChatModel, build_chat_model
from app.infra.storage import FileStorage
from app.services.notifications import ManagerNotifier, QueueNotifier


@dataclass
class Container:
    """Process-wide singletons. Tests build their own instance with fakes."""

    settings: Settings
    database: Database

    @cached_property
    def redis(self) -> Redis:
        return Redis.from_url(self.settings.redis_url, decode_responses=True)

    @cached_property
    def queue(self) -> Queue:
        return Queue.from_url(self.settings.redis_url, name="relay")

    @cached_property
    def embedder(self) -> Embedder:
        return build_embedder(self.settings)

    @cached_property
    def crawler(self) -> Crawler:
        return Crawler(
            max_pages=self.settings.crawl_max_pages,
            allow_private=self.settings.crawl_allow_private,
        )

    @cached_property
    def storage(self) -> FileStorage:
        return FileStorage(self.settings.upload_dir)

    @cached_property
    def llm(self) -> ChatModel | None:
        return build_chat_model(self.settings)

    @cached_property
    def notifier(self) -> ManagerNotifier:
        return QueueNotifier(self.queue)


@lru_cache
def get_container() -> Container:
    return Container(settings=get_settings(), database=get_database())
