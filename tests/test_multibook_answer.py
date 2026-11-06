"""Multi-book answer path, no network."""

import re

import pytest

from app.pipeline.generate import generate as generate_module
from app.pipeline.generate.multibook import (
    MULTI_BOOK_BATCH_EXTRACT_SYSTEM,
    MULTI_BOOK_EXTRACT_SYSTEM,
    MULTI_BOOK_SYSTEM,
    BookExtract,
    _cap_evidence,
    _line_supported,
    ask_multi_book,
    coverage_statement,
)
from app.providers.errors import ProviderError
from app.schemas import Chunk, ChunkMetadata

_CITATION = re.compile(r"\[(b\d+-c\d+-\d+)\]")


def _chunk(book: int) -> Chunk:
    return Chunk(
        id=f"b{book}-c01-0000",
        text=f"Book {book} says something relevant.",
        metadata=ChunkMetadata(
            book_num=book,
            chapter_num=1,
            book_name=f"Book {book}",
            chapter_name="Chapter 1",
        ),
        score=1.0,
    )


class _Retriever:
    def __init__(self, missing: set[int] | None = None) -> None:
        self.missing = missing or set()

    async def retrieve(self, query: str, top_k: int):
        return [_chunk(1)]

    async def retrieve_book(self, query: str, book_num: int, top_k: int):
        if book_num in self.missing:
            return []
        return [_chunk(book_num)]


class _Llm:
    name = "fake/multibook"

    def __init__(self, no_evidence: bool = False) -> None:
        self.no_evidence = no_evidence
        self.calls = 0

    async def generate(self, system: str, prompt: str, *, context=None) -> str:
        self.calls += 1
        if system == MULTI_BOOK_EXTRACT_SYSTEM:
            if self.no_evidence:
                return "NO_EVIDENCE"
            match = re.search(r"\[(b\d+-c\d+-\d+)\] (.+)", prompt)
            return f"- {match.group(2).strip()} [{match.group(1)}]"
        if system == MULTI_BOOK_BATCH_EXTRACT_SYSTEM:
            if self.no_evidence:
                return "NO_EVIDENCE"
            lines = [
                f"- Book {book}: {text.strip()} [{cid}]"
                for book, cid, text in re.findall(
                    r"Book (\d+):\n\[(b\d+-c\d+-\d+)\] (.+)", prompt
                )
            ]
            return "\n".join(lines)
        if system == MULTI_BOOK_SYSTEM:
            quotes = [
                line[2:].strip()
                for line in prompt.splitlines()
                if line.startswith("- ")
            ]
            return "\n".join(quotes)
        raise AssertionError(f"unexpected system prompt: {system}")

    def stream(self, system: str, prompt: str, *, context=None):
        async def gen():
            yield await self.generate(system, prompt)

        return gen()


async def test_multi_book_path_merges_extracts_and_states_coverage():
    result = await ask_multi_book(
        "Who appears in each book?",
        retriever=_Retriever(missing={3}),
        llm=_Llm(),
    )
    assert not result.abstained
    assert result.citations == [
        "b1-c01-0000",
        "b2-c01-0000",
        "b4-c01-0000",
        "b5-c01-0000",
        "b6-c01-0000",
        "b7-c01-0000",
    ]
    assert "Coverage: books 1, 2, 4, 5, 6 and 7 had evidence" in result.answer
    assert "book 3 had none" in result.answer
    assert len(result.chunks) == 6
    assert result.attempts == 1


async def test_multi_book_path_abstains_without_extracts():
    result = await ask_multi_book(
        "Who appears in each book?",
        retriever=_Retriever(),
        llm=_Llm(no_evidence=True),
    )
    assert result.abstained
    assert result.abstain_reason == "no_evidence"


async def test_multi_book_path_abstains_when_no_book_has_evidence():
    result = await ask_multi_book(
        "Who appears in each book?",
        retriever=_Retriever(missing=set(range(1, 8))),
        llm=_Llm(),
    )
    assert result.abstained
    assert result.abstain_reason == "no_evidence"


async def test_multi_book_path_abstains_on_uncited_synthesis():
    class _UncitedLlm(_Llm):
        async def generate(self, system: str, prompt: str, *, context=None) -> str:
            if system == MULTI_BOOK_SYSTEM:
                return "An answer with no citation."
            return await super().generate(system, prompt)

    result = await ask_multi_book(
        "Who appears in each book?",
        retriever=_Retriever(),
        llm=_UncitedLlm(),
    )
    assert result.abstained
    assert result.abstain_reason == "uncited"


async def test_top1_floor_keeps_books_above_the_floor():
    result = await ask_multi_book(
        "Who appears in each book?",
        retriever=_Retriever(),
        llm=_Llm(),
        selection="top1_floor",
        selection_floor=0.5,
    )
    assert not result.abstained
    assert result.citations == [f"b{book}-c01-0000" for book in range(1, 8)]


async def test_top1_floor_skips_a_book_below_the_floor():
    class _LowScoreRetriever(_Retriever):
        async def retrieve_book(self, query, book_num, top_k):
            chunks = await super().retrieve_book(query, book_num, top_k)
            if book_num == 3:
                return [chunk.model_copy(update={"score": 0.1}) for chunk in chunks]
            return chunks

    result = await ask_multi_book(
        "Who appears in each book?",
        retriever=_LowScoreRetriever(),
        llm=_Llm(),
        selection="top1_floor",
        selection_floor=0.5,
    )
    assert not result.abstained
    assert "b3-c01-0000" not in result.citations
    assert "book 3 had none" in result.answer


async def test_batched_top3_uses_one_extraction_call():
    llm = _Llm()
    result = await ask_multi_book(
        "Who appears in each book?",
        retriever=_Retriever(),
        llm=llm,
        selection="batched_top3",
    )
    assert not result.abstained
    assert result.citations == [f"b{book}-c01-0000" for book in range(1, 8)]
    # One batched extraction plus one synthesis.
    assert llm.calls == 2


async def test_unknown_selection_is_rejected():
    with pytest.raises(ValueError, match="unknown multi-book selection"):
        await ask_multi_book(
            "Who appears in each book?",
            retriever=_Retriever(),
            llm=_Llm(),
            selection="nope",
        )


def test_coverage_statement_all_partial_and_none():
    assert coverage_statement(set(range(1, 8))) == (
        "Coverage: all seven books had evidence."
    )
    assert coverage_statement({2}) == (
        "Coverage: book 2 had evidence; books 1, 3, 4, 5, 6 and 7 had none."
    )
    assert coverage_statement(set()) == (
        "Coverage: none of the seven books had evidence."
    )
    assert coverage_statement({3}, {3}) == (
        "Coverage: the selected book (3) had evidence."
    )
    assert coverage_statement({9}, {1, 2}) == (
        "Coverage: none of the 2 selected books had evidence."
    )


async def test_ask_routes_to_the_multi_book_path_when_enabled():
    result = await generate_module.ask(
        "Who teaches in each book?",
        retriever=_Retriever(),
        llm=_Llm(),
        multi_book=True,
    )
    assert not result.abstained
    assert "Coverage:" in result.answer
    assert result.citations


async def test_ask_keeps_single_pass_when_the_flag_is_off():
    class _SingleLlm(_Llm):
        async def generate(self, system: str, prompt: str, *, context=None) -> str:
            return "Single-pass answer [b1-c01-0000]."

    result = await generate_module.ask(
        "Who teaches in each book?",
        retriever=_Retriever(),
        llm=_SingleLlm(),
        multi_book=False,
    )
    assert "Coverage:" not in result.answer
    assert result.citations == ["b1-c01-0000"]


async def test_paraphrased_extract_is_discarded():
    class _ParaphraseLlm(_Llm):
        async def generate(self, system: str, prompt: str, *, context=None) -> str:
            if system == MULTI_BOOK_EXTRACT_SYSTEM:
                chunk_id = _CITATION.search(prompt)[1]
                return f"- Quirrell teaches the subject [{chunk_id}]"
            return await super().generate(system, prompt)

    result = await ask_multi_book(
        "Who appears in each book?",
        retriever=_Retriever(),
        llm=_ParaphraseLlm(),
    )
    assert result.abstained
    assert result.abstain_reason == "no_evidence"


async def test_multi_book_answer_drops_an_invented_citation():
    class _MixedLlm(_Llm):
        async def generate(self, system: str, prompt: str, *, context=None) -> str:
            if system == MULTI_BOOK_SYSTEM:
                return "Book 1 says something relevant. [b1-c01-0000][b9-c99-9999]"
            return await super().generate(system, prompt)

    result = await ask_multi_book(
        "Who appears in each book?",
        retriever=_Retriever(),
        llm=_MixedLlm(),
    )
    assert result.citations == ["b1-c01-0000"]
    assert "b9-c99-9999" not in result.answer


async def test_multi_book_answer_propagates_provider_errors():
    class _ProviderRetriever(_Retriever):
        async def retrieve_book(self, query: str, book_num: int, top_k: int):
            raise ProviderError("provider down")

    with pytest.raises(ProviderError, match="provider down"):
        await ask_multi_book(
            "Who appears in each book?",
            retriever=_ProviderRetriever(),
            llm=_Llm(),
        )


async def test_multi_book_answer_respects_top_k():
    result = await ask_multi_book(
        "Who appears in each book?",
        retriever=_Retriever(),
        llm=_Llm(),
        top_k=2,
    )
    assert len(result.chunks) <= 2
    assert len(result.citations) <= 2


def _chunk_at(book: int, chapter: int) -> Chunk:
    return Chunk(
        id=f"b{book}-c{chapter:02d}-0000",
        text=f"Book {book} chapter {chapter} names a relevant person.",
        metadata=ChunkMetadata(
            book_num=book,
            chapter_num=chapter,
            book_name=f"Book {book}",
            chapter_name=f"Chapter {chapter}",
        ),
        score=1.0 - chapter / 100,
    )


def test_cap_evidence_keeps_one_chunk_per_book_before_repeats():
    extracts = [
        BookExtract(
            book,
            tuple(_chunk_at(book, chapter) for chapter in range(1, 4)),
            tuple(
                f"Book {book} chapter {chapter} names a relevant person. "
                f"[b{book}-c{chapter:02d}-0000]"
                for chapter in range(1, 4)
            ),
        )
        for book in range(1, 8)
    ]
    capped = _cap_evidence(extracts, 7)
    assert len(capped) == 7
    assert [len(extract.chunks) for extract in capped] == [1] * 7
    assert {extract.book_num for extract in capped} == set(range(1, 8))


def test_line_supported_rejects_a_cross_book_quote():
    by_id = {"b1-c01-0000": _chunk_at(1, 1), "b5-c01-0000": _chunk_at(5, 1)}
    assert _line_supported(
        "Book 1: Book 5 chapter 1 names a relevant person. [b5-c01-0000]", by_id
    ) is False


def test_line_supported_requires_every_segment():
    chunk = _chunk_at(1, 1)
    by_id = {chunk.id: chunk}
    assert _line_supported(
        "Book 1: Book 1 chapter 1 names a relevant person. ... "
        "and an invented clause follows [b1-c01-0000]",
        by_id,
    ) is False


def test_line_supported_accepts_a_verbatim_quote():
    chunk = _chunk_at(1, 1)
    by_id = {chunk.id: chunk}
    assert _line_supported(
        "Book 1: Book 1 chapter 1 names a relevant person. [b1-c01-0000]", by_id
    )


async def test_multi_book_path_keeps_both_books_for_distinct_lines():
    class _RepeatLlm(_Llm):
        async def generate(self, system: str, prompt: str, *, context=None) -> str:
            if system == MULTI_BOOK_EXTRACT_SYSTEM:
                match = re.search(r"\[(b\d+-c\d+-\d+)\] (.+)", prompt)
                return f"- {match.group(2).strip()} [{match.group(1)}]"
            if system == MULTI_BOOK_SYSTEM:
                return (
                    "Book 1: Book 1 says something relevant. [b1-c01-0000]\n"
                    "Book 2: Book 2 says something relevant. [b2-c01-0000]"
                )
            raise AssertionError(system)

    result = await ask_multi_book(
        "Who appears in each book?",
        retriever=_Retriever(missing=set(range(3, 8))),
        llm=_RepeatLlm(),
    )
    assert not result.abstained
    assert "books 1 and 2 had evidence" in result.answer


async def test_multi_book_path_counts_every_extraction_call():
    result = await ask_multi_book(
        "Who appears in each book?",
        retriever=_Retriever(),
        llm=_Llm(no_evidence=True),
    )
    assert result.abstained
    assert result.model_calls == 7


async def test_multi_book_path_counts_extractions_and_synthesis():
    result = await ask_multi_book(
        "Who appears in each book?",
        retriever=_Retriever(),
        llm=_Llm(),
    )
    assert result.model_calls == 8


async def test_multi_book_path_respects_explicit_book_numbers():
    result = await ask_multi_book(
        "What happens in books 1 and 2?",
        retriever=_Retriever(),
        llm=_Llm(),
        books=[1, 2],
    )
    assert not result.abstained
    assert "all 2 selected books had evidence" in result.answer
    assert {chunk.metadata.book_num for chunk in result.chunks} == {1, 2}


async def test_coverage_excludes_a_book_whose_line_was_dropped():
    class _PartlyInventedLlm(_Llm):
        async def generate(self, system: str, prompt: str, *, context=None) -> str:
            if system == MULTI_BOOK_SYSTEM:
                return (
                    "Book 1: Book 1 says something relevant. [b1-c01-0000]\n"
                    "Book 2: An invented claim about book 2. [b2-c01-0000]"
                )
            return await super().generate(system, prompt)

    result = await ask_multi_book(
        "Who appears in each book?",
        retriever=_Retriever(missing=set(range(4, 8))),
        llm=_PartlyInventedLlm(),
    )
    assert not result.abstained
    assert "book 1 had evidence" in result.answer
    assert "books 2, 3, 4, 5, 6 and 7 had none" in result.answer
    assert "book 2 had evidence" not in result.answer


async def test_a_repeated_sentence_is_kept_for_each_book():
    class _SameTextRetriever(_Retriever):
        async def retrieve_book(self, query: str, book_num: int, top_k: int):
            if book_num > 2:
                return []
            chunk = _chunk(book_num).model_copy(
                update={"text": "A shared relevant sentence about the topic."}
            )
            return [chunk]

    class _SameTextLlm(_Llm):
        async def generate(self, system: str, prompt: str, *, context=None) -> str:
            if system == MULTI_BOOK_EXTRACT_SYSTEM:
                match = re.search(r"\[(b\d+-c\d+-\d+)\] (.+)", prompt)
                return f"- {match.group(2).strip()} [{match.group(1)}]"
            if system == MULTI_BOOK_SYSTEM:
                return (
                    "Book 1: A shared relevant sentence about the topic. "
                    "[b1-c01-0000]\n"
                    "Book 2: A shared relevant sentence about the topic. "
                    "[b2-c01-0000]"
                )
            raise AssertionError(system)

    result = await ask_multi_book(
        "Who appears in each book?",
        retriever=_SameTextRetriever(),
        llm=_SameTextLlm(),
    )
    assert not result.abstained
    assert "books 1 and 2 had evidence" in result.answer
    assert set(result.citations) == {"b1-c01-0000", "b2-c01-0000"}


async def test_extraction_provider_error_propagates():
    class _ProviderLlm(_Llm):
        async def generate(self, system: str, prompt: str, *, context=None) -> str:
            if system == MULTI_BOOK_EXTRACT_SYSTEM:
                raise ProviderError("extraction down")
            return await super().generate(system, prompt)

    with pytest.raises(ProviderError, match="extraction down"):
        await ask_multi_book(
            "Who appears in each book?",
            retriever=_Retriever(missing=set(range(2, 8))),
            llm=_ProviderLlm(),
        )


async def test_multi_book_graph_carries_model_calls():
    from app.agent import build_graph

    graph = build_graph(_Retriever(), _Llm(), multi_book=True)
    state = await graph.ainvoke(
        {
            "question": "Who teaches in each book?",
            "requested_mode": "auto",
            "student_answer": None,
            "top_k": 7,
        }
    )
    assert state["model_calls"] == 8
    assert state["abstain_reason"] is None
    assert "Coverage:" in state["answer"]
