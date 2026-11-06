"""Runner wiring: manifest settings must reach retrieval and the result rows."""

from types import SimpleNamespace

import eval.runner as runner


async def test_run_passes_the_manifest_settings(monkeypatch, tmp_path):
    seen: dict[str, int] = {}
    manifest = {"generation": {"retry_budget": 0}}

    async def fake_compose(*args, **kwargs):
        seen["compose_quota"] = kwargs["subquery_quota"]
        return SimpleNamespace(retriever=object(), dims=1024, text_hash="hash")

    def fake_manifest_row(*args, **kwargs):
        seen["manifest_quota"] = kwargs["subquery_quota"]
        return {}

    async def fake_retrieval(*args, **kwargs):
        return SimpleNamespace(n=0), {}

    async def fake_abstention(*args, **kwargs):
        seen["abstention"] = args[4]
        return SimpleNamespace(n=0), {}

    async def fake_judge(*args, **kwargs):
        seen["judge"] = args[6]
        return []

    gold_path = tmp_path / "gold.jsonl"
    gold_path.write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(runner, "compose_retriever", fake_compose)
    monkeypatch.setattr(runner, "make_embedder", lambda *a, **k: object())
    monkeypatch.setattr(runner, "make_reranker", lambda *a, **k: object())
    monkeypatch.setattr(runner, "make_llm", lambda *a, **k: object())
    monkeypatch.setattr(runner, "CachedLlm", lambda *a, **k: object())
    monkeypatch.setattr(runner, "load_gold", lambda path: [])
    monkeypatch.setattr(runner, "load_chunks", lambda path: [])
    monkeypatch.setattr(runner, "load_manifest", lambda: manifest)
    monkeypatch.setattr(runner, "manifest_row", fake_manifest_row)
    monkeypatch.setattr(runner, "timestamp_run_id", lambda: "20260101T000000Z")
    monkeypatch.setattr(runner, "write_results", lambda path, rows: None)
    monkeypatch.setattr(runner, "retrieval_metrics_all", fake_retrieval)
    monkeypatch.setattr(runner, "retrieval_diagnostics_all", fake_retrieval)
    monkeypatch.setattr(runner, "abstention_metrics_all", fake_abstention)
    monkeypatch.setattr(runner, "judge_sample", fake_judge)
    monkeypatch.setattr(runner, "summarize_generation", lambda verdicts: SimpleNamespace())
    monkeypatch.setattr(runner, "generation_metrics_by_slice", lambda v, g: {})
    for name in (
        "retrieval_rows",
        "retrieval_diagnostic_rows",
        "abstention_rows",
        "generation_rows",
    ):
        monkeypatch.setattr(runner, name, lambda *a, **k: [])

    await runner.run(
        gold_path=gold_path,
        chunks_path=tmp_path / "chunks.jsonl",
        index_dir=tmp_path / "index",
        cache_dir=tmp_path / "cache",
        results_dir=tmp_path / "results",
        baseline=tmp_path / "baseline.csv",
        k=5,
        sample=15,
        pin_baseline=False,
    )

    assert seen == {
        "compose_quota": runner.settings.subquery_quota,
        "manifest_quota": runner.settings.subquery_quota,
        "abstention": 0,
        "judge": 0,
    }
