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
    assert "grounded only in the setting notes" in llm.systems[0]
    assert "Cite every setting fact with [lore:<id>]" in llm.systems[0]
    assert "grounded only in the excerpts" not in llm.systems[0]


async def test_public_history_question_uses_the_record_entry():
    llm = _Llm("The war is public history [lore:public-record-war].")
    result = await ask(
        "What does Professor Crane know about the war?",
        retriever=_WeakRetriever(),
        llm=llm,
        lore=STORE,
    )
    assert not result.abstained
    assert result.lore_citations == ["public-record-war"]
    assert "[lore:public-record-war]" in llm.prompts[0]
    assert "The public history of the war" in llm.prompts[0]


async def test_a_battle_detail_question_without_book_evidence_abstains():
    result = await ask(
        "What happened at the Battle of Hogwarts?",
        retriever=_WeakRetriever(),
        llm=_Llm("A confident claim [lore:public-record-war]."),
        lore=STORE,
    )
    assert result.abstained
    assert result.abstain_reason == "no_evidence"


async def test_grouped_lore_citations_are_parsed():
    llm = _Llm(
        "Ashcombe was founded in 2008 "
        "[lore:school-001, lore:timeline-2008]."
    )
    result = await ask(
        "When was Ashcombe founded?",
        retriever=_WeakRetriever(),
        llm=llm,
        lore=STORE,
    )
    assert not result.abstained
    assert result.lore_citations == ["school-001", "timeline-2008"]


async def test_a_book_question_does_not_pull_lore_into_the_prompt():
    llm = _Llm("Rowan trims the wick [b1-c01-0000].")
    result = await ask(
        "Who is the new Defence Against the Dark Arts teacher?",
        retriever=_Retriever(),
        llm=llm,
        lore=STORE,
    )
    assert not result.abstained
    assert result.lore_citations == []
    assert "Setting notes:" not in llm.prompts[0]
    assert "grounded only in the excerpts" in llm.systems[0]


async def test_a_book_id_cannot_pass_as_lore_and_vice_versa():
    llm = _Llm("A claim [lore:b1-c01-0000] and another [b1-c01-0000].")
    result = await ask(
        "Who trims the wick?",
        retriever=_Retriever(),
        llm=llm,
        lore=STORE,
    )
    assert result.citations == ["b1-c01-0000"]
    assert result.lore_citations == []
    assert "[lore:b1-c01-0000]" not in result.answer


async def test_a_draft_with_no_citation_in_either_space_abstains():
    llm = _Llm("A confident claim with no citation.")
    result = await ask(
        "When was Ashcombe founded?",
        retriever=_WeakRetriever(),
        llm=llm,
        lore=STORE,
    )
    assert result.abstained
    assert result.abstain_reason == "uncited"
    assert "cited no setting note" in llm.systems[1]


async def test_a_bare_lore_id_cannot_pass_as_a_chunk():
    result = await ask(
        "Who is Professor Crane?",
        retriever=_Retriever(),
        llm=_Llm("A claim [school-001]."),
        lore=STORE,
    )
    assert result.abstained
    assert result.abstain_reason == "uncited"
