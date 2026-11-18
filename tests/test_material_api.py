"""The material route: reviewed pack prose only, never a corpus passage."""

from fastapi.testclient import TestClient

from app.api.runtime import Runtime
from app.config import Settings
from app.knowledge.materials import Material, SourceRef
from app.knowledge.packs import (
    Concept,
    PackManifest,
    PackStore,
    SubjectPack,
    Topic,
)
from app.main import create_app

_MATERIAL_ID = "dada-dark-creatures-boggarts-counter"


class _Retriever:
    async def retrieve(self, query: str, top_k: int) -> list[object]:
        return []


class _Llm:
    name = "fake/material"

    async def generate(self, system: str, prompt: str, *, context=None) -> str:
        return ""

    def stream(self, system: str, prompt: str, *, context=None):
        async def empty():
            yield ""

        return empty()


def _pack(
    *, status: str = "published", review_status: str = "reviewed"
) -> SubjectPack:
    material = Material(
        material_id=_MATERIAL_ID,
        subject="dada",
        topic="dark-creatures",
        concept="boggarts",
        kind="creature",
        text="The counter-charm is Riddikulus.",
        review_status=review_status,
        source_refs=[
            SourceRef(
                chunk_id="b3-c07-0041",
                book=3,
                chapter=7,
                quote="A Boggart takes the shape",
                text_hash="a" * 16,
                index_text_hash="test-index",
            )
        ],
    )
    return SubjectPack(
        manifest=PackManifest(
            subject="dada",
            version="1.0.0",
            status=status,
            built_at="2026-11-18T00:00:00Z",
            index_text_hash="test-index",
        ),
        topics=[
            Topic(topic_id="dark-creatures", subject="dada", title="Dark creatures")
        ],
        concepts=[
            Concept(
                concept_id="boggarts",
                subject="dada",
                kind="creature",
                title="Boggarts",
            )
        ],
        materials=[material],
    )


def _store(
    *, status: str = "published", review_status: str = "reviewed"
) -> PackStore:
    return PackStore(
        packs={"dada": _pack(status=status, review_status=review_status)},
        fingerprints={"dada": "test"},
    )


def _client(store: PackStore | None) -> TestClient:
    app = create_app(
        app_settings=Settings(),
        runtime=Runtime(
            retriever=_Retriever(),
            llm=_Llm(),
            pack_store=store,
        ),
    )
    return TestClient(app)


def test_material_route_returns_reviewed_text_and_safe_refs():
    with _client(_store()) as client:
        response = client.get(f"/v1/materials/dada/{_MATERIAL_ID}")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=300"
    data = response.json()
    assert data["material_id"] == _MATERIAL_ID
    assert data["subject"] == "dada"
    assert data["topic"] == "dark-creatures"
    assert data["topic_title"] == "Dark creatures"
    assert data["concept"] == "boggarts"
    assert data["concept_title"] == "Boggarts"
    assert data["text"] == "The counter-charm is Riddikulus."
    assert data["pack_version"] == "1.0.0"
    assert data["source_refs"] == [
        {"chunk_id": "b3-c07-0041", "book": 3, "chapter": 7}
    ]
    # The corpus quote and per-chunk hashes stay on the server.
    ref = data["source_refs"][0]
    assert "quote" not in ref
    assert "text_hash" not in ref
    assert "index_text_hash" not in ref


def test_material_route_hides_unknown_ids_and_subjects():
    with _client(_store()) as client:
        assert client.get("/v1/materials/dada/not-a-material").status_code == 404
        assert (
            client.get(f"/v1/materials/astrology/{_MATERIAL_ID}").status_code
            == 422
        )
        # A registered O.W.L. subject with no published pack is a 404.
        assert (
            client.get(f"/v1/materials/astronomy/{_MATERIAL_ID}").status_code
            == 404
        )


def test_material_route_serves_only_published_reviewed_material():
    with _client(_store(status="draft")) as client:
        assert client.get(f"/v1/materials/dada/{_MATERIAL_ID}").status_code == 404
    with _client(_store(review_status="draft")) as client:
        assert client.get(f"/v1/materials/dada/{_MATERIAL_ID}").status_code == 404
    with _client(None) as client:
        assert client.get(f"/v1/materials/dada/{_MATERIAL_ID}").status_code == 404
