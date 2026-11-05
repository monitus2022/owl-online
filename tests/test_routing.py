"""Intent routing: practice/feedback use the small model, answer stays strong."""

import pytest

from app.agent import build_graph
from app.providers.errors import ProviderError
from app.providers.policy import ensure_allowed_model
from app.schemas import Chunk, ChunkMetadata

_TWO_LEG = 2.0 / 61


class _Retriever:
    async def retrieve(self, query: str, top_k: int) -> list[Chunk]:
        return [
            Chunk(
                id="b1-c01-0000",
                text="Rowan trims the wick.",
                metadata=ChunkMetadata(
                    book_num=1, chapter_num=1, book_name="Book 1", chapter_name="Ch1"
                ),
                score=_TWO_LEG,
            )
        ]


class _Llm:
    def __init__(self, name: str, text: str, *, fail: bool = False) -> None:
        self.name = name
        self.text = text
        self.fail = fail
        self.calls = 0

    def stream(self, system: str, prompt: str, *, context=None):
        self.calls += 1

        async def gen():
            if self.fail:
                raise ProviderError("down")
            for piece in self.text.split(" "):
                yield piece + " "

        return gen()


def _request(question: str, *, mode: str = "auto", student: str | None = None) -> dict:
    return {
        "question": question,
        "requested_mode": mode,
        "student_answer": student,
        "top_k": 5,
    }


async def test_practice_uses_the_small_model():
    strong = _Llm("strong", "Strong [b1-c01-0000].")
    small = _Llm("small", "Small [b1-c01-0000].")
    graph = build_graph(_Retriever(), strong, small_llm=small)
    state = await graph.ainvoke(_request("Give me a practice question on the wick"))
    assert state["mode"] == "practice"
    assert small.calls == 1
    assert strong.calls == 0


async def test_answer_stays_on_the_strong_model():
    strong = _Llm("strong", "Strong [b1-c01-0000].")
    small = _Llm("small", "Small [b1-c01-0000].")
    graph = build_graph(_Retriever(), strong, small_llm=small)
    await graph.ainvoke(_request("Who trims the wick?"))
    assert strong.calls == 1
    assert small.calls == 0


async def test_feedback_uses_the_small_model():
    strong = _Llm("strong", "Strong [b1-c01-0000].")
    small = _Llm("small", "Small [b1-c01-0000].")
    graph = build_graph(_Retriever(), strong, small_llm=small)
    await graph.ainvoke(_request("Give me feedback", student="Rowan trims the wick."))
    assert small.calls == 1
    assert strong.calls == 0


class _PartialThenFailLlm(_Llm):
    def stream(self, system: str, prompt: str, *, context=None):
        self.calls += 1

        async def gen():
            yield "Partial draft "
            raise ProviderError("down")

        return gen()


async def test_fallback_clears_the_partial_draft():
    strong = _Llm("strong", "Strong [b1-c01-0000].")
    small = _PartialThenFailLlm("small", "unused")
    graph = build_graph(_Retriever(), strong, small_llm=small)
    events = []
    async for mode, chunk in graph.astream(
        _request("Give me a practice question on the wick"),
        stream_mode=["custom", "updates"],
    ):
        if mode == "custom":
            events.append(chunk)
    kinds = [event.get("type") for event in events]
    assert "reset" in kinds
    assert kinds.index("reset") > 0  # after the partial token
    assert any(
        event.get("type") == "token" and "Strong" in event.get("text", "")
        for event in events
    )


async def test_provider_failure_falls_back_to_the_strong_model():
    strong = _Llm("strong", "Strong [b1-c01-0000].")
    small = _Llm("small", "Small [b1-c01-0000].", fail=True)
    graph = build_graph(_Retriever(), strong, small_llm=small)
    state = await graph.ainvoke(_request("Give me a practice question on the wick"))
    assert state["citations"] == ["b1-c01-0000"]
    assert small.calls == 1
    assert strong.calls == 1


def test_banned_vendors_are_rejected():
    for slug in (
        "openai/gpt-oss-20b",
        "google/gemma-4-26b-a4b-it",
        "anthropic/claude-sonnet",
        "qwen/qwen3-30b-a3b-instruct-2507",
        "mistralai/mistral-small-3.2-24b-instruct",
    ):
        if slug.startswith(("qwen", "mistral")):
            ensure_allowed_model(slug)
        else:
            with pytest.raises(ValueError):
                ensure_allowed_model(slug)
