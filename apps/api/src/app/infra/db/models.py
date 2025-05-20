import uuid
from datetime import UTC, date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Computed,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.config import get_settings
from app.domain.enums import (
    ConversationStatus,
    GapStatus,
    LeadStatus,
    MessageRole,
    SourceKind,
    SourceStatus,
)

EMBEDDING_DIM = get_settings().embedding_dim


def utcnow() -> datetime:
    return datetime.now(UTC)


def _enum(cls: type, name: str) -> Enum:
    return Enum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class Base(DeclarativeBase):
    type_annotation_map = {  # noqa: RUF012
        datetime: DateTime(timezone=True),
        dict[str, Any]: JSONB,
        list[dict[str, Any]]: JSONB,
    }


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    public_key: Mapped[str] = mapped_column(String(40), unique=True)
    allowed_domains: Mapped[list[str]] = mapped_column(ARRAY(String(253)), default=list)
    widget: Mapped[dict[str, Any]] = mapped_column(default=dict)
    instructions: Mapped[str] = mapped_column(Text, default="")
    confidence_threshold: Mapped[float] = mapped_column(Float, default=0.35)
    monthly_token_budget: Mapped[int] = mapped_column(Integer, default=300_000)
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    telegram_chat_title: Mapped[str | None] = mapped_column(String(255))
    telegram_link_token: Mapped[str] = mapped_column(String(40), unique=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[SourceKind] = mapped_column(_enum(SourceKind, "source_kind"))
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str | None] = mapped_column(String(2048))
    file_path: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[SourceStatus] = mapped_column(
        _enum(SourceStatus, "source_status"), default=SourceStatus.QUEUED
    )
    error: Mapped[str | None] = mapped_column(Text)
    documents_count: Mapped[int] = mapped_column(Integer, default=0)
    chunks_count: Mapped[int] = mapped_column(Integer, default=0)
    indexed_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class FaqItem(Base):
    __tablename__ = "faq_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), index=True
    )
    question: Mapped[str] = mapped_column(String(500))
    answer: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    faq_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("faq_items.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str | None] = mapped_column(String(2048))
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        Index(
            "ix_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    tsv: Mapped[str] = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple', text)", persisted=True)
    )

    document: Mapped[Document] = relationship(back_populates="chunks")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), index=True
    )
    visitor_token_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[ConversationStatus] = mapped_column(
        _enum(ConversationStatus, "conversation_status"), default=ConversationStatus.BOT
    )
    language: Mapped[str] = mapped_column(String(8), default="en")
    page_url: Mapped[str | None] = mapped_column(String(2048))
    visitor_name: Mapped[str | None] = mapped_column(String(120))
    rating: Mapped[int | None] = mapped_column(Integer)
    handoff_requested_at: Mapped[datetime | None]
    manager_name: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    last_message_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Message.id",
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[MessageRole] = mapped_column(_enum(MessageRole, "message_role"))
    content: Mapped[str] = mapped_column(Text)
    author_name: Mapped[str | None] = mapped_column(String(120))
    sources: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    confidence: Mapped[float | None] = mapped_column(Float)
    answered: Mapped[bool | None] = mapped_column(Boolean)
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(120))
    contact: Mapped[str] = mapped_column(String(200))
    question: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[LeadStatus] = mapped_column(
        _enum(LeadStatus, "lead_status"), default=LeadStatus.NEW
    )
    # Seeded demo leads. Contacts of real ones are masked for the shared demo account.
    sample: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)


class KnowledgeGap(Base):
    __tablename__ = "knowledge_gaps"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), index=True
    )
    question: Mapped[str] = mapped_column(String(1000))
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    times_asked: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[GapStatus] = mapped_column(
        _enum(GapStatus, "gap_status"), default=GapStatus.OPEN
    )
    last_asked_at: Mapped[datetime] = mapped_column(default=utcnow)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class TelegramThread(Base):
    """Maps a bot message in a manager chat to the conversation it belongs to."""

    __tablename__ = "telegram_threads"
    __table_args__ = (UniqueConstraint("chat_id", "message_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int] = mapped_column(BigInteger)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )


class UsageDaily(Base):
    __tablename__ = "usage_daily"

    site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    requests: Mapped[int] = mapped_column(Integer, default=0)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
