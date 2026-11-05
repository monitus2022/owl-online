"""API tests: the /ask endpoint with an injected Runtime, no network."""

import json

from fastapi.testclient import TestClient

from app.api.runtime import Runtime
from app.config import Settings
from app.logging import get_request_id
from app.main import create_app
from app.pipeline.generate import ABSTAIN_MESSAGE
from app.providers.errors import ProviderError
from app.schemas import Chunk, ChunkMetadata

_TWO_LEG = 2.0 / 61  # RRF score above the two-leg abstention floor


class _Retriever:
    async def retrieve(self, query: str, top_k: int) -> list[Chunk]:
        return [
            Chunk(
                id="b1-c01-0000",
                text="Rowan trims the wick.",
                metadata=ChunkMetadata(
                    book_num=1, chapter_num=1, book_name="Book 1", chapter_name="Chapter 1"
                ),
                score=_TWO_LEG,
            )
        ]


class _Llm:
    async def generate(self, system: str, prompt: str, *, context=None) -> str:
        return "Rowan trims the wick [b1-c01-0000]."

    async def stream(self, system: str, prompt: str, *, context=None):
        for piece in ("Rowan", " trims", " the wick", " [b1-c01-0000]."):
            yield piece


class _BoomLlm:
    async def generate(self, system: str, prompt: str, *, context=None) -> str:
        raise ProviderError("upstream down")


class _UncitedLlm(_Llm):
    async def stream(self, system: str, prompt: str, *, context=None):
        for piece in ("Rowan", " trims", " the wick."):
            yield piece


class _WeakRetriever:
    async def retrieve(self, query: str, top_k: int) -> list[Chunk]:
        return []


def _client(runtime: Runtime | None = None) -> TestClient:
    app = create_app(
        app_settings=Settings(retry_budget=1),
        runtime=runtime or Runtime(retriever=_Retriever(), llm=_Llm()),
    )
    return TestClient(app)


def test_health_still_green():
    with _client() as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_ask_returns_grounded_answer_with_citations():
    with _client() as client:
        response = client.post("/ask", json={"question": "Who trims the wick?"})
    assert response.status_code == 200
    body = response.json()
    assert body["abstained"] is False
    assert body["citations"] == ["b1-c01-0000"]
    assert "b1-c01-0000" in body["answer"]


def test_ask_rejects_empty_question():
    with _client() as client:
        response = client.post("/ask", json={"question": ""})
    assert response.status_code == 422


def test_ask_abstains_when_retrieval_is_weak():
    class _WeakRetriever:
        async def retrieve(self, query: str, top_k: int) -> list[Chunk]:
            return []

    runtime = Runtime(retriever=_WeakRetriever(), llm=_Llm())
    with _client(runtime) as client:
        body = client.post("/ask", json={"question": "Who?"}).json()
    assert body["abstained"] is True
    assert body["citations"] == []


def test_provider_error_maps_to_502_without_a_traceback():
    runtime = Runtime(retriever=_Retriever(), llm=_BoomLlm())
    with _client(runtime) as client:
        response = client.post("/ask", json={"question": "Who?"})
    assert response.status_code == 502
    assert "traceback" not in response.text.lower()


def test_chat_page_is_served():
    with _client() as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "O.W.L. Online" in response.text


def test_ask_rejects_a_blank_question():
    with _client() as client:
        response = client.post("/ask", json={"question": "   "})
    assert response.status_code == 422


def test_ask_response_matches_the_typed_schema():
    with _client() as client:
        body = client.post("/ask", json={"question": "Who?"}).json()
    assert set(body) == {"answer", "citations", "abstained"}


def test_response_carries_a_request_id():
    with _client() as client:
        response = client.post("/ask", json={"question": "Who?"})
    assert response.headers.get("x-request-id")


def test_request_id_propagates_into_the_handler():
    """The ContextVar set in the middleware is visible to the endpoint."""
    seen: dict[str, str] = {}

    class _RidRetriever:
        async def retrieve(self, query: str, top_k: int) -> list[Chunk]:
            seen["rid"] = get_request_id()
            return []

    app = create_app(runtime=Runtime(retriever=_RidRetriever(), llm=_Llm()))
    with TestClient(app) as client:
        response = client.post("/ask", json={"question": "q"})
    assert seen["rid"] == response.headers["x-request-id"]
    assert seen["rid"] != "-"


def test_cors_allows_the_pages_origin():
    with _client() as client:
        response = client.get(
            "/health", headers={"Origin": "https://owl-online.pages.dev"}
        )
    assert response.headers.get("access-control-allow-origin") == "https://owl-online.pages.dev"


def test_unexpected_error_returns_500_without_a_traceback():
    class _BoomRetriever:
        async def retrieve(self, query: str, top_k: int) -> list[Chunk]:
            raise RuntimeError("kaboom")

    app = create_app(runtime=Runtime(retriever=_BoomRetriever(), llm=_Llm()))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/ask", json={"question": "q"})
    assert response.status_code == 500
    assert "kaboom" not in response.text
    assert "traceback" not in response.text.lower()


def test_runtime_builds_the_graph_once():
    app = create_app(runtime=Runtime(retriever=_Retriever(), llm=_Llm()))
    with TestClient(app) as client:
        first = app.state.runtime.agent
        assert first is not None
        client.post("/ask/stream", json={"question": "Who trims the wick?"})
        assert app.state.runtime.agent is first


def _parse_sse(body: str) -> list[tuple[str, dict]]:
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
    if data:
        events.append((name, json.loads(data)))
    return events


def test_ask_stream_emits_tokens_then_a_grounded_final():
    with _client() as client:
        with client.stream(
            "POST", "/ask/stream", json={"question": "Who trims the wick?"}
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            body = "".join(response.iter_text())

    events = _parse_sse(body)
    tokens = [data["text"] for name, data in events if name == "token"]
    finals = [data for name, data in events if name == "final"]
    modes = [data for name, data in events if name == "mode"]
    assert "".join(tokens) == "Rowan trims the wick [b1-c01-0000]."
    assert finals[0]["citations"] == ["b1-c01-0000"]
    assert finals[0]["abstained"] is False
    assert finals[0]["attempts"] == 1
    assert modes[0]["mode"] == "answer"


def test_ask_stream_resets_an_uncited_draft():
    runtime = Runtime(retriever=_Retriever(), llm=_UncitedLlm())
    with _client(runtime) as client:
        with client.stream(
            "POST", "/ask/stream", json={"question": "Who trims the wick?"}
        ) as response:
            body = "".join(response.iter_text())
    events = _parse_sse(body)
    names = [name for name, _ in events]
    finals = [data for name, data in events if name == "final"]
    assert "reset" in names
    assert names.index("reset") < names.index("final")
    assert finals[0]["abstained"] is True
    assert finals[0]["answer"] == ABSTAIN_MESSAGE


def test_ask_stream_abstains_when_retrieval_is_weak():
    runtime = Runtime(retriever=_WeakRetriever(), llm=_Llm())
    with _client(runtime) as client:
        with client.stream(
            "POST", "/ask/stream", json={"question": "Who trims the wick?"}
        ) as response:
            body = "".join(response.iter_text())
    events = _parse_sse(body)
    finals = [data for name, data in events if name == "final"]
    assert finals[0]["abstained"] is True
    assert finals[0]["citations"] == []


def test_ask_stream_rejects_a_blank_question():
    with _client() as client:
        response = client.post("/ask/stream", json={"question": "   "})
    assert response.status_code == 422


def test_ask_stream_routes_a_practice_request():
    with _client() as client:
        with client.stream(
            "POST",
            "/ask/stream",
            json={"question": "Give me a practice question on the wick"},
        ) as response:
            body = "".join(response.iter_text())
    events = _parse_sse(body)
    finals = [data for name, data in events if name == "final"]
    assert finals[0]["mode"] == "practice"


def test_ask_stream_routes_feedback_when_a_student_answer_is_present():
    with _client() as client:
        with client.stream(
            "POST",
            "/ask/stream",
            json={
                "question": "Give me feedback on this answer",
                "student_answer": "Rowan trims the wick.",
            },
        ) as response:
            body = "".join(response.iter_text())
    events = _parse_sse(body)
    finals = [data for name, data in events if name == "final"]
    assert finals[0]["mode"] == "feedback"


def test_ask_stream_rejects_the_old_generate_mode():
    with _client() as client:
        response = client.post(
            "/ask/stream", json={"question": "Generate a quiz", "mode": "generate"}
        )
    assert response.status_code == 422


def test_ask_stream_reports_missing_feedback_answer():
    with _client() as client:
        with client.stream(
            "POST",
            "/ask/stream",
            json={"question": "Give me feedback on this answer", "mode": "feedback"},
        ) as response:
            body = "".join(response.iter_text())
    events = _parse_sse(body)
    names = [name for name, _ in events]
    finals = [data for name, data in events if name == "final"]
    assert "reset" not in names
    assert finals[0]["needs_input"] is True
    assert finals[0]["abstained"] is False


def test_ask_stream_rejects_student_answer_outside_feedback_mode():
    with _client() as client:
        response = client.post(
            "/ask/stream",
            json={
                "question": "Who trims the wick?",
                "mode": "answer",
                "student_answer": "Rowan.",
            },
        )
    assert response.status_code == 422


class _BoomStreamLlm(_Llm):
    def stream(self, system: str, prompt: str, *, context=None):
        async def gen():
            raise ProviderError("upstream down")
            yield ""  # pragma: no cover

        return gen()


def test_ask_stream_reports_a_provider_error_as_an_event():
    runtime = Runtime(retriever=_Retriever(), llm=_BoomStreamLlm())
    with _client(runtime) as client:
        with client.stream(
            "POST", "/ask/stream", json={"question": "Who?"}
        ) as response:
            body = "".join(response.iter_text())
    events = _parse_sse(body)
    names = [name for name, _ in events]
    assert "error" in names
    assert "reset" in names
    assert names.index("reset") < names.index("error")


def test_retry_budget_setting_disables_the_retry():
    runtime = Runtime(retriever=_Retriever(), llm=_RetryStreamLlm())
    app = create_app(app_settings=Settings(retry_budget=0), runtime=runtime)
    with TestClient(app) as client:
        with client.stream(
            "POST", "/ask/stream", json={"question": "Who trims the wick?"}
        ) as response:
            body = "".join(response.iter_text())
    events = _parse_sse(body)
    finals = [data for name, data in events if name == "final"]
    assert finals[0]["attempts"] == 1
    assert finals[0]["abstained"] is True


class _RetryStreamLlm(_Llm):
    """An uncited first draft, then a grounded one."""

    def __init__(self) -> None:
        self.streams = 0

    def stream(self, system: str, prompt: str, *, context=None):
        self.streams += 1
        pieces = (
            ("Rowan", " trims", " the wick.")
            if self.streams == 1
            else ("Rowan", " trims", " the wick", " [b1-c01-0000].")
        )

        async def gen():
            for piece in pieces:
                yield piece

        return gen()


def test_ask_stream_resets_and_retries_an_uncited_draft():
    runtime = Runtime(retriever=_Retriever(), llm=_RetryStreamLlm())
    with _client(runtime) as client:
        with client.stream(
            "POST", "/ask/stream", json={"question": "Who trims the wick?"}
        ) as response:
            body = "".join(response.iter_text())
    events = _parse_sse(body)
    names = [name for name, _ in events]
    finals = [data for name, data in events if name == "final"]
    assert names.count("reset") == 1
    assert names.index("reset") < names.index("final")
    assert finals[0]["citations"] == ["b1-c01-0000"]
    assert finals[0]["attempts"] == 2
