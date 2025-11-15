from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    secret_key: str = "change-me"
    database_url: str = "postgresql+asyncpg://relay:relay@127.0.0.1:5441/relay"
    redis_url: str = "redis://127.0.0.1:6391/0"

    public_api_url: str = "http://localhost:8010"
    admin_origin: str = "http://localhost:3010"

    # Any OpenAI-compatible endpoint. Empty key switches answers to quote mode.
    # The usual OPENAI_* / OPENROUTER_API_KEY names work too.
    llm_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        validation_alias=AliasChoices("LLM_BASE_URL", "OPENAI_BASE_URL"),
    )
    llm_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"),
    )
    llm_model: str = Field(
        default="openai/gpt-4.1-mini", validation_alias=AliasChoices("LLM_MODEL", "OPENAI_MODEL")
    )
    llm_max_tokens: int = 400
    llm_temperature: float = 0.2

    embeddings_provider: Literal["local", "openai", "hash"] = "local"
    embeddings_model: str = "intfloat/multilingual-e5-small"
    # The int8 build of the same model: a quarter of the memory, near-identical vectors.
    # Changing it means running `python -m app.cli reembed`.
    embeddings_model_file: str = "onnx/model_qint8_avx512_vnni.onnx"
    embeddings_base_url: str = ""
    embeddings_api_key: str = ""
    embedding_dim: int = 384
    # Raw cosine scores of e5 sit in a narrow band, so confidence is rescaled between these.
    similarity_floor: float = 0.74
    similarity_ceiling: float = 0.88

    telegram_bot_token: str = ""
    telegram_bot_username: str = ""
    # Off when the bot token is shared with other services: we then only send messages and
    # never read updates, so nothing gets consumed from under them. Managers reply in the admin.
    telegram_receive_updates: bool = True

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

    # Owner account with the narcisbin.com assistant; skipped when empty.
    owner_email: str = ""
    owner_password: str = ""
    owner_site_key: str = ""
    demo_reset_cron: str = "0 */6 * * *"
    # Small installs run the queue worker inside the API process, so the embedding
    # model is loaded once instead of twice.
    run_worker_in_api: bool = False

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token)


@lru_cache
def get_settings() -> Settings:
    return Settings()
