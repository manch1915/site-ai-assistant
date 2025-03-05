import re
from dataclasses import dataclass, field

RRF_K = 60

_WORD = re.compile(r"[\w]+", re.UNICODE)
_STOPWORDS = {
    # en
    "the", "and", "for", "are", "you", "your", "with", "what", "how", "can", "does", "did",
    "have", "has", "this", "that", "from", "about", "there", "which", "when", "where", "who",
    "will", "would", "could", "should", "any", "much", "many", "our", "they", "them", "its",
    "not", "but", "was", "were", "been", "please", "tell",
    # ru
    "как", "что", "это", "для", "или", "есть", "ваш", "ваша", "ваше", "ваши", "вас", "вам",
    "мне", "меня", "можно", "сколько", "какой", "какая", "какие", "когда", "где", "кто",
    "ли", "если", "уже", "так", "там", "тут", "при", "под", "над", "все", "всё", "его",
    "она", "они", "мой", "моя", "мои", "вы", "у", "по", "на", "из", "до", "не", "да", "нет",
    "подскажите", "скажите", "пожалуйста",
}  # fmt: skip


@dataclass(slots=True)
class Hit:
    chunk_id: int
    document_id: str
    title: str
    url: str | None
    text: str
    similarity: float | None = None
    lexical_rank: int | None = None
    vector_rank: int | None = None
    score: float = 0.0
    sources: set[str] = field(default_factory=set)


def build_tsquery(text: str) -> str | None:
    """OR-query with crude prefix stemming, so "экрана" still matches "экран"."""
    terms: list[str] = []
    for word in _WORD.findall(text.lower()):
        if len(word) < 3 or word in _STOPWORDS:
            continue
        stem = word if len(word) <= 4 else word[: max(4, len(word) - 2)]
        term = f"{stem}:*"
        if term not in terms:
            terms.append(term)
    return " | ".join(terms[:12]) or None


def fuse(vector_hits: list[Hit], lexical_hits: list[Hit], limit: int) -> list[Hit]:
    """Reciprocal Rank Fusion of the two result lists."""
    merged: dict[int, Hit] = {}
    for rank, hit in enumerate(vector_hits, start=1):
        hit.vector_rank = rank
        hit.score += 1 / (RRF_K + rank)
        hit.sources.add("vector")
        merged[hit.chunk_id] = hit
    for rank, hit in enumerate(lexical_hits, start=1):
        existing = merged.get(hit.chunk_id)
        target = existing or hit
        target.lexical_rank = rank
        target.score += 1 / (RRF_K + rank)
        target.sources.add("lexical")
        merged[hit.chunk_id] = target
    return sorted(merged.values(), key=lambda h: h.score, reverse=True)[:limit]


def calibrate(similarity: float, floor: float, ceiling: float) -> float:
    if ceiling <= floor:
        return 0.0
    return min(max((similarity - floor) / (ceiling - floor), 0.0), 1.0)


def confidence(hits: list[Hit], floor: float, ceiling: float) -> float:
    """Best semantic match, nudged up when keyword search agrees on a top result."""
    similarities = [h.similarity for h in hits if h.similarity is not None]
    if not similarities:
        return 0.0
    score = calibrate(max(similarities), floor, ceiling)
    if any(len(h.sources) == 2 for h in hits[:3]):
        score += 0.1
    return round(min(score, 1.0), 3)
