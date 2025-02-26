import re
from dataclasses import dataclass

_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+(?=[A-ZА-ЯЁ0-9«\"(])")
_BLANK_LINES = re.compile(r"\n\s*\n")
_SPACES = re.compile(r"[ \t ]+")


@dataclass(frozen=True, slots=True)
class ChunkingOptions:
    max_chars: int = 900
    overlap_chars: int = 160
    min_chars: int = 40


def normalize_text(text: str) -> str:
    lines = [_SPACES.sub(" ", line).strip() for line in text.replace("\r\n", "\n").split("\n")]
    joined = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", joined).strip()


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_END.split(text) if s.strip()]


def _blocks(text: str, max_chars: int) -> list[str]:
    """Paragraphs, with oversized ones broken down by sentence and then by hard cut."""
    blocks: list[str] = []
    for raw_paragraph in _BLANK_LINES.split(text):
        paragraph = raw_paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= max_chars:
            blocks.append(paragraph)
            continue
        for sentence in split_sentences(paragraph):
            rest = sentence
            while len(rest) > max_chars:
                cut = rest.rfind(" ", 0, max_chars)
                cut = cut if cut > max_chars // 2 else max_chars
                blocks.append(rest[:cut].strip())
                rest = rest[cut:].strip()
            if rest:
                blocks.append(rest)
    return blocks


def _tail(text: str, limit: int) -> str:
    if limit <= 0:
        return ""
    sentences = split_sentences(text)
    tail: list[str] = []
    size = 0
    for sentence in reversed(sentences):
        if size + len(sentence) > limit:
            break
        tail.insert(0, sentence)
        size += len(sentence) + 1
    return " ".join(tail)


def chunk_text(text: str, options: ChunkingOptions | None = None) -> list[str]:
    opts = options or ChunkingOptions()
    clean = normalize_text(text)
    if not clean:
        return []

    chunks: list[str] = []
    current = ""
    for block in _blocks(clean, opts.max_chars):
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) <= opts.max_chars:
            current = candidate
            continue
        chunks.append(current)
        overlap = _tail(current, opts.overlap_chars)
        current = f"{overlap}\n\n{block}" if overlap else block
        if len(current) > opts.max_chars:
            current = block
    if current:
        chunks.append(current)

    # A tiny trailing piece reads better glued to its neighbour.
    if len(chunks) > 1 and len(chunks[-1]) < opts.min_chars:
        tail = chunks.pop()
        chunks[-1] = f"{chunks[-1]}\n\n{tail}"
    return chunks
