from app.domain.chunking import ChunkingOptions, chunk_text, normalize_text, split_sentences


def test_normalize_collapses_whitespace_and_blank_runs() -> None:
    raw = "Title\r\n\r\n\r\n\r\nFirst   line here  \n\tsecond"
    assert normalize_text(raw) == "Title\n\nFirst line here\nsecond"


def test_split_sentences_handles_russian_and_english() -> None:
    text = "Замена экрана занимает час. Гарантия 6 месяцев! Is it fast? Yes."
    assert split_sentences(text) == [
        "Замена экрана занимает час.",
        "Гарантия 6 месяцев!",
        "Is it fast?",
        "Yes.",
    ]


def test_short_text_is_one_chunk() -> None:
    assert chunk_text("We repair phones and laptops.") == ["We repair phones and laptops."]


def test_empty_text_has_no_chunks() -> None:
    assert chunk_text("   \n\n ") == []


def test_long_text_is_split_within_limit_with_overlap() -> None:
    paragraphs = [f"Paragraph {i}. " + "Sentence about repairs. " * 12 for i in range(6)]
    opts = ChunkingOptions(max_chars=400, overlap_chars=80)
    chunks = chunk_text("\n\n".join(paragraphs), opts)

    assert len(chunks) > 3
    assert all(len(c) <= opts.max_chars for c in chunks)
    # The start of each next chunk repeats the end of the previous one.
    assert chunks[1].split("\n\n")[0] in chunks[0]


def test_oversized_sentence_is_hard_cut() -> None:
    word_soup = "battery " * 300
    chunks = chunk_text(word_soup, ChunkingOptions(max_chars=200, overlap_chars=0))
    assert all(len(c) <= 200 for c in chunks)
    assert "".join(chunks).replace(" ", "").replace("\n", "") == word_soup.replace(" ", "")


def test_tiny_tail_is_merged() -> None:
    text = "A" * 300 + "\n\n" + "Ok."
    chunks = chunk_text(text, ChunkingOptions(max_chars=302, overlap_chars=0, min_chars=10))
    assert len(chunks) == 1
