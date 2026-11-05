"""Cost controls at the HTTP edge: burst, cache, budget and usage logs."""

import json
import logging

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
                    book_num=1, chapter_num=1, book_name="Book 1", chapter_name="Ch1"
                ),
                score=_TWO_LEG,
            )
        ]


class _Llm:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, system: str, prompt: str, *, context=None) -> str:
        self.calls += 1
        return "Rowan trims the wick [b1-c01-0000]."

    def stream(self, system: str, prompt: str, *, context=None):
        self.calls += 1

        async def gen():
            for piece in ("Rowan", " trims", " the wick", " [b1-c01-0000]."):
                yield piece

        return gen()


def _client(llm: _Llm, **overrides) -> TestClient:
    app = create_app(
        app_settings=Settings(**overrides),
        runtime=Runtime(retriever=_Retriever(), llm=llm),
    )
    return TestClient(app)


def _sse_events(body: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    name = "message"
    data = ""
    for line in body.splitlines():
        if line.startswith("event: "):
            name = line[7:].strip()
        elif line.startswith("data: "):
            data += line[6:]
        elif not line.strip() and data:
            events.append((name, json.loads(data)))
            name, data = "message", ""
    return events


def test_burst_returns_429_with_retry_after():
    llm = _Llm()
    with _client(llm, chat_per_minute=2) as client:
        questions = ("Who trims?", "Who keeps the lighthouse?", "Who is the keeper?")
        statuses = [
            client.post("/ask", json={"question": question}).status_code
            for question in questions
        ]
        response = client.post("/ask", json={"question": "Who else?"})
    assert statuses == [200, 200, 429]
    assert response.status_code == 429
    assert response.headers["retry-after"]
    assert response.json()["reason"] == "minute"
    assert llm.calls == 2


def test_repeated_question_is_served_from_cache_and_logged(caplog):
    caplog.set_level(logging.INFO)
    llm = _Llm()
    with _client(llm) as client:
        first = client.post("/ask", json={"question": "Who trims the wick?"}).json()
        second = client.post("/ask", json={"question": "who trims the wick"}).json()
    assert first == second
    assert llm.calls == 1
    assert "cache=True" in caplog.text
    assert "chat usage" in caplog.text
    assert "in_tokens=" in caplog.text and "cost_usd=" in caplog.text


def test_feedback_is_not_served_from_the_shared_cache():
    llm = _Llm()
    with _client(llm) as client:
        client.post("/ask", json={"question": "Give me feedback on this answer"})
        for answer in ("Rowan trims the wick.", "Rowan does not trim the wick."):
            with client.stream(
                "POST",
                "/ask/stream",
                json={
                    "question": "Give me feedback on this answer",
                    "student_answer": answer,
                },
            ) as response:
                response.read()
    assert llm.calls == 3


def test_budget_degrades_chat_but_health_stays_up():
    llm = _Llm()
    with _client(llm, chat_daily_token_budget=5) as client:
        assert client.post("/ask", json={"question": "Who trims?"}).status_code == 200
        second = client.post("/ask", json={"question": "Who trims the wick?"})
        assert second.status_code == 503
        assert second.json()["reason"] == "budget"
        assert client.get("/health").status_code == 200


def test_rate_limited_requests_do_not_call_the_model():
    llm = _Llm()
    with _client(llm, chat_per_minute=1) as client:
        client.post("/ask", json={"question": "Who trims?"})
        second = client.post("/ask", json={"question": "Who trims the wick?"})
    assert second.status_code == 429
    assert llm.calls == 1


def test_stream_answer_hits_the_cache_on_repeat():
    llm = _Llm()
    with _client(llm) as client:
        bodies = []
        for question in ("Who trims the wick?", "who trims the wick"):
            with client.stream(
                "POST", "/ask/stream", json={"question": question}
            ) as response:
                bodies.append("".join(response.iter_text()))
    finals = [_sse_events(body)[-1] for body in bodies]
    assert finals[0][0] == "final" and finals[1][0] == "final"
    assert llm.calls == 1


def test_forged_session_header_does_not_bypass_the_cookie_session():
    llm = _Llm()
    with _client(llm, chat_per_minute=1) as client:
        assert (
            client.post(
                "/ask",
                json={"question": "Who trims the wick?"},
                headers={"X-Session-ID": "forged-one-1234"},
            ).status_code
            == 200
        )
        second = client.post(
            "/ask",
            json={"question": "Who keeps the lighthouse?"},
            headers={"X-Session-ID": "forged-two-5678"},
        )
    assert second.status_code == 429
    assert second.json()["reason"] == "minute"


def test_cached_answer_is_served_after_the_budget_is_exhausted():
    llm = _Llm()
    with _client(llm, chat_daily_token_budget=5) as client:
        assert client.post("/ask", json={"question": "Who trims?"}).status_code == 200
        repeat = client.post("/ask", json={"question": "Who trims?"})
    assert repeat.status_code == 200
    assert llm.calls == 1


def test_stream_records_usage_once(caplog):
    caplog.set_level(logging.INFO)
    llm = _Llm()
    with _client(llm) as client:
        with client.stream(
            "POST", "/ask/stream", json={"question": "Who trims the wick?"}
        ) as response:
            response.read()
    assert caplog.text.count("chat usage") == 1
    assert llm.calls == 1


def test_forged_cookie_is_replaced():
    llm = _Llm()
    with _client(llm) as client:
        client.cookies.clear()
        response = client.post(
            "/ask",
            json={"question": "Who trims?"},
            headers={"Cookie": "owl_session=forged.deadbeef"},
        )
    assert response.status_code == 200
    assert "set-cookie" in response.headers


def test_cached_stream_records_one_usage_line(caplog):
    caplog.set_level(logging.INFO)
    llm = _Llm()
    with _client(llm) as client:
        with client.stream(
            "POST", "/ask/stream", json={"question": "Who trims the wick?"}
        ) as response:
            response.read()
        caplog.clear()
        with client.stream(
            "POST", "/ask/stream", json={"question": "who trims the wick"}
        ) as response:
            response.read()
    assert caplog.text.count("chat usage") == 1
    assert "cache=True" in caplog.text
    assert llm.calls == 1


def test_cookie_is_httponly_and_cross_site_on_tls():
    llm = _Llm()
    with _client(llm) as client:
        client.cookies.clear()
        response = client.post(
            "/ask",
            json={"question": "Who trims?"},
            headers={"X-Forwarded-Proto": "https"},
        )
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=none" in cookie
    assert "secure" in cookie
