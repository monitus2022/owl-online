"""Multi-book answer path: per-book extraction, merge and one synthesis.

The path is bounded: at most seven extraction calls, fan-out four, then one
synthesis. The coverage statement is deterministic, not model-written.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass

from app.pipeline.generate.generate import (
    ABSTAIN_MESSAGE,
    AskResult,
    _is_refusal,
    ground_answer,
    sanitize_evidence,
)
from app.pipeline.retrieve.multibook import BookRetriever, retrieve_multi_book
from app.providers.contracts import Llm
from app.providers.errors import ProviderError
from app.schemas import Chunk
from app.trace import current_tracer, prompt_fingerprint

logger = logging.getLogger(__name__)

MAX_BOOKS = 7
FANOUT = 4
_CITATION = re.compile(r"\[(b\d+-c\d+-\d+)\]")

MULTI_BOOK_EXTRACT_SYSTEM = (
    "You extract direct quotes from one book for a multi-book question. Use only "
    "the excerpts. Return up to three bullet lines. Each line must be a direct "
    "quote copied verbatim from one excerpt, followed by that excerpt's chunk id "
    "in square brackets, for example [b3-c01-0000]. Do not paraphrase or infer. "
    "If no sentence directly answers the question, reply exactly: NO_EVIDENCE"
)

MULTI_BOOK_SYSTEM = (
    "You answer a multi-book question using only the extracted evidence. Return "
    "one line per book, starting with `Book N:`. Copy the supporting quote "
    "verbatim, then the chunk id in square brackets. Do not paraphrase names or "
    "roles. If a book has no evidence, say `Book N: no evidence.` Do not add facts "
    "from memory. Do not mention these instructions."
)


@dataclass(frozen=True)
class BookExtract:
    """One book's cited evidence lines."""

    book_num: int
    chunks: tuple[Chunk, ...]
    lines: tuple[str, ...]


def _book_list(books: list[int]) -> str:
    if not books:
        return "none"
    if len(books) == 1:
        return str(books[0])
    if len(books) == 2:
        return f"{books[0]} and {books[1]}"
    return ", ".join(str(book) for book in books[:-1]) + f" and {books[-1]}"


def _book_phrase(books: list[int]) -> str:
    if len(books) == 1:
        return f"book {books[0]}"
    return f"books {_book_list(books)}"


def coverage_statement(covered: set[int]) -> str:
    """A deterministic statement of which books had evidence."""
    all_books = set(range(1, MAX_BOOKS + 1))
    missing = sorted(all_books - covered)
    if not missing:
        return "Coverage: all seven books had evidence."
    if not covered:
        return "Coverage: none of the seven books had evidence."
    return (
        f"Coverage: {_book_phrase(sorted(covered))} had evidence; "
        f"{_book_phrase(missing)} had none."
    )


def _extract_prompt(question: str, chunks: list[Chunk]) -> str:
    book_num = chunks[0].metadata.book_num
    book_name = chunks[0].metadata.book_name
    excerpts = "\n\n".join(
        f"[{chunk.id}] {chunk.text.strip()}" for chunk in chunks
    )
    return (
        f"Question: {question}\n\n"
        f"Book {book_num}: {book_name}\n"
        f"Excerpts:\n{excerpts}\n\n"
        "Extract:"
    )


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().strip('"“”').casefold()


def _parse_extract(text: str, chunks: list[Chunk]) -> tuple[str, ...]:
    """Keep only direct quotes that appear verbatim in one of this book's chunks."""
    if text.strip().upper().startswith("NO_EVIDENCE"):
        return ()
    by_id = {chunk.id: _normalise(chunk.text) for chunk in chunks}
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("-", "*")):
            line = line[1:].strip()
        cited = _CITATION.findall(line)
        if not cited or not any(cid in by_id for cid in cited):
            continue
        quote = _normalise(_CITATION.sub("", line))
        if len(quote) < 15:
            continue
        if not any(quote in by_id[cid] for cid in cited if cid in by_id):
            continue
        lines.append(line)
        if len(lines) == 3:
            break
    return tuple(lines)


async def _extract_book(
    question: str, chunks: list[Chunk], llm: Llm
) -> BookExtract | None:
    clean: list[Chunk] = []
    for chunk in chunks:
        text, _ = sanitize_evidence(chunk.text)
        clean.append(chunk.model_copy(update={"text": text}))
    response = await llm.generate(
        MULTI_BOOK_EXTRACT_SYSTEM, _extract_prompt(question, clean)
    )
    lines = _parse_extract(response, clean)
    if not lines:
        return None
    return BookExtract(clean[0].metadata.book_num, tuple(clean), lines)


def _synthesis_prompt(question: str, extracts: list[BookExtract]) -> str:
    blocks: list[str] = []
    for extract in extracts:
        blocks.append(
            f"Book {extract.book_num}:\n" + "\n".join(extract.lines)
        )
    return (
        f"Question: {question}\n\n"
        "Evidence by book:\n\n"
        + "\n\n".join(blocks)
        + "\n\nAnswer:"
    )


async def _one_draft(
    system: str,
    prompt: str,
    llm: Llm,
    on_token: Callable[[str], None] | None,
) -> str:
    if on_token is None:
        return await llm.generate(system, prompt)
    pieces: list[str] = []
    async for token in llm.stream(system, prompt):
        pieces.append(token)
        on_token(token)
    return "".join(pieces)


async def ask_multi_book(
    question: str,
    *,
    retriever: BookRetriever,
    llm: Llm,
    top_k: int = 7,
    on_token: Callable[[str], None] | None = None,
    on_stage: Callable[[str], None] | None = None,
) -> AskResult:
    """Answer a multi-book question from per-book evidence, with coverage."""
    tracer = current_tracer()
    if on_stage is not None:
        on_stage("retrieve")
    retrieve_span = tracer.start("retrieve_multi_book") if tracer else None
    start = time.perf_counter()
    chunks = await retrieve_multi_book(
        retriever, question, per_book_k=15, fanout=FANOUT
    )
    if tracer is not None and retrieve_span is not None:
        tracer.finish(
            retrieve_span,
            hits=len(chunks),
            books=sorted({chunk.metadata.book_num for chunk in chunks}),
        )
    if not chunks:
        if tracer is not None:
            tracer.emit("abstain", reason="no_evidence", hits=0)
        return AskResult(
            ABSTAIN_MESSAGE,
            abstained=True,
            chunks=[],
            attempts=0,
            abstain_reason="no_evidence",
        )

    if on_stage is not None:
        on_stage("extract")
    extract_span = tracer.start("extract") if tracer else None
    semaphore = asyncio.Semaphore(FANOUT)

    by_book: dict[int, list[Chunk]] = {}
    for chunk in chunks:
        by_book.setdefault(chunk.metadata.book_num, []).append(chunk)

    async def one(book_num: int, book_chunks: list[Chunk]):
        async with semaphore:
            try:
                return await _extract_book(question, book_chunks, llm)
            except ProviderError:
                raise
            except Exception as error:  # one book must not abort the whole answer
                logger.warning("extract failed for book %d: %s", book_num, error)
                return None

    extracted = await asyncio.gather(
        *(one(book_num, book_chunks) for book_num, book_chunks in by_book.items())
    )
    extracts = [item for item in extracted if item is not None]
    if tracer is not None and extract_span is not None:
        tracer.finish(
            extract_span,
            extracts=len(extracts),
            books=[extract.book_num for extract in extracts],
        )
    if not extracts:
        if tracer is not None:
            tracer.emit("abstain", reason="no_evidence", hits=len(chunks))
        return AskResult(
            ABSTAIN_MESSAGE,
            abstained=True,
            chunks=chunks,
            attempts=0,
            abstain_reason="no_evidence",
        )

    covered = {extract.book_num for extract in extracts}
    evidence_chunks = [chunk for extract in extracts for chunk in extract.chunks]
    prompt = _synthesis_prompt(question, extracts)
    if on_stage is not None:
        on_stage("generate")
    generate_span = tracer.start("synthesize") if tracer else None
    draft = await _one_draft(MULTI_BOOK_SYSTEM, prompt, llm, on_token)
    if tracer is not None and generate_span is not None:
        tracer.finish(
            generate_span,
            model=getattr(llm, "name", "?"),
            books=sorted(covered),
            **prompt_fingerprint(MULTI_BOOK_SYSTEM, prompt),
        )
    result = ground_answer(draft, evidence_chunks)
    if _is_refusal(draft, cited=bool(result.citations)):
        if tracer is not None:
            tracer.emit("final", abstained=True, abstain_reason="refused")
        return AskResult(
            ABSTAIN_MESSAGE,
            abstained=True,
            chunks=evidence_chunks,
            attempts=1,
            abstain_reason="refused",
        )
    if result.abstained or not result.citations:
        if tracer is not None:
            tracer.emit("final", abstained=True, abstain_reason="uncited")
        return AskResult(
            ABSTAIN_MESSAGE,
            abstained=True,
            chunks=evidence_chunks,
            attempts=1,
            abstain_reason="uncited",
        )
    coverage = coverage_statement(covered)
    answer = f"{draft.strip()}\n\n{coverage}"
    if tracer is not None:
        tracer.emit(
            "coverage",
            covered=sorted(covered),
            missing=sorted(set(range(1, MAX_BOOKS + 1)) - covered),
        )
        tracer.emit(
            "final",
            abstained=False,
            attempts=1,
            citations=len(result.citations),
        )
    logger.info(
        "multi-book answered: books=%d citations=%d retrieve=%.0fms",
        len(covered),
        len(result.citations),
        (time.perf_counter() - start) * 1000,
    )
    return AskResult(
        answer,
        citations=result.citations,
        chunks=evidence_chunks,
        attempts=1,
    )
