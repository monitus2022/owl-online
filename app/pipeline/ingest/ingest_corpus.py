"""Ingestion orchestration: PDF -> pages -> chapters -> validated chunks JSONL.

Used in scripts/ingest_corpus.py and in uv CLI for one-off ingestion runs.
The CLI prints a summary of the run, including chunk counts and sizes.
"""

import collections
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from app.pipeline.ingest.chunker import make_chunks, parse_chapters
from app.schemas import Chunk


# --- Extract pages from PDF into list of strings ---
def extract_pages(pdf: Path, cache: Path) -> list[str]:
    """PDF -> list of page texts, backed by a form-feed separated cache file."""
    if cache.exists():
        return cache.read_text(encoding="utf-8").split("\f")
    doc = pymupdf.open(pdf)
    pages = [page.get_text() for page in doc]
    cache.write_text("\f".join(pages), encoding="utf-8")
    return pages


@dataclass(frozen=True)
class IngestSummary:
    """What one ingestion run produced; the library returns it, the CLI prints it."""

    pages: int
    books: int
    chapters: int
    total_chunks: int
    per_book: dict[int, int]
    min_size: int
    median_size: int
    max_size: int

# --- Ingest step used in scripts/ingest_corpus.py and uv CLI ---
def ingest_corpus(pdf: Path, cache: Path, out: Path) -> IngestSummary:
    """Extract pages, parse chapters, chunk, and write validated JSONL to out."""
    pages = extract_pages(pdf, cache)
    chapters = parse_chapters(pages)
    chunks: list[Chunk] = [c for chapter in chapters for c in make_chunks(chapter)]
    if not chunks:
        # Fail here rather than letting an empty JSONL surface elsewhere.
        raise ValueError("ingestion produced zero chunks — corpus empty or misparsed")

    sizes = sorted(len(c.text) for c in chunks)
    per_book = dict(sorted(collections.Counter(c.metadata.book_num for c in chunks).items()))

    out.write_text("\n".join(c.model_dump_json() for c in chunks) + "\n", encoding="utf-8")

    return IngestSummary(
        pages=len(pages),
        books=max(c.book_num for c in chapters),
        chapters=len(chapters),
        total_chunks=len(chunks),
        per_book=per_book,
        min_size=sizes[0],
        median_size=sizes[len(sizes) // 2],
        max_size=sizes[-1],
    )