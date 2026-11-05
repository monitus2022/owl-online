"""ask() tests: grounded citations, abstention, no network.

All excerpt text is invented; the corpus is copyrighted and stays out of git.
"""

from app.pipeline.generate import ABSTAIN_MESSAGE, ask
from app.schemas import Chunk, ChunkMetadata

# RRF reference scores with rrf_k=60: one leg contributes 1/(rrf_k+1) for its
# top hit, a two-leg hit twice that. DEFAULT_MIN_SCORE requires a two-leg hit.
_ONE_LEG = 1.0 / 61
_TWO_LEG = 2.0 / 61


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
    chunks = [_chunk("b1-c01-0000", _TWO_LEG), _chunk("b1-c02-0000", _ONE_LEG)]
    llm = _Llm("The lighthouse keeper is Rowan [b1-c01-0000].")
    result = await ask("Who keeps the lighthouse?", retriever=_Retriever(chunks), llm=llm)
    assert result.abstained is False
    assert result.citations == ["b1-c01-0000"]
    assert "b1-c01-0000" in result.answer


async def test_only_retrieved_ids_are_accepted_and_invented_ones_are_stripped():
    chunks = [_chunk("b1-c01-0000", _TWO_LEG)]
    llm = _Llm("See [b9-c99-0000] and [b1-c01-0000].")
    result = await ask("q", retriever=_Retriever(chunks), llm=llm)
    assert result.citations == ["b1-c01-0000"]
    assert "b9-c99-0000" not in result.answer


async def test_multi_id_citation_group_is_split():
    chunks = [_chunk("b1-c01-0000", _TWO_LEG), _chunk("b1-c02-0000", _ONE_LEG)]
    llm = _Llm("Both apply [b1-c01-0000, b1-c02-0000].")
    result = await ask("q", retriever=_Retriever(chunks), llm=llm)
    assert result.citations == ["b1-c01-0000", "b1-c02-0000"]


async def test_duplicate_citations_are_deduped_in_order():
    chunks = [_chunk("b1-c01-0000", _TWO_LEG), _chunk("b1-c02-0000", _ONE_LEG)]
    llm = _Llm("[b1-c02-0000] then [b1-c01-0000] then [b1-c02-0000]")
    result = await ask("q", retriever=_Retriever(chunks), llm=llm)
    assert result.citations == ["b1-c02-0000", "b1-c01-0000"]


async def test_weak_retrieval_abstains_without_calling_the_llm():
    llm = _Llm("should not be used")
    result = await ask("q", retriever=_Retriever([_chunk("b1-c01-0000", 0.001)]), llm=llm)
    assert result.answer == ABSTAIN_MESSAGE
    assert result.citations == []
    assert result.abstained is True
    assert [chunk.id for chunk in result.chunks] == ["b1-c01-0000"]
    assert llm.calls == []


async def test_single_leg_hit_abstains():
    """A dense-only top hit (one-leg RRF score) is below the two-leg floor."""
    llm = _Llm("Rowan [b1-c01-0000]")
    result = await ask("q", retriever=_Retriever([_chunk("b1-c01-0000", _ONE_LEG)]), llm=llm)
    assert result.abstained is True
    assert llm.calls == []


async def test_empty_retrieval_abstains():
    result = await ask("q", retriever=_Retriever([]), llm=_Llm("x"))
    assert result.abstained is True
    assert result.citations == []


async def test_uncited_answer_abstains():
    retriever = _Retriever([_chunk("b1-c01-0000", _TWO_LEG)])
    result = await ask("q", retriever=retriever, llm=_Llm("Rowan."))
    assert result.abstained is True
    assert result.citations == []


async def test_prompt_contains_excerpt_ids_and_question():
    chunks = [_chunk("b1-c01-0000", _TWO_LEG, text="Rowan trims the wick")]
    llm = _Llm("[b1-c01-0000]")
    await ask("Who trims the wick?", retriever=_Retriever(chunks), llm=llm)
    _, prompt = llm.calls[0]
    assert "[b1-c01-0000]" in prompt
    assert "Rowan trims the wick" in prompt
    assert "Who trims the wick?" in prompt


class _StreamLlm(_Llm):
    def stream(self, system: str, prompt: str, *, context=None):
        async def gen():
            for piece in ("Rowan", " trims", " the wick", " [b1-c01-0000]."):
                yield piece

        return gen()


async def test_streaming_forwards_tokens_and_still_grounds():
    chunks = [_chunk("b1-c01-0000", _TWO_LEG)]
    tokens: list[str] = []
    result = await ask(
        "Who trims the wick?",
        retriever=_Retriever(chunks),
        llm=_StreamLlm("unused"),
        on_token=tokens.append,
    )
    assert "".join(tokens) == "Rowan trims the wick [b1-c01-0000]."
    assert result.citations == ["b1-c01-0000"]
    assert result.abstained is False
