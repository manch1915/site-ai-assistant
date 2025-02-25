from enum import StrEnum


class SourceKind(StrEnum):
    SITEMAP = "sitemap"
    URL = "url"
    FILE = "file"
    FAQ = "faq"


class SourceStatus(StrEnum):
    QUEUED = "queued"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"


class ConversationStatus(StrEnum):
    BOT = "bot"
    WAITING = "waiting"
    HUMAN = "human"
    CLOSED = "closed"


class MessageRole(StrEnum):
    VISITOR = "visitor"
    BOT = "bot"
    MANAGER = "manager"
    SYSTEM = "system"


class LeadStatus(StrEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class GapStatus(StrEnum):
    OPEN = "open"
    ANSWERED = "answered"
    DISMISSED = "dismissed"
