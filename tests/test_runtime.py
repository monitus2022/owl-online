"""Composition root: settings must reach the compiled graph."""

from types import SimpleNamespace

from app.api import runtime as runtime_module
from app.config import Settings


async def test_build_runtime_passes_the_retrieval_settings(monkeypatch, tmp_path):
    captured: dict[str, int] = {}

    async def fake_compose(*args, **kwargs):
        captured["subquery_quota"] = kwargs["subquery_quota"]
        return SimpleNamespace(
            retriever=object(), dims=1024, text_hash="hash", chunks_by_id={}
        )

    def fake_build_graph(retriever, llm, **kwargs):
        captured["max_retries"] = kwargs["max_retries"]
        return object()

    monkeypatch.setattr(runtime_module, "compose_retriever", fake_compose)
    monkeypatch.setattr(runtime_module, "make_embedder", lambda *a, **k: object())
    monkeypatch.setattr(runtime_module, "make_reranker", lambda *a, **k: object())
    monkeypatch.setattr(runtime_module, "make_llm", lambda *a, **k: object())
    monkeypatch.setattr(runtime_module, "build_graph", fake_build_graph)

    built = await runtime_module.build_runtime(
        Settings(
            retry_budget=0,
            subquery_quota=2,
            lore_path=tmp_path / "absent-lore",
            subjects_path=tmp_path / "absent-subjects",
        )
    )

    assert captured["max_retries"] == 0
    assert captured["subquery_quota"] == 2
    assert built.agent is not None
    assert built.lore is None
    assert built.packs == ()


async def test_build_runtime_loads_published_pack_summaries(monkeypatch, tmp_path):
    from app.knowledge.packs import PackSummary

    summary = PackSummary(
        subject="dada",
        title="Defence Against the Dark Arts",
        tier="owl",
        version="1.0.0",
        status="published",
        built_at="2026-11-08T00:00:00Z",
        fingerprint="0123456789abcdef",
        topics=("dark-creatures",),
        concepts=21,
        materials=25,
    )

    async def fake_compose(*args, **kwargs):
        return SimpleNamespace(
            retriever=object(), dims=1024, text_hash="hash", chunks_by_id={}
        )

    monkeypatch.setattr(runtime_module, "compose_retriever", fake_compose)
    monkeypatch.setattr(runtime_module, "make_embedder", lambda *a, **k: object())
    monkeypatch.setattr(runtime_module, "make_reranker", lambda *a, **k: object())
    monkeypatch.setattr(runtime_module, "make_llm", lambda *a, **k: object())
    monkeypatch.setattr(runtime_module, "build_graph", lambda *a, **k: object())
    monkeypatch.setattr(
        runtime_module,
        "load_pack_store",
        lambda *a, **k: SimpleNamespace(summaries=lambda: [summary]),
    )

    built = await runtime_module.build_runtime(
        Settings(
            retry_budget=0,
            lore_path=tmp_path / "absent-lore",
            subjects_path=tmp_path,
        )
    )
    assert built.packs == (summary,)


class _FakeStore:
    def summaries(self):
        return [SimpleNamespace(subject="dada", version="1.0.0")]

    def subjects(self):
        return ("dada",)

    def scope(self):
        return "dada:fp"


def _patch_runtime(monkeypatch):
    async def fake_compose(*args, **kwargs):
        return SimpleNamespace(
            retriever=object(), dims=1024, text_hash="hash", chunks_by_id={}
        )

    monkeypatch.setattr(runtime_module, "compose_retriever", fake_compose)
    monkeypatch.setattr(runtime_module, "make_embedder", lambda *a, **k: object())
    monkeypatch.setattr(runtime_module, "make_reranker", lambda *a, **k: object())
    monkeypatch.setattr(runtime_module, "make_llm", lambda *a, **k: object())
    monkeypatch.setattr(runtime_module, "build_graph", lambda *a, **k: object())
    monkeypatch.setattr(runtime_module, "load_pack_store", lambda *a, **k: _FakeStore())


async def test_build_runtime_builds_the_lesson_selector(monkeypatch, tmp_path):
    _patch_runtime(monkeypatch)
    selector = SimpleNamespace(subjects=lambda: ("dada",))

    async def fake_build(store, embedder):
        return selector

    monkeypatch.setattr(
        runtime_module, "LessonSelector", SimpleNamespace(build=fake_build)
    )

    built = await runtime_module.build_runtime(
        Settings(
            lesson_mode=True,
            lore_path=tmp_path / "absent-lore",
            subjects_path=tmp_path,
        )
    )

    assert built.lesson is selector
    assert built.pack_store is not None


async def test_build_runtime_keeps_chat_up_when_lesson_embedding_fails(
    monkeypatch, tmp_path
):
    _patch_runtime(monkeypatch)

    async def fake_build(store, embedder):
        raise RuntimeError("embedder down")

    monkeypatch.setattr(
        runtime_module, "LessonSelector", SimpleNamespace(build=fake_build)
    )

    built = await runtime_module.build_runtime(
        Settings(
            lesson_mode=True,
            lore_path=tmp_path / "absent-lore",
            subjects_path=tmp_path,
        )
    )

    assert built.lesson is None
    assert built.pack_store is not None
