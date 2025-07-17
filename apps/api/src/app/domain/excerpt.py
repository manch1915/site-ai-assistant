"""Picks the lines of a passage that answer the question, for replies without a model."""

import re

from app.domain.retrieval import key_terms

_SEPARATOR_ROW = re.compile(r"^\|?\s*:?-{2,}")
_HEADING = re.compile(r"^#{1,6}\s+")
_WORD = re.compile(r"\w+", re.UNICODE)
SHORT_LINE = 32


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
        if not line or line.startswith("|"):
            continue
        lines.extend(s for s in re.split(r"(?<=[.!?])\s+(?=[A-ZА-ЯЁ])", line) if s)
    return lines


def _score(line: str, terms: list[str]) -> int:
    words = _WORD.findall(line.lower())
    return sum(1 for term in terms if any(w.startswith(term) for w in words))


def best_lines(text: str, question: str, limit: int = 3, title: str = "") -> tuple[int, list[str]]:
    """Returns how well the passage matches and the lines worth quoting."""
    # A line repeating the title (a heading, or the question of a FAQ entry) answers nothing.
    candidates = [
        line for line in _sentences(text) if line.strip().lower() != title.strip().lower()
    ]
    if not candidates:
        return 0, []
    terms = key_terms(question)
    scored = [(_score(line, terms), i) for i, line in enumerate(candidates)]
    top = max(score for score, _ in scored)
    if top == 0:
        return 0, candidates[:2]
    # Lines that match as well as the best one, in their original order.
    chosen = [i for score, i in scored if score == top][:limit]
    lines: list[str] = []
    for i in chosen:
        lines.append(candidates[i])
        # A short match is usually a heading ("Opening hours"); the answer is right below it.
        if len(candidates[i]) < SHORT_LINE:
            lines.extend(candidates[i + 1 : i + 3])
    return top, list(dict.fromkeys(lines))[: limit + 2]


def best_passage(
    texts: list[str], question: str, titles: list[str] | None = None
) -> tuple[int, list[str]]:
    """Index of the passage with the best matching lines, and those lines."""
    best_index, best_score, best = 0, -1, list[str]()
    for index, text in enumerate(texts):
        title = titles[index] if titles and index < len(titles) else ""
        score, lines = best_lines(text, question, title=title)
        if score > best_score:
            best_index, best_score, best = index, score, lines
    return best_index, best
