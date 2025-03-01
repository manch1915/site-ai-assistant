from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    secret_key: str = "change-me"
    database_url: str = "postgresql+asyncpg://relay:relay@localhost:5441/relay"
    redis_url: str = "redis://localhost:6391/0"

    public_api_url: str = "http://localhost:8010"
    admin_origin: str = "http://localhost:3010"

    # Any OpenAI-compatible endpoint. Empty key switches answers to quote mode.
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: str = ""
    llm_model: str = "openai/gpt-4.1-mini"
    llm_max_tokens: int = 500
    llm_temperature: float = 0.2

    embeddings_provider: Literal["local", "openai", "hash"] = "local"
    embeddings_model: str = "intfloat/multilingual-e5-small"
    embeddings_base_url: str = ""
    embeddings_api_key: str = ""
    embedding_dim: int = 384
    # Raw cosine scores of e5 sit in a narrow band, so confidence is rescaled between these.
    similarity_floor: float = 0.74
    similarity_ceiling: float = 0.88

    telegram_bot_token: str = ""
    telegram_bot_username: str = ""

    # Global safety net on top of per-site monthly budgets.
    daily_token_limit: int = 400_000
    widget_rate_per_minute: int = 12
    crawl_max_pages: int = 150
    crawl_allow_private: bool = False
    upload_max_bytes: int = 10 * 1024 * 1024
    upload_dir: str = "storage/uploads"

    demo_email: str = "demo@relay.example"
    demo_password: str = Field(default="demo-relay-2026")
    session_ttl_hours: int = 72

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token)


@lru_cache
def get_settings() -> Settings:
    return Settings()
