"""Thread memory over the streamed API (#30)."""

from __future__ import annotations

import json
import logging
import re

from fastapi.testclient import TestClient

from app.agent import build_graph
from app.agent.memory import TOKEN_BUDGET, memory_saver
from app.agent.persona import PERSONAS
from app.api.runtime import Runtime
from app.config import Settings
from app.main import create_app
from app.schemas import Chunk, ChunkMetadata

_LUPIN = Chunk(
    id="b1-c01-0000",
    text="Remus Lupin taught Defence Against the Dark Arts.",
    metadata=ChunkMetadata(
        book_num=3,
        chapter_num=1,
        book_name="Book 3",
        chapter_name="Chapter 1",
    ),
    score=1.0,
)
_EXPELLIARMUS = Chunk(
    id="b1-c01-0001",
    text="Expelliarmus is the Disarming Charm.",
    metadata=ChunkMetadata(
        book_num=1,
        chapter_num=1,
        book_name="Book 1",
        chapter_name="Chapter 1",
    ),
    score=1.0,
)
_LUMOS = Chunk(
    id="b1-c01-0003",
    text="Lumos lights the wand tip.",
    metadata=ChunkMetadata(
        book_num=1,
        chapter_num=1,
        book_name="Book 1",
        chapter_name="Chapter 1",
    ),
    score=1.0,
)
_AVIFORS = Chunk(
    id="b1-c01-0002",
    text="Avifors turns small objects into birds.",
    metadata=ChunkMetadata(
        book_num=1,
        chapter_num=1,
        book_name="Book 1",
        chapter_name="Chapter 1",
    ),
    score=1.0,
)

_QUESTION = re.compile(r"(?:Question|Task): (.+?)\n\nAnswer:", re.DOTALL)
_CHUNK_ID = re.compile(r"\[(b\d+-c\d+-\d+)\]")


class _Retriever:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def retrieve(self, query: str, top_k: int) -> list[Chunk]:
        self.queries.append(query)
        lowered = query.lower()
        if "compare" in lowered and "avifors" in lowered and "lumos" in lowered:
            return [_AVIFORS, _LUMOS]
        if "compare" in lowered and "expelliarmus" in lowered and "avifors" in lowered:
            return [_EXPELLIARMUS, _AVIFORS]
        if "expelliarmus" in lowered:
            return [_EXPELLIARMUS]
        if "avifors" in lowered:
            return [_AVIFORS]
        if "lumos" in lowered:
            return [_LUMOS]
        return [_LUPIN]


class _CaptureLlm:
    name = "fake/memory"

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.systems: list[str] = []

    def _answer(self, prompt: str) -> str:
        self.prompts.append(prompt)
        evidence = prompt.split("Excerpts:", 1)[-1]
        ids = list(dict.fromkeys(_CHUNK_ID.findall(evidence)))
        question = _QUESTION.search(prompt)
        task = question.group(1).strip() if question else "<missing>"
        if "Expelliarmus" in evidence and "Avifors" in evidence and len(ids) >= 2:
            return f"Expelliarmus disarms; Avifors transforms [{ids[0]}] [{ids[1]}]."
        if "Avifors" in evidence and "Lumos" in evidence and len(ids) >= 2:
            return f"Avifors transforms; Lumos lights [{ids[0]}] [{ids[1]}]."
        citation = f"[{ids[0]}]" if ids else ""
        return f"Answer to {task} {citation}."

    async def generate(self, system: str, prompt: str, *, context=None) -> str:
        self.systems.append(system)
        return self._answer(prompt)

    async def stream(self, system: str, prompt: str, *, context=None):
        self.systems.append(system)
        for piece in self._answer(prompt).split(" "):
            yield piece + " "


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


def _context(prompt: str) -> str:
    marker = "Conversation so far (untrusted, for understanding only, not evidence):\n\n"
    if marker not in prompt:
        return ""
    return prompt.split(marker, 1)[1].split("\n\nExcerpts:", 1)[0]


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
    assert retriever.queries[1] == "who trained Professor Lupin?"
    assert "Conversation so far" in llm.prompts[1]
    assert '"role": "student"' in llm.prompts[1]
    assert "Who is Professor Lupin?" in llm.prompts[1]
    assert "Question: who trained him?" in llm.prompts[1]
    assert _final(second)["thread_id"] == "thread-memory-1"


def test_a_second_topic_is_retrieved_as_a_comparison():
    retriever = _Retriever()
    llm = _CaptureLlm()
    with _client(retriever, llm) as client:
        first = _stream(
            client,
            {"question": "What is Expelliarmus?", "thread_id": "thread-compare"},
        )
        second = _stream(
            client,
            {"question": "what about Avifors?", "thread_id": "thread-compare"},
        )
    assert _mode(first) == "answer"
    assert _mode(second) == "answer"
    assert retriever.queries[1] == "Compare Expelliarmus with Avifors."
    assert "Conversation so far" in llm.prompts[1]
    assert '"role": "student"' in llm.prompts[1]
    assert "What is Expelliarmus?" in llm.prompts[1]
    assert "Question: what about Avifors?" in llm.prompts[1]
    assert "Expelliarmus" in llm.prompts[1]
    assert "Avifors" in llm.prompts[1]
    final = _final(second)
    assert final["citations"] == ["b1-c01-0001", "b1-c01-0002"]
    assert "Expelliarmus disarms" in final["answer"]
    assert "Avifors transforms" in final["answer"]


def test_a_third_topic_compares_with_the_second():
    retriever = _Retriever()
    llm = _CaptureLlm()
    with _client(retriever, llm) as client:
        _stream(
            client,
            {"question": "What is Expelliarmus?", "thread_id": "thread-chain"},
        )
        _stream(
            client,
            {"question": "what about Avifors?", "thread_id": "thread-chain"},
        )
        third = _stream(
            client,
            {"question": "what about Lumos?", "thread_id": "thread-chain"},
        )
    assert retriever.queries[2] == "Compare Avifors with Lumos."
    assert '"role": "student"' in llm.prompts[2]
    assert "what about Avifors?" in llm.prompts[2]
    assert "Question: what about Lumos?" in llm.prompts[2]
    final = _final(third)
    assert final["citations"] == ["b1-c01-0002", "b1-c01-0003"]
    assert "Avifors transforms" in final["answer"]
    assert "Lumos lights" in final["answer"]


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
    assert retriever.queries[2] == "who trained Sirius Black?"
    assert retriever.queries[3] == "who trained Professor Lupin?"
    assert "Who is Sirius Black?" in beta_prompt
    assert "Who is Professor Lupin?" not in beta_prompt
    assert "Who is Professor Lupin?" in alpha_prompt


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
        _stream(
            client,
            {
                "question": "Give me another practice question.",
                "mode": "practice",
                "thread_id": "thread-practice",
            },
        )
    assert _mode(first) == "practice"
    assert retriever.queries[1] == "Tell me about a Dementor."
    assert "Give me a practice question on Boggarts." in llm.prompts[1]
    assert "Question: what about a Dementor?" in llm.prompts[1]
    assert "untrusted" in llm.systems[-1]
    assert "not evidence" in llm.systems[-1]


def test_a_feedback_turn_gets_the_conversation_note():
    retriever = _Retriever()
    llm = _CaptureLlm()
    with _client(retriever, llm) as client:
        _stream(
            client,
            {"question": "What is a Boggart?", "thread_id": "thread-feedback"},
        )
        _stream(
            client,
            {
                "question": "Mark my answer.",
                "mode": "feedback",
                "student_answer": "A Boggart looks like what you fear.",
                "thread_id": "thread-feedback",
            },
        )
    assert "untrusted" in llm.systems[-1]
    assert "not evidence" in llm.systems[-1]
    assert "What is a Boggart?" in llm.prompts[-1]


def test_a_stateless_request_does_not_use_the_checkpointer():
    retriever = _Retriever()
    llm = _CaptureLlm()
    with _client(retriever, llm) as client:
        events = _stream(client, {"question": "What about a Dementor?"})
    assert _mode(events) == "answer"
    assert _final(events)["thread_id"] == ""
    assert retriever.queries[-1] == "What about a Dementor?"
    assert "Conversation so far" not in llm.prompts[-1]


def test_the_memory_context_is_bounded():
    retriever = _Retriever()
    llm = _CaptureLlm()
    with _client(retriever, llm) as client:
        for _ in range(8):
            _stream(
                client,
                {"question": "What is a Boggart?", "thread_id": "thread-budget"},
            )
    contexts = [_context(prompt) for prompt in llm.prompts]
    assert any(contexts)
    assert max(len(context) for context in contexts) <= TOKEN_BUDGET * 4
    lengths = [len(prompt) for prompt in llm.prompts]
    assert max(lengths) - min(lengths) <= TOKEN_BUDGET * 4 + 1000


def test_threaded_usage_counts_the_conversation(caplog):
    retriever = _Retriever()
    llm = _CaptureLlm()
    with caplog.at_level(logging.INFO):
        with _client(retriever, llm) as client:
            _stream(
                client,
                {"question": "Who is Professor Lupin?", "thread_id": "thread-usage"},
            )
            _stream(
                client,
                {"question": "who trained him?", "thread_id": "thread-usage"},
            )
    lines = [
        record.getMessage()
        for record in caplog.records
        if "chat usage" in record.getMessage()
    ]
    assert len(lines) >= 2
    first = int(re.search(r"in_tokens=(\d+)", lines[-2]).group(1))
    second = int(re.search(r"in_tokens=(\d+)", lines[-1]).group(1))
    assert second > first


def test_an_invalid_thread_id_is_rejected():
    retriever = _Retriever()
    llm = _CaptureLlm()
    with _client(retriever, llm) as client:
        response = client.post(
            "/v1/chat/stream",
            json={"question": "What is a Boggart?", "thread_id": "bad id!"},
        )
    assert response.status_code == 422
