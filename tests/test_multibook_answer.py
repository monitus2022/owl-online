"""Multi-book answer path, no network."""

import re

from app.pipeline.generate import generate as generate_module
from app.pipeline.generate.multibook import (
    MULTI_BOOK_EXTRACT_SYSTEM,
    MULTI_BOOK_SYSTEM,
    ask_multi_book,
    coverage_statement,
)
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

    async def generate(self, system: str, prompt: str, *, context=None) -> str:
        if system == MULTI_BOOK_EXTRACT_SYSTEM:
            if self.no_evidence:
                return "NO_EVIDENCE"
            match = re.search(r"\[(b\d+-c\d+-\d+)\] (.+)", prompt)
            return f"- {match.group(2).strip()} [{match.group(1)}]"
        if system == MULTI_BOOK_SYSTEM:
            ids = _CITATION.findall(prompt)
            return f"Combined answer [{ids[0]}][{ids[-1]}]."
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
    assert result.citations == ["b1-c01-0000", "b7-c01-0000"]
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


async def test_ask_routes_to_the_multi_book_path_when_enabled(monkeypatch):
    monkeypatch.setattr(generate_module.settings, "multi_book", True)
    result = await generate_module.ask(
        "Who teaches in each book?",
        retriever=_Retriever(),
        llm=_Llm(),
    )
    assert not result.abstained
    assert "Coverage:" in result.answer
    assert result.citations


async def test_ask_keeps_single_pass_when_the_flag_is_off(monkeypatch):
    monkeypatch.setattr(generate_module.settings, "multi_book", False)

    class _SingleLlm(_Llm):
        async def generate(self, system: str, prompt: str, *, context=None) -> str:
            return "Single-pass answer [b1-c01-0000]."

    result = await generate_module.ask(
        "Who teaches in each book?",
        retriever=_Retriever(),
        llm=_SingleLlm(),
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
