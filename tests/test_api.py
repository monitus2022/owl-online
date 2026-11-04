"""API tests: the /ask endpoint with an injected Runtime, no network."""

from fastapi.testclient import TestClient

from app.api.runtime import Runtime
from app.main import create_app
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


class _BoomLlm:
    async def generate(self, system: str, prompt: str, *, context=None) -> str:
        raise ProviderError("upstream down")


def _client(runtime: Runtime | None = None) -> TestClient:
    app = create_app(runtime=runtime or Runtime(retriever=_Retriever(), llm=_Llm()))
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
