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
    ground_answer,
    is_refusal,
    one_draft,
    sanitize_evidence,
)
from app.pipeline.retrieve.multibook import BookRetriever, retrieve_multi_book
from app.providers.contracts import Llm
from app.schemas import Chunk
from app.trace import current_tracer, prompt_fingerprint

logger = logging.getLogger(__name__)

MAX_BOOKS = 7
FANOUT = 4
# Candidates retrieved per book before extraction. k=1 missed the answer chunk
# for some books; 15 covers a chapter's worth without unbounded prompt growth.
PER_BOOK_K = 15
# Extraction strategies for the #105 ablation. `per_book` is the shipped path:
# one extraction call per book over its per-book candidates. `top1_floor` uses
# only the top candidate and drops a book below the floor. `batched_top3` sends
# the top three candidates per book to one extraction call.
DEFAULT_SELECTION = "per_book"
SELECTIONS = frozenset({"per_book", "top1_floor", "batched_top3"})
DEFAULT_SELECTION_FLOOR = 0.0
BATCH_TOP_N = 3
# Final evidence cap: at most one chunk per book under the default seven.
DEFAULT_FINAL_TOP_K = 7
_CITATION = re.compile(r"\[(b\d+-c\d+-\d+)\]")
_BOOK_LABEL = re.compile(r"^[-*]?\s*Book (\d+):\s*", re.IGNORECASE)

MULTI_BOOK_EXTRACT_SYSTEM = (
    "You extract direct quotes from one book for a multi-book question. Use only "
    "the excerpts. Return up to three bullet lines. Each line must be a direct "
    "quote copied verbatim from one excerpt, followed by that excerpt's chunk id "
    "in square brackets, for example [b3-c01-0000]. Do not paraphrase or infer. "
    "If no sentence directly answers the question, reply exactly: NO_EVIDENCE"
)

MULTI_BOOK_BATCH_EXTRACT_SYSTEM = (
    "You extract direct quotes from several books for a multi-book question. Use "
    "only the excerpts. For each book, return up to three bullet lines. Each line "
    "must start with `Book N:` and contain a direct quote copied verbatim from "
    "one excerpt, followed by that excerpt's chunk id in square brackets, for "
    "example `Book 3: \"...\" [b3-c01-0000]`. Do not paraphrase or infer. If a "
    "book has no sentence that directly answers the question, write "
    "`Book N: NO_EVIDENCE`."
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


def coverage_statement(
    covered: set[int], searched: set[int] | None = None
) -> str:
    """A deterministic statement of which searched books had evidence."""
    selected = set(searched) if searched is not None else set(range(1, MAX_BOOKS + 1))
    covered = covered & selected
    missing = sorted(selected - covered)
    if not missing:
        if selected == set(range(1, MAX_BOOKS + 1)):
            return "Coverage: all seven books had evidence."
        if len(selected) == 1:
            return f"Coverage: the selected book ({next(iter(selected))}) had evidence."
        return f"Coverage: all {len(selected)} selected books had evidence."
    if not covered:
        if selected == set(range(1, MAX_BOOKS + 1)):
            return "Coverage: none of the seven books had evidence."
        if len(selected) == 1:
            return f"Coverage: the selected book ({next(iter(selected))}) had none."
        return f"Coverage: none of the {len(selected)} selected books had evidence."
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


_TYPOGRAPHIC = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})
_SEGMENT_SPLIT = re.compile(r"\.\.\.|…")


def _normalise(text: str) -> str:
    """Casefold, collapse whitespace and unify curly quotes for comparison."""
    text = text.translate(_TYPOGRAPHIC)
    return re.sub(r"\s+", " ", text).strip().strip('"').casefold()


def _parse_extract(text: str, chunks: list[Chunk]) -> tuple[str, ...]:
    """Keep only direct quotes that appear verbatim in the cited chunk.

    An extract line must cite exactly one chunk from this book, and the quote
    must be found verbatim in that chunk. A line with several citations or an
    unknown one is rejected rather than guessed at.
    """
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
        if len(cited) != 1 or cited[0] not in by_id:
            continue
        quote = _normalise(_CITATION.sub("", line))
        if len(quote) < 15:
            continue
        if quote not in by_id[cited[0]]:
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
    cited_ids = {cid for line in lines for cid in _CITATION.findall(line)}
    cited_chunks = tuple(chunk for chunk in clean if chunk.id in cited_ids)
    if not cited_chunks:
        return None
    return BookExtract(clean[0].metadata.book_num, cited_chunks, lines)


def _batched_extract_prompt(
    question: str, by_book: dict[int, list[Chunk]], top_n: int
) -> str:
    blocks: list[str] = []
    for book_num in sorted(by_book):
        excerpts = "\n\n".join(
            f"[{chunk.id}] {chunk.text.strip()}"
            for chunk in by_book[book_num][:top_n]
        )
        blocks.append(f"Book {book_num}:\n{excerpts}")
    return (
        f"Question: {question}\n\n"
        + "\n\n".join(blocks)
        + "\n\nExtract:"
    )


def _parse_batched_extract(
    text: str, chunks: list[Chunk]
) -> list[BookExtract]:
    """Keep verbatim quotes, grouped by the book of the chunk they cite."""
    by_id = {chunk.id: _normalise(chunk.text) for chunk in chunks}
    book_of = {chunk.id: chunk.metadata.book_num for chunk in chunks}
    grouped: dict[int, list[str]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("-", "*")):
            line = line[1:].strip()
        label = _BOOK_LABEL.match(line)
        label_book = int(label.group(1)) if label else None
        if label is not None:
            line = line[label.end() :].strip()
        if line.upper().startswith("NO_EVIDENCE"):
            continue
        cited = _CITATION.findall(line)
        if len(cited) != 1 or cited[0] not in by_id:
            continue
        book_num = book_of[cited[0]]
        if label_book is not None and label_book != book_num:
            continue
        quote = _normalise(_CITATION.sub("", line))
        if len(quote) < 15:
            continue
        if quote not in by_id[cited[0]]:
            continue
        grouped.setdefault(book_num, []).append(line)
    extracts: list[BookExtract] = []
    for book_num, lines in sorted(grouped.items()):
        kept_lines = tuple(lines[:3])
        cited_ids = {
            cid for line in kept_lines for cid in _CITATION.findall(line)
        }
        cited_chunks = tuple(chunk for chunk in chunks if chunk.id in cited_ids)
        if cited_chunks:
            extracts.append(BookExtract(book_num, cited_chunks, kept_lines))
    return extracts


async def _extract_batched(
    question: str,
    chunks: list[Chunk],
    llm: Llm,
    *,
    top_n: int = BATCH_TOP_N,
) -> list[BookExtract]:
    clean: list[Chunk] = []
    for chunk in chunks:
        text, _ = sanitize_evidence(chunk.text)
        clean.append(chunk.model_copy(update={"text": text}))
    by_book: dict[int, list[Chunk]] = {}
    for chunk in clean:
        by_book.setdefault(chunk.metadata.book_num, []).append(chunk)
    response = await llm.generate(
        MULTI_BOOK_BATCH_EXTRACT_SYSTEM,
        _batched_extract_prompt(question, by_book, top_n),
    )
    return _parse_batched_extract(response, clean)


def _synthesis_prompt(question: str, extracts: list[BookExtract]) -> str:
    blocks: list[str] = []
    for extract in extracts:
        blocks.append(
            f"Book {extract.book_num}:\n"
            + "\n".join(f"- {line}" for line in extract.lines)
        )
    return (
        f"Question: {question}\n\n"
        "Evidence by book:\n\n"
        + "\n\n".join(blocks)
        + "\n\nAnswer:"
    )


def _dedupe_extracts(extracts: list[BookExtract]) -> list[BookExtract]:
    """Drop repeated lines inside one book, keeping every book's evidence.

    Cross-book repeats are kept on purpose: the coverage claim is per book, so
    the same sentence found in two books is evidence for both. Conflicting lines
    are not resolved here; both reach synthesis labelled by book.
    """
    merged: list[BookExtract] = []
    for extract in extracts:
        seen: set[str] = set()
        lines: list[str] = []
        for line in extract.lines:
            key = _normalise(_CITATION.sub("", line))
            if key in seen:
                continue
            seen.add(key)
            lines.append(line)
        if lines:
            merged.append(BookExtract(extract.book_num, extract.chunks, tuple(lines)))
    return merged


def _cap_evidence(extracts: list[BookExtract], top_k: int) -> list[BookExtract]:
    """Keep at most `top_k` cited chunks, one round per book before any repeats.

    Round-robin selection means seven books keep one chunk each under the
    default cap of seven, so a book is not dropped because another book scored
    higher. Extract lines that cite a dropped chunk are removed with it.
    """
    limit = max(1, top_k)
    pools = [list(extract.chunks) for extract in extracts]
    kept: list[str] = []
    while len(kept) < limit and any(pools):
        for pool in pools:
            if not pool:
                continue
            chunk = pool.pop(0)
            if chunk.id not in kept:
                kept.append(chunk.id)
            if len(kept) >= limit:
                break
    keep = set(kept)
    capped: list[BookExtract] = []
    for extract in extracts:
        lines = tuple(
            line for line in extract.lines if set(_CITATION.findall(line)) <= keep
        )
        if not lines:
            continue
        # Keep only the chunks a surviving line actually cites, so a dropped
        # line does not hold a cap slot.
        line_ids = {cid for line in lines for cid in _CITATION.findall(line)}
        chunks = tuple(chunk for chunk in extract.chunks if chunk.id in line_ids)
        if not chunks:
            continue
        capped.append(BookExtract(extract.book_num, chunks, lines))
    return capped


def _line_supported(line: str, by_id: dict[str, Chunk]) -> bool:
    """A synthesis line passes only if its quote sits in the chunks it cites.

    Every citation must name an extracted chunk, the `Book N` label must match
    those chunks' books, and every non-empty segment of the quote (split on
    ellipses) must be found verbatim. A paraphrase, a cross-book quote or an
    invented clause fails, including a short invented tail.
    """
    cited = _CITATION.findall(line)
    known = [cid for cid in cited if cid in by_id]
    if not known:
        return False
    chunks = [by_id[cid] for cid in known]
    label = re.match(r"^[-*]?\s*Book (\d+):", line)
    if label is not None and any(
        chunk.metadata.book_num != int(label.group(1)) for chunk in chunks
    ):
        return False
    quote = re.sub(r"^[-*]\s*", "", line)
    quote = re.sub(r"^Book \d+:\s*", "", quote)
    quote = _CITATION.sub("", quote)
    segments = [
        segment
        for segment in (_normalise(part) for part in _SEGMENT_SPLIT.split(quote))
        if segment
    ]
    if not segments:
        return False
    haystack = " ".join(_normalise(chunk.text) for chunk in chunks)
    return all(segment in haystack for segment in segments)


def _filter_supported_lines(draft: str, chunks: list[Chunk]) -> str:
    """Keep only synthesis lines whose quote is grounded in their cited chunk."""
    by_id = {chunk.id: chunk for chunk in chunks}
    kept = [
        line.strip()
        for line in draft.splitlines()
        if line.strip() and _line_supported(line.strip(), by_id)
    ]
    return "\n".join(kept)


async def ask_multi_book(
    question: str,
    *,
    retriever: BookRetriever,
    llm: Llm,
    top_k: int = DEFAULT_FINAL_TOP_K,
    books: list[int] | None = None,
    per_book_k: int = PER_BOOK_K,
    selection: str = DEFAULT_SELECTION,
    selection_floor: float = DEFAULT_SELECTION_FLOOR,
    on_token: Callable[[str], None] | None = None,
    on_stage: Callable[[str], None] | None = None,
) -> AskResult:
    """Answer a multi-book question from per-book evidence, with coverage."""
    if selection not in SELECTIONS:
        raise ValueError(f"unknown multi-book selection {selection!r}")
    tracer = current_tracer()
    if on_stage is not None:
        on_stage("retrieve")
    retrieve_span = tracer.start("retrieve_multi_book") if tracer else None
    start = time.perf_counter()
    searched = set(books) if books else set(range(1, MAX_BOOKS + 1))
    chunks = await retrieve_multi_book(
        retriever,
        question,
        per_book_k=per_book_k,
        fanout=FANOUT,
        books=sorted(searched),
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

    by_book: dict[int, list[Chunk]] = {}
    for chunk in chunks:
        by_book.setdefault(chunk.metadata.book_num, []).append(chunk)

    if selection == "batched_top3":
        extracts = _dedupe_extracts(
            await _extract_batched(question, chunks, llm, top_n=BATCH_TOP_N)
        )
        calls = 1
    else:
        if selection == "top1_floor":
            by_book = {
                book_num: book_chunks[:1]
                for book_num, book_chunks in by_book.items()
                if book_chunks and book_chunks[0].score >= selection_floor
            }
        semaphore = asyncio.Semaphore(FANOUT)

        async def one(book_num: int, book_chunks: list[Chunk]):
            async with semaphore:
                return await _extract_book(question, book_chunks, llm)

        extracted = await asyncio.gather(
            *(one(book_num, book_chunks) for book_num, book_chunks in by_book.items())
        )
        extracts = _dedupe_extracts([item for item in extracted if item is not None])
        calls = len(by_book)
    extracts = _cap_evidence(extracts, top_k)
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
            chunks=chunks[:top_k],
            attempts=0,
            abstain_reason="no_evidence",
            model_calls=calls,
        )

    evidence_chunks = [chunk for extract in extracts for chunk in extract.chunks]
    extracted_books = {extract.book_num for extract in extracts}
    prompt = _synthesis_prompt(question, extracts)
    if on_stage is not None:
        on_stage("generate")
    generate_span = tracer.start("synthesize") if tracer else None
    raw = await one_draft(MULTI_BOOK_SYSTEM, prompt, llm, on_token)
    if tracer is not None and generate_span is not None:
        tracer.finish(
            generate_span,
            model=getattr(llm, "name", "?"),
            books=sorted(extracted_books),
            **prompt_fingerprint(MULTI_BOOK_SYSTEM, prompt),
        )
    refused = is_refusal(raw, cited=bool(_CITATION.search(raw)))
    draft = _filter_supported_lines(raw, evidence_chunks)
    result = ground_answer(draft, evidence_chunks)
    # Coverage follows the lines that survived binding, not the raw extracts:
    # a book whose only line was dropped is not claimed as covered.
    by_id = {chunk.id: chunk for chunk in evidence_chunks}
    covered = {
        by_id[cid].metadata.book_num
        for line in draft.splitlines()
        for cid in _CITATION.findall(line)
        if cid in by_id
    }
    if refused:
        if tracer is not None:
            tracer.emit("final", abstained=True, abstain_reason="refused")
        return AskResult(
            ABSTAIN_MESSAGE,
            abstained=True,
            chunks=evidence_chunks,
            attempts=1,
            abstain_reason="refused",
            model_calls=calls + 1,
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
            model_calls=calls + 1,
        )
    coverage = coverage_statement(covered, searched)
    answer = f"{result.answer}\n\n{coverage}"
    if tracer is not None:
        tracer.emit(
            "coverage",
            covered=sorted(covered),
            missing=sorted(searched - covered),
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
        model_calls=calls + 1,
    )
