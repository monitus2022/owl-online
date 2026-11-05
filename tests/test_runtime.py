"""Composition root: settings must reach the compiled graph."""

from types import SimpleNamespace

from app.api import runtime as runtime_module
from app.config import Settings


async def test_build_runtime_passes_the_retry_budget(monkeypatch):
    captured: dict[str, int] = {}

    async def fake_compose(*args, **kwargs):
        return SimpleNamespace(retriever=object(), dims=1024, text_hash="hash")

    def fake_build_graph(retriever, llm, **kwargs):
        captured["max_retries"] = kwargs["max_retries"]
        return object()

    monkeypatch.setattr(runtime_module, "compose_retriever", fake_compose)
    monkeypatch.setattr(runtime_module, "make_embedder", lambda *a, **k: object())
    monkeypatch.setattr(runtime_module, "make_reranker", lambda *a, **k: object())
    monkeypatch.setattr(runtime_module, "make_llm", lambda *a, **k: object())
    monkeypatch.setattr(runtime_module, "build_graph", fake_build_graph)

    built = await runtime_module.build_runtime(Settings(retry_budget=0))

    assert captured["max_retries"] == 0
    assert built.agent is not None
