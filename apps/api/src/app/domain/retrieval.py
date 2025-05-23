import re
from dataclasses import dataclass, field

from app.domain.language import detect_language

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


def key_terms(text: str) -> list[str]:
    """Content words cut to a crude stem, so "экрана" still matches "экран"."""
    terms: list[str] = []
    for word in _WORD.findall(text.lower()):
        # Model numbers ("15", "S24") matter even when short.
        if (len(word) < 3 and not word.isdigit()) or word in _STOPWORDS:
            continue
        stem = word if len(word) <= 5 else word[: max(4, len(word) - 2)]
        if stem not in terms:
            terms.append(stem)
    return terms[:12]


def build_tsquery(text: str) -> str | None:
    """OR-query over key terms with prefix matching."""
    return " | ".join(f"{term}:*" for term in key_terms(text)) or None


def term_coverage(query: str, hits: list[Hit]) -> float | None:
    """Share of the question's key terms found in the top passages.

    Embeddings rate "can you fix my washing machine" close to any repair page; the words
    "washing" and "machine" appearing nowhere is what gives it away. Returns None when the
    question and passages are in different languages, where word overlap means nothing.
    """
    terms = key_terms(query)
    top = hits[:3]
    if not terms or not top:
        return None
    if detect_language(query) != detect_language(" ".join(h.text for h in top)):
        return None
    words = set(_WORD.findall(" ".join(h.text for h in top).lower()))
    found = sum(1 for term in terms if any(word.startswith(term) for word in words))
    return found / len(terms)


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


def coverage_factor(coverage: float | None) -> float:
    """1.0 when at least two thirds of the key words are found, 0.3 at one third or less.

    Calibrated on the demo questions: off-topic questions about repairs ("washing machine",
    "DJI drone") share exactly one generic word with the pages, real questions share more.
    """
    if coverage is None:
        return 1.0
    return 0.3 + 0.7 * min(max((coverage - 1 / 3) * 3, 0.0), 1.0)


def confidence(hits: list[Hit], floor: float, ceiling: float, query: str = "") -> float:
    """Best semantic match, scaled down when the passages miss the question's key words."""
    similarities = [h.similarity for h in hits if h.similarity is not None]
    if not similarities:
        return 0.0
    score = calibrate(max(similarities), floor, ceiling)
    if query:
        score *= coverage_factor(term_coverage(query, hits))
    return round(score, 3)
