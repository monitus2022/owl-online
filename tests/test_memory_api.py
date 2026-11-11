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


def test_thread_memory_resolves_a_pronoun_across_requests():
    retriever = _Retriever()
    llm = _CaptureLlm()
    graph = build_graph(
        retriever,
        llm,
        personas=PERSONAS,
        default_subject="dada",
        checkpointer=memory_saver(),
    )
    app = create_app(
        app_settings=Settings(session_secret="memory-test-secret"),
        runtime=Runtime(retriever=retriever, llm=llm, agent=graph),
    )
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/v1/chat/stream",
            json={
                "question": "Who is Professor Lupin?",
                "thread_id": "thread-memory-1",
            },
        ) as response:
            first = "".join(response.iter_text())
        with client.stream(
            "POST",
            "/v1/chat/stream",
            json={
                "question": "who trained him?",
                "thread_id": "thread-memory-1",
            },
        ) as response:
            second = "".join(response.iter_text())
    first_events = _parse_sse(first)
    second_events = _parse_sse(second)
    assert [data for name, data in first_events if name == "mode"][0]["mode"] == "answer"
    assert [data for name, data in second_events if name == "mode"][0]["mode"] == "answer"
    assert "Professor Lupin" in llm.prompts[1]
    assert "who trained him?" not in llm.prompts[1]
    final = [data for name, data in second_events if name == "final"][0]
    assert final["thread_id"] == "thread-memory-1"
