"""Picks the lines of a passage that answer the question, for replies without a model."""

import re

from app.domain.retrieval import key_terms

_SEPARATOR_ROW = re.compile(r"^\|?\s*:?-{2,}")
_HEADING = re.compile(r"^#{1,6}\s+")
_WORD = re.compile(r"\w+", re.UNICODE)


def readable_line(line: str) -> str:
    """Markdown table rows become "iPhone 15 screen replacement: about 1 hour, €189"."""
    line = _HEADING.sub("", line.strip())
    if line.startswith("|"):
        cells = [cell.strip() for cell in line.strip("|").split("|") if cell.strip()]
        if not cells:
            return ""
        head, *rest = cells
        return f"{head}: {', '.join(rest)}" if rest else head
    return line


def _sentences(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        if not raw.strip() or _SEPARATOR_ROW.match(raw.strip()):
            continue
        line = readable_line(raw)
        if line.startswith(("|", "-")) or not line:
            continue
        lines.extend(s for s in re.split(r"(?<=[.!?])\s+(?=[A-ZА-ЯЁ])", line) if s)
    return lines


def best_lines(text: str, question: str, limit: int = 3) -> list[str]:
    candidates = _sentences(text)
    if not candidates:
        return []
    terms = key_terms(question)

    def score(line: str) -> int:
        words = _WORD.findall(line.lower())
        return sum(1 for term in terms if any(w.startswith(term) for w in words))

    scored = [(score(line), i, line) for i, line in enumerate(candidates)]
    best = [item for item in sorted(scored, key=lambda x: (-x[0], x[1])) if item[0] > 0][:limit]
    if not best:
        return candidates[:2]
    top = best[0][0]
    # Keep only the lines that match as well as the best one, in their original order.
    chosen = sorted((item for item in best if item[0] == top), key=lambda x: x[1])
    return [line for _, _, line in chosen]
