"""Graph end-to-end tests: every route returns a grounded state, no network."""

import re

from app.agent import build_graph
from app.schemas import Chunk, ChunkMetadata

_TWO_LEG = 2.0 / 61


def _chunk(cid: str = "b1-c01-0000") -> Chunk:
    return Chunk(
        id=cid,
        text="Rowan trims the wick.",
        metadata=ChunkMetadata(
            book_num=1, chapter_num=1, book_name="Book 1", chapter_name="Chapter 1"
        ),
        score=_TWO_LEG,
    )


class _Retriever:
    def __init__(self, chunks: list[Chunk] | None = None) -> None:
        self._chunks = chunks if chunks is not None else [_chunk()]
        self.queries: list[str] = []

    async def retrieve(self, query: str, top_k: int) -> list[Chunk]:
        self.queries.append(query)
        return self._chunks[:top_k]


class _Llm:
    def __init__(self, text: str) -> None:
        self.text = text

    async def generate(self, system: str, prompt: str, *, context=None) -> str:
        return self.text

    def stream(self, system: str, prompt: str, *, context=None):
        async def gen():
            for piece in re.findall(r"\S+\s*", self.text):
                yield piece

        return gen()


async def test_answer_route_grounds_and_cites():
    graph = build_graph(_Retriever(), _Llm("Rowan trims the wick [b1-c01-0000]."))
    state = await graph.ainvoke(
        {
            "question": "Who trims the wick?",
            "requested_mode": "auto",
            "student_answer": None,
            "top_k": 5,
        }
    )
    assert state["mode"] == "answer"
    assert state["abstained"] is False
    assert state["citations"] == ["b1-c01-0000"]


async def test_practice_route_returns_cited_practice_material():
    graph = build_graph(
        _Retriever(),
        _Llm("Practice question: Who trims the wick? [b1-c01-0000]\nAnswer: Rowan."),
    )
    state = await graph.ainvoke(
        {
            "question": "Give me a practice question about the wick",
            "requested_mode": "auto",
            "student_answer": None,
            "top_k": 5,
        }
    )
    assert state["mode"] == "practice"
    assert state["citations"] == ["b1-c01-0000"]
    assert state["abstained"] is False


async def test_feedback_route_uses_the_student_answer():
    graph = build_graph(
        _Retriever(),
        _Llm("8/10. Correct keeper, missing detail. [b1-c01-0000]"),
    )
    state = await graph.ainvoke(
        {
            "question": "Give me feedback on this answer",
            "requested_mode": "auto",
            "student_answer": "Rowan trims the wick.",
            "top_k": 5,
        }
    )
    assert state["mode"] == "feedback"
    assert state["citations"] == ["b1-c01-0000"]
    assert state["abstained"] is False


async def test_feedback_retrieves_with_the_student_answer():
    retriever = _Retriever()
    graph = build_graph(retriever, _Llm("8/10. [b1-c01-0000]"))
    await graph.ainvoke(
        {
            "question": "Give me feedback on this answer",
            "requested_mode": "auto",
            "student_answer": "Rowan trims the wick.",
            "top_k": 5,
        }
    )
    assert "Rowan trims the wick." in retriever.queries[0]


async def test_feedback_without_an_answer_abstains_without_retrieval():
    graph = build_graph(_Retriever(), _Llm("should not run"))
    state = await graph.ainvoke(
        {
            "question": "Give me feedback on this answer",
            "requested_mode": "feedback",
            "student_answer": None,
            "top_k": 5,
        }
    )
    assert state["abstained"] is True
    assert state["citations"] == []


async def test_graph_streams_custom_token_events():
    text = "Rowan trims the wick [b1-c01-0000]."
    graph = build_graph(_Retriever(), _Llm(text))
    tokens: list[str] = []
    async for mode, chunk in graph.astream(
        {
            "question": "Who trims the wick?",
            "requested_mode": "answer",
            "student_answer": None,
            "top_k": 5,
        },
        stream_mode=["custom", "updates"],
    ):
        if mode == "custom" and chunk.get("type") == "token":
            tokens.append(chunk["text"])
    assert "".join(tokens) == text
