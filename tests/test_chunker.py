"""Chunker unit tests: pure functions, no PDF needed."""

import pytest

from app.pipeline.ingest.chunker import chunk_text, make_chunks, parse_chapters, word2int
from app.schemas import Chunk


@pytest.mark.parametrize(
    ("word", "expected"),
    [("ONE", 1), ("SEVENTEEN", 17), ("TWENTY", 20), ("TWENTY-EIGHT", 28), ("THIRTY-SEVEN", 37)],
)
def test_word2int(word, expected):
    assert word2int(word) == expected


def test_word2int_rejects_garbage():
    with pytest.raises(ValueError):
        word2int("ELEVENTY")


def _page(i: int, chapter: str, title: str) -> str:
    body = f"Paragraph {i} text. " * 30
    return f"CHAPTER  {chapter}\n{title}\n\n{body}"


def test_parse_chapters_resets_book_on_chapter_one():
    pages = ["front matter with no headings"] + [
        _page(1, "ONE", "THE BOY WHO LIVED"),
        _page(2, "TWO", "THE VANISHING GLASS"),
        "interlude: next book title page",
        _page(3, "ONE", "OLET'S BEGIN"),  # typo'd title still parses as caps line
    ]
    chapters = parse_chapters(pages)
    assert [(c.book_num, c.chapter_num) for c in chapters] == [(1, 1), (1, 2), (2, 1)]
    assert chapters[0].chapter_name == "THE BOY WHO LIVED"
    # interlude page attaches to the previous chapter (documented V1 trade-off)
    assert "interlude" in chapters[1].text


def test_chunk_text_respects_chunk_size_and_keeps_ends():
    text = "\n\n".join(f"Sentence number {i} adds words to the passage." * 2 for i in range(60))
    chunks = chunk_text(text, chunk_size=800, overlap=120, min_size=200)
    assert len(chunks) > 1
    assert all(len(c) <= 800 * 1.5 for c in chunks)
    assert chunks[0].startswith(text[:20])
    assert chunks[-1].endswith(text[-20:])
    # consecutive chunks share the overlap context (asserted against the previous
    # chunk, not the raw text: whitespace normalization + seam spacing make
    # verbatim-in-source impossible by design)
    assert chunks[1][:40] in chunks[0]


def test_make_chunks_produces_valid_chunks():
    pages = [_page(1, "ONE", "THE BOY WHO LIVED")]
    chapter = parse_chapters(pages)[0]
    chunks = make_chunks(chapter, chunk_size=600, overlap=90, min_size=200)
    assert chunks
    assert all(isinstance(c, Chunk) for c in chunks)
    assert all(
        c.metadata.book_num == 1 and c.metadata.chapter_name == "THE BOY WHO LIVED" for c in chunks
    )
    assert [c.id for c in chunks] == [f"b1-c01-{i:04d}" for i in range(len(chunks))]


def test_lowercase_chapter_lines_do_not_start_chapters():
    # The heading match is caps-only: a stray lowercase "chapter one" in
    # story prose cannot silently start or reset book counting.
    pages = ["story text\n\nchapter one\n", _page(1, "ONE", "THE BOY WHO LIVED")]
    chapters = parse_chapters(pages)
    assert [(c.book_num, c.chapter_num) for c in chapters] == [(1, 1)]


def test_parse_chapters_rejects_numbering_gaps():
    # A missed or duplicated heading raises loudly instead of mislabelling
    # every chunk that follows it (contiguity guard).
    pages = [_page(1, "ONE", "A START"), _page(2, "THREE", "A SKIP")]
    with pytest.raises(ValueError, match="not contiguous"):
        parse_chapters(pages)


def test_chunk_text_merges_small_last_chunk():
    # A final chunk below min_size folds into the previous one instead of
    # surviving as a tiny retrieval unit.
    text = "a" * 400 + "\n\n" + "b" * 400 + "\n\nend"
    chunks = chunk_text(text, chunk_size=800, overlap=120, min_size=200)
    assert len(chunks) == 1
    assert all(len(c) >= 200 for c in chunks)
    assert chunks[0].endswith("end")


def test_chunk_text_overlap_seam_length():
    # Pin the exact overlap contract consecutive chunks share: each chunk
    # starts with the previous chunk's 120-char tail minus its first
    # (partial) word. min_size=1 keeps the last-chunk merge out of
    # scope so every consecutive pair is a genuine seam.
    text = "\n\n".join(f"Sentence number {i} adds words to the passage." * 2 for i in range(60))
    chunks = chunk_text(text, chunk_size=800, overlap=120, min_size=1)
    assert len(chunks) > 2
    for a, b in zip(chunks, chunks[1:], strict=False):
        assert b.startswith(a[-120:].split(" ", 1)[1])
