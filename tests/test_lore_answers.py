"""Lore-grounded answers: book and lore citation spaces, no network."""

from pathlib import Path

from app.knowledge import load_lore
from app.pipeline.generate import ask
from app.schemas import Chunk, ChunkMetadata

STORE = load_lore(Path(__file__).resolve().parents[1] / "eval" / "fixtures" / "lore")


def _chunk() -> Chunk:
    return Chunk(
        id="b1-c01-0000",
        text="Rowan trims the wick.",
        metadata=ChunkMetadata(
            book_num=1, chapter_num=1, book_name="Book 1", chapter_name="Chapter 1"
        ),
        score=1.0,
    )


class _Retriever:
    async def retrieve(self, query: str, top_k: int) -> list[Chunk]:
        return [_chunk()]


class _WeakRetriever:
    async def retrieve(self, query: str, top_k: int) -> list[Chunk]:
        return []


class _Llm:
    name = "fake/lore"

    def __init__(self, text: str) -> None:
        self.text = text
        self.systems: list[str] = []
        self.prompts: list[str] = []

    async def generate(self, system: str, prompt: str, *, context=None) -> str:
        self.systems.append(system)
        self.prompts.append(prompt)
        return self.text

    def stream(self, system: str, prompt: str, *, context=None):
        self.systems.append(system)
        self.prompts.append(prompt)

        async def gen():
            yield self.text

        return gen()


async def test_lore_only_answer_cites_the_pack():
    llm = _Llm("Ashcombe was founded in 2008 [lore:school-001].")
    result = await ask(
        "When was Ashcombe founded?",
        retriever=_WeakRetriever(),
        llm=llm,
        lore=STORE,
    )
    assert not result.abstained
    assert result.citations == []
    assert result.lore_citations == ["school-001"]
    assert "[lore:school-001]" in result.answer


async def test_mixed_answer_cites_both_spaces():
    llm = _Llm(
        "Rowan trims the wick [b1-c01-0000]. "
        "Ashcombe was founded in 2008 [lore:school-001]."
    )
    result = await ask(
        "Who trims the wick, and when was Ashcombe founded?",
        retriever=_Retriever(),
        llm=llm,
        lore=STORE,
    )
    assert not result.abstained
    assert result.citations == ["b1-c01-0000"]
    assert result.lore_citations == ["school-001"]


async def test_unknown_lore_citation_abstains():
    llm = _Llm("A confident claim [lore:missing-999].")
    result = await ask(
        "When was Ashcombe founded?",
        retriever=_WeakRetriever(),
        llm=llm,
        lore=STORE,
    )
    assert result.abstained
    assert result.abstain_reason == "uncited"
    assert result.lore_citations == []


async def test_no_evidence_without_book_or_lore():
    result = await ask(
        "When was Ashcombe founded?",
        retriever=_WeakRetriever(),
        llm=_Llm("unused"),
        lore=None,
    )
    assert result.abstained
    assert result.abstain_reason == "no_evidence"


async def test_prompt_includes_setting_notes_and_the_lore_citation_rule():
    llm = _Llm("Ashcombe was founded in 2008 [lore:school-001].")
    await ask(
        "When was Ashcombe founded?",
        retriever=_WeakRetriever(),
        llm=llm,
        lore=STORE,
    )
    assert "Setting notes:" in llm.prompts[0]
    assert "[lore:school-001]" in llm.prompts[0]
    assert "Setting notes are cited as [lore:<id>]." in llm.systems[0]
