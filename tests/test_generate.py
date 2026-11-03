"""ask() tests: grounded citations, abstention, no network."""

from app.pipeline.generate import ABSTAIN_MESSAGE, AskResult, ask
from app.schemas import Chunk, ChunkMetadata


def _chunk(cid: str, score: float, text: str = "text") -> Chunk:
    return Chunk(
        id=cid,
        text=text,
        metadata=ChunkMetadata(
            book_num=1, chapter_num=1, book_name="Book 1", chapter_name="Chapter 1"
        ),
        score=score,
    )


class _Retriever:
    def __init__(self, chunks: list[Chunk]) -> None:
        self._chunks = chunks
        self.calls: list[tuple[str, int]] = []

    async def retrieve(self, query: str, top_k: int) -> list[Chunk]:
        self.calls.append((query, top_k))
        return self._chunks[:top_k]


class _Llm:
    def __init__(self, answer: str) -> None:
        self._answer = answer
        self.calls: list[tuple[str, str]] = []

    async def generate(self, system: str, prompt: str, *, context=None) -> str:
        self.calls.append((system, prompt))
        return self._answer


async def test_grounded_answer_returns_cited_ids():
    chunks = [_chunk("b1-c01-0000", 0.03), _chunk("b1-c02-0000", 0.02)]
    llm = _Llm("The Dursleys live at Privet Drive [b1-c01-0000].")
    result = await ask("Where?", retriever=_Retriever(chunks), llm=llm)
    assert result.abstained is False
    assert result.citations == ["b1-c01-0000"]
    assert "b1-c01-0000" in result.answer


async def test_only_retrieved_ids_are_accepted_as_citations():
    chunks = [_chunk("b1-c01-0000", 0.03)]
    llm = _Llm("See [b9-c99-0000] and [b1-c01-0000].")
    result = await ask("Where?", retriever=_Retriever(chunks), llm=llm)
    assert result.citations == ["b1-c01-0000"]


async def test_duplicate_citations_are_deduped_in_order():
    chunks = [_chunk("b1-c01-0000", 0.03), _chunk("b1-c02-0000", 0.02)]
    llm = _Llm("[b1-c02-0000] then [b1-c01-0000] then [b1-c02-0000]")
    result = await ask("q", retriever=_Retriever(chunks), llm=llm)
    assert result.citations == ["b1-c02-0000", "b1-c01-0000"]


async def test_weak_retrieval_abstains_without_calling_the_llm():
    llm = _Llm("should not be used")
    result = await ask("q", retriever=_Retriever([_chunk("b1-c01-0000", 0.001)]), llm=llm)
    assert result == AskResult(ABSTAIN_MESSAGE, [], True)
    assert llm.calls == []


async def test_empty_retrieval_abstains():
    result = await ask("q", retriever=_Retriever([]), llm=_Llm("x"))
    assert result.abstained is True
    assert result.citations == []


async def test_uncited_answer_abstains():
    retriever = _Retriever([_chunk("b1-c01-0000", 0.03)])
    result = await ask("q", retriever=retriever, llm=_Llm("Surrey."))
    assert result.abstained is True
    assert result.citations == []


async def test_prompt_contains_excerpt_ids_and_question():
    chunks = [_chunk("b1-c01-0000", 0.03, text="Privet Drive")]
    llm = _Llm("[b1-c01-0000]")
    await ask("Where do they live?", retriever=_Retriever(chunks), llm=llm)
    _, prompt = llm.calls[0]
    assert "[b1-c01-0000]" in prompt
    assert "Privet Drive" in prompt
    assert "Where do they live?" in prompt