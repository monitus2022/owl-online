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
        self.top_k_values: list[int] = []

    async def retrieve(self, query: str, top_k: int) -> list[Chunk]:
        self.queries.append(query)
        self.top_k_values.append(top_k)
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
    assert [chunk.id for chunk in state["chunks"]] == ["b1-c01-0000"]
    assert state["attempts"] == 1


async def test_answer_honors_state_top_k():
    retriever = _Retriever()
    graph = build_graph(retriever, _Llm("Rowan trims the wick [b1-c01-0000]."))
    await graph.ainvoke(
        {
            "question": "Who trims the wick?",
            "requested_mode": "answer",
            "student_answer": None,
            "top_k": 2,
        }
    )
    assert retriever.top_k_values == [2]


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


async def test_feedback_without_an_answer_requests_input():
    retriever = _Retriever()
    graph = build_graph(retriever, _Llm("should not run"))
    state = await graph.ainvoke(
        {
            "question": "Give me feedback on this answer",
            "requested_mode": "feedback",
            "student_answer": None,
            "top_k": 5,
        }
    )
    assert state["needs_input"] is True
    assert state["abstained"] is False
    assert state["citations"] == []
    assert retriever.queries == []


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


class _RetryLlm(_Llm):
    """A draft without a citation first, then a grounded one."""

    def __init__(self) -> None:
        super().__init__("unused")
        self.drafts = 0

    def stream(self, system: str, prompt: str, *, context=None):
        self.drafts += 1
        text = (
            "Rowan trims the wick."
            if self.drafts == 1
            else "Rowan trims the wick [b1-c01-0000]."
        )

        async def gen():
            for piece in re.findall(r"\S+\s*", text):
                yield piece

        return gen()


async def test_answer_retries_an_uncited_draft_once():
    graph = build_graph(_Retriever(), _RetryLlm())
    state = await graph.ainvoke(
        {
            "question": "Who trims the wick?",
            "requested_mode": "answer",
            "student_answer": None,
            "top_k": 5,
        }
    )
    assert state["attempts"] == 2
    assert state["retry_reason"] == "uncited"
    assert state["citations"] == ["b1-c01-0000"]
    assert state["abstained"] is False


async def test_stream_emits_reset_between_the_two_drafts():
    graph = build_graph(_Retriever(), _RetryLlm())
    events: list[dict] = []
    async for mode, chunk in graph.astream(
        {
            "question": "Who trims the wick?",
            "requested_mode": "answer",
            "student_answer": None,
            "top_k": 5,
        },
        stream_mode=["custom", "updates"],
    ):
        if mode == "custom":
            events.append(chunk)
    kinds = [event.get("type") for event in events]
    assert kinds.count("reset") == 1
    reset_at = kinds.index("reset")
    before = "".join(
        event["text"] for event in events[:reset_at] if event.get("type") == "token"
    )
    after = "".join(
        event["text"] for event in events[reset_at:] if event.get("type") == "token"
    )
    assert before == "Rowan trims the wick."
    assert after == "Rowan trims the wick [b1-c01-0000]."


class _AlwaysUncitedLlm(_Llm):
    """Every draft answers without a citation, so both drafts fail."""

    def __init__(self) -> None:
        super().__init__("unused")

    def stream(self, system: str, prompt: str, *, context=None):
        async def gen():
            for piece in re.findall(r"\S+\s*", "Rowan trims the wick."):
                yield piece

        return gen()


async def test_budget_exhaustion_abstains_at_the_graph_level():
    graph = build_graph(_Retriever(), _AlwaysUncitedLlm())
    state = await graph.ainvoke(
        {
            "question": "Who trims the wick?",
            "requested_mode": "answer",
            "student_answer": None,
            "top_k": 5,
        }
    )
    assert state["abstained"] is True
    assert state["attempts"] == 2
    assert state["retry_reason"] == "uncited"
    assert state["citations"] == []
