"""The graph checkpointer keeps a thread across two streamed requests (#30)."""

from __future__ import annotations

import json
import re

from fastapi.testclient import TestClient

from app.agent import build_graph
from app.agent.memory import memory_saver
from app.agent.persona import PERSONAS
from app.api.runtime import Runtime
from app.config import Settings
from app.main import create_app
from app.schemas import Chunk, ChunkMetadata

_TWO_LEG = 2.0 / 61


class _Retriever:
    async def retrieve(self, query: str, top_k: int) -> list[Chunk]:
        return [
            Chunk(
                id="b1-c01-0000",
                text="Remus Lupin taught Defence Against the Dark Arts.",
                metadata=ChunkMetadata(
                    book_num=3,
                    chapter_num=1,
                    book_name="Book 3",
                    chapter_name="Chapter 1",
                ),
                score=_TWO_LEG,
            )
        ]


class _CaptureLlm:
    name = "fake/memory"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, system: str, prompt: str, *, context=None) -> str:
        self.prompts.append(prompt)
        return "Remus Lupin trained Professor Lupin [b1-c01-0000]."

    async def stream(self, system: str, prompt: str, *, context=None):
        self.prompts.append(prompt)
        yield "Remus Lupin trained Professor Lupin [b1-c01-0000]."


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for frame in re.split(r"\r?\n\r?\n", body):
        name = ""
        data = ""
        for line in frame.splitlines():
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                data += line[6:]
        if name and data:
            events.append((name, json.loads(data)))
    return events


def _runtime(retriever: _Retriever, llm: _CaptureLlm) -> Runtime:
    def graph(checkpointer):
        return build_graph(
            retriever,
            llm,
            personas=PERSONAS,
            default_subject="dada",
            checkpointer=checkpointer,
        )

    return Runtime(
        retriever=retriever,
        llm=llm,
        agent=graph(memory_saver()),
        stateless_agent=graph(None),
    )


def _stream(client: TestClient, payload: dict) -> list[tuple[str, dict]]:
    with client.stream("POST", "/v1/chat/stream", json=payload) as response:
        return _parse_sse("".join(response.iter_text()))


def _mode(events: list[tuple[str, dict]]) -> str:
    return [data for name, data in events if name == "mode"][0]["mode"]


def _final(events: list[tuple[str, dict]]) -> dict:
    return [data for name, data in events if name == "final"][0]


def _client(retriever: _Retriever, llm: _CaptureLlm) -> TestClient:
    app = create_app(
        app_settings=Settings(session_secret="memory-test-secret"),
        runtime=_runtime(retriever, llm),
    )
    return TestClient(app)


def test_thread_memory_resolves_a_pronoun_across_requests():
    retriever = _Retriever()
    llm = _CaptureLlm()
    with _client(retriever, llm) as client:
        first = _stream(
            client,
            {"question": "Who is Professor Lupin?", "thread_id": "thread-memory-1"},
        )
        second = _stream(
            client,
            {"question": "who trained him?", "thread_id": "thread-memory-1"},
        )
    assert _mode(first) == "answer"
    assert _mode(second) == "answer"
    assert "Professor Lupin" in llm.prompts[1]
    assert "who trained him?" not in llm.prompts[1]
    assert _final(second)["thread_id"] == "thread-memory-1"


def test_threads_are_isolated():
    retriever = _Retriever()
    llm = _CaptureLlm()
    with _client(retriever, llm) as client:
        _stream(
            client,
            {"question": "Who is Professor Lupin?", "thread_id": "thread-alpha"},
        )
        _stream(
            client,
            {"question": "Who is Sirius Black?", "thread_id": "thread-beta"},
        )
        _stream(
            client,
            {"question": "who trained him?", "thread_id": "thread-beta"},
        )
        beta_prompt = llm.prompts[-1]
        _stream(
            client,
            {"question": "who trained him?", "thread_id": "thread-alpha"},
        )
        alpha_prompt = llm.prompts[-1]
    assert "who trained Sirius Black?" in beta_prompt
    assert "who trained Professor Lupin?" not in beta_prompt
    assert "who trained Professor Lupin?" in alpha_prompt


def test_a_practice_turn_is_remembered():
    retriever = _Retriever()
    llm = _CaptureLlm()
    with _client(retriever, llm) as client:
        first = _stream(
            client,
            {
                "question": "Give me a practice question on Boggarts.",
                "mode": "practice",
                "thread_id": "thread-practice",
            },
        )
        _stream(
            client,
            {"question": "what about a Dementor?", "thread_id": "thread-practice"},
        )
    assert _mode(first) == "practice"
    assert "Tell me about a Dementor." in llm.prompts[-1]


def test_a_stateless_request_does_not_use_the_checkpointer():
    retriever = _Retriever()
    llm = _CaptureLlm()
    with _client(retriever, llm) as client:
        events = _stream(client, {"question": "What about a Dementor?"})
    assert _mode(events) == "answer"
    assert _final(events)["thread_id"] == ""
    assert "What about a Dementor?" in llm.prompts[-1]


def test_the_context_does_not_grow_the_prompt():
    retriever = _Retriever()
    llm = _CaptureLlm()
    with _client(retriever, llm) as client:
        for _ in range(8):
            _stream(
                client,
                {"question": "What is a Boggart?", "thread_id": "thread-budget"},
            )
    lengths = {len(prompt) for prompt in llm.prompts}
    assert len(lengths) == 1


def test_an_invalid_thread_id_is_rejected():
    retriever = _Retriever()
    llm = _CaptureLlm()
    with _client(retriever, llm) as client:
        response = client.post(
            "/v1/chat/stream",
            json={"question": "What is a Boggart?", "thread_id": "bad id!"},
        )
    assert response.status_code == 422
