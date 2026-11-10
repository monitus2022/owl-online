"""Privacy and retention checks (#180): no text in logs, cookie flags, delete."""

from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from app.api.runtime import Runtime
from app.exam.attempts import AttemptQuestion, AttemptRecord
from app.main import create_app
from app.schemas import Chunk, ChunkMetadata
from app.storage.exam_store import ExamStore

_TWO_LEG = 2.0 / 61
PROMPT = "UniquePrivacyPromptQZX"
ANSWER = "UniquePrivacyAnswerQZX"


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
    name = "fake/privacy"

    async def generate(self, system: str, prompt: str, *, context=None) -> str:
        return f"{ANSWER} [b1-c01-0000]."

    async def stream(self, system: str, prompt: str, *, context=None):
        yield f"{ANSWER} [b1-c01-0000]."


def _attempt(attempt_id: str, session: str, created_at: str) -> AttemptRecord:
    return AttemptRecord(
        attempt_id=attempt_id,
        paper_id="paper-1",
        subject="dada",
        bank_version="1.0.0",
        created_at=created_at,
        session_id=session,
        questions=(
            AttemptQuestion(
                position=0,
                item_id="item-1",
                kind="short_answer",
                prompt="A served question?",
                marks=8,
            ),
        ),
    )


def test_prompt_and_answer_text_do_not_reach_logs_or_traces(caplog):
    caplog.set_level(logging.INFO)
    app = create_app(runtime=Runtime(retriever=_Retriever(), llm=_Llm()))
    with TestClient(app) as client:
        body = client.post("/ask", json={"question": PROMPT}).json()
    assert ANSWER in body["answer"]
    messages = [record.getMessage() for record in caplog.records]
    text = "\n".join(messages)
    assert any("chat usage" in message for message in messages)
    assert any('"span":' in message for message in messages)
    assert PROMPT not in text
    assert ANSWER not in text


def test_session_cookie_flags():
    app = create_app(runtime=Runtime(retriever=_Retriever(), llm=_Llm()))
    with TestClient(app) as client:
        response = client.get("/health")
    cookie = response.headers.get("set-cookie", "")
    assert "owl_session=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Max-Age=86400" in cookie


def test_session_cookie_is_cross_site_secure_on_https():
    app = create_app(runtime=Runtime(retriever=_Retriever(), llm=_Llm()))
    with TestClient(app, base_url="https://testserver") as client:
        response = client.get("/health")
    cookie = response.headers.get("set-cookie", "")
    assert "SameSite=none" in cookie
    assert "Secure" in cookie


def test_delete_preflight_allows_the_pages_origin():
    app = create_app(runtime=Runtime(retriever=_Retriever(), llm=_Llm()))
    with TestClient(app) as client:
        response = client.options(
            "/v1/attempts",
            headers={
                "Origin": "https://owl-online.pages.dev",
                "Access-Control-Request-Method": "DELETE",
            },
        )
    assert response.status_code == 200
    methods = response.headers.get("access-control-allow-methods", "")
    assert "DELETE" in methods


def test_delete_attempts_is_session_scoped(tmp_path):
    store = ExamStore(tmp_path / "exams.db")
    app = create_app(
        runtime=Runtime(retriever=_Retriever(), llm=_Llm(), exam_store=store)
    )
    with TestClient(app) as client:
        client.get("/health")
        raw = client.cookies.get("owl_session")
        assert raw is not None
        session = raw.split(".", 1)[0]
        store.create_attempt(_attempt("a1", session, "2026-11-01T00:00:00Z"))
        store.create_attempt(_attempt("a2", "other-session", "2026-11-01T00:00:00Z"))
        response = client.delete("/v1/attempts")
        assert response.status_code == 200
        assert response.json() == {"deleted": 1}
        assert store.attempt("a1") is None
        assert store.attempt("a2") is not None


def test_prune_attempts_by_age(tmp_path):
    with ExamStore(tmp_path / "exams.db") as store:
        store.create_attempt(_attempt("old", "s1", "2020-01-01T00:00:00Z"))
        store.create_attempt(_attempt("new", "s1", "2026-11-01T00:00:00Z"))
        assert store.count_attempts_before("2021-01-01T00:00:00Z") == 1
        assert store.prune_attempts("2021-01-01T00:00:00Z") == 1
        assert store.attempt("old") is None
        assert store.attempt("new") is not None
