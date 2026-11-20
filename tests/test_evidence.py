"""Operator-only evidence (#295): present only with OWL_DEV_EVIDENCE."""

import json

from fastapi.testclient import TestClient

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
                text="Rowan trims the wick.",
                metadata=ChunkMetadata(
                    book_num=1,
                    chapter_num=1,
                    book_name="Book 1",
                    chapter_name="Chapter 1",
                ),
                score=_TWO_LEG,
            )
        ]


class _Llm:
    async def generate(self, system: str, prompt: str, *, context=None) -> str:
        return "Rowan trims the wick [b1-c01-0000]."

    async def stream(self, system: str, prompt: str, *, context=None):
        yield "Rowan trims the wick [b1-c01-0000]."


def _client(dev_evidence: bool) -> TestClient:
    app = create_app(
        app_settings=Settings(dev_evidence=dev_evidence),
        runtime=Runtime(retriever=_Retriever(), llm=_Llm()),
    )
    return TestClient(app)


def _final(client: TestClient) -> dict[str, object]:
    with client.stream(
        "POST", "/v1/chat/stream", json={"question": "Who trims the wick?"}
    ) as response:
        events = [
            line.removeprefix("data: ")
            for line in response.iter_lines()
            if line.startswith("data: ")
        ]
    finals = [
        json.loads(event)
        for event in events
        if '"answer"' in event and '"abstained"' in event
    ]
    assert finals
    return finals[-1]


def test_dev_evidence_is_off_by_default() -> None:
    assert Settings().dev_evidence is False


def test_chat_response_omits_evidence_when_disabled() -> None:
    with _client(False) as client:
        body = client.post(
            "/v1/chat", json={"question": "Who trims the wick?"}
        ).json()
    assert "evidence" not in body


def test_chat_response_carries_evidence_when_enabled() -> None:
    with _client(True) as client:
        body = client.post(
            "/v1/chat", json={"question": "Who trims the wick?"}
        ).json()
    evidence = body["evidence"]
    assert evidence["chunks"][0]["id"] == "b1-c01-0000"
    assert evidence["chunks"][0]["text"] == "Rowan trims the wick."
    assert evidence["chunks"][0]["score"] > 0
    assert evidence["prompt_sha256"]
    assert evidence["prompt_chars"] > 0
    assert evidence["attempts"] == 1
    assert evidence["abstained"] is False


def test_stream_omits_evidence_when_disabled() -> None:
    with _client(False) as client:
        assert "evidence" not in _final(client)


def test_stream_carries_evidence_when_enabled() -> None:
    with _client(True) as client:
        evidence = _final(client)["evidence"]
    assert evidence["chunks"][0]["text"] == "Rowan trims the wick."
    assert evidence["prompt_sha256"]
