"""Result CSV and baseline diff tests, no network."""

from eval.results import (
    ResultRow,
    copy_baseline,
    diff_results,
    latest_run,
    load_manifest,
    manifest_mismatch,
    manifest_row,
    metric_keys,
    read_results,
    timestamp_run_id,
    write_results,
)


def _manifest() -> dict:
    return {
        "generator": {"model": "gen"},
        "judge": {"model": "judge"},
        "reranker": {"model": "rerank", "pool": 50},
        "embedder": {
            "cloud": {"model": "titan", "dimensions": 1024},
            "local": {"model": "ollama", "dimensions": 1024},
        },
        "chunking": {"size": 500, "overlap": 75, "min_size": 200},
        "retrieval": {
            "top_k": 5,
            "rrf_k": 60,
            "candidates": 50,
            "subquery_quota": 0,
        },
    }


def test_manifest_row_records_the_run_choices():
    cloud = manifest_row(_manifest(), embedder_provider="bedrock", rerank_enabled=True)
    assert cloud["generator_model"] == "gen"
    assert cloud["judge_model"] == "judge"
    assert cloud["reranker_model"] == "rerank"
    assert cloud["reranker_pool"] == "50"
    assert cloud["embedder_provider"] == "bedrock"
    assert cloud["embedder_model"] == "titan"
    assert cloud["embedder_dims"] == "1024"
    assert cloud["top_k"] == "5"
    assert cloud["rrf_k"] == "60"
    assert cloud["candidates"] == "50"
    assert cloud["subquery_quota"] == "0"

    local = manifest_row(_manifest(), embedder_provider="local", rerank_enabled=False)
    assert local["embedder_model"] == "ollama"
    assert local["reranker_model"] == "none"
    assert local["reranker_pool"] == "0"
    # Rerank off uses the retriever's own candidate default, not the pool.
    assert local["candidates"] == "20"


def test_manifest_row_records_run_time_overrides():
    row = manifest_row(
        _manifest(),
        embedder_provider="bedrock",
        rerank_enabled=True,
        top_k=3,
        reranker_pool=30,
        candidates=30,
        judged_sample=7,
        reranker_model="effective-rerank",
        embedder_model="effective-embed",
        embedder_dims=512,
        gold_hash="abc123",
        index_text_hash="def456",
        rerank_min_score=0.25,
        generator_temperature=0.0,
        judge_temperature=0.0,
        subquery_quota=2,
    )
    assert row["top_k"] == "3"
    assert row["reranker_pool"] == "30"
    assert row["candidates"] == "30"
    assert row["judged_sample"] == "7"
    assert row["reranker_model"] == "effective-rerank"
    assert row["embedder_model"] == "effective-embed"
    assert row["embedder_dims"] == "512"
    assert row["gold_hash"] == "abc123"
    assert row["index_text_hash"] == "def456"
    assert row["rerank_min_score"] == "0.25"
    assert row["generator_temperature"] == "0.0"
    assert row["judge_temperature"] == "0.0"
    assert row["subquery_quota"] == "2"


def test_load_manifest_pins_the_real_file():
    manifest = load_manifest()
    assert "generator" in manifest
    assert "retrieval" in manifest


def test_timestamp_run_id_sorts():
    from datetime import UTC, datetime

    assert timestamp_run_id(datetime(2026, 11, 4, 12, 0, tzinfo=UTC)) == "20261104T120000Z"


def test_write_and_read_results_round_trip(tmp_path):
    manifest = manifest_row(_manifest(), embedder_provider="local", rerank_enabled=True)
    rows = [
        ResultRow("run1", "pinned", "overall", "hit_at_k", 0.7, manifest),
        ResultRow("run1", "pinned", "simple", "f1", 0.5, manifest),
    ]
    path = tmp_path / "run.csv"
    write_results(path, rows)
    back = read_results(path)
    assert [row["metric"] for row in back] == ["hit_at_k", "f1"]
    assert float(back[0]["value"]) == 0.7
    assert back[0]["generator_model"] == "gen"
    # Every row repeats the manifest values.
    assert back[1]["top_k"] == "5"


def test_latest_run_ignores_the_baseline(tmp_path):
    (tmp_path / "20260101T000000Z.csv").write_text("", encoding="utf-8")
    (tmp_path / "20260102T000000Z.csv").write_text("", encoding="utf-8")
    (tmp_path / "baseline.csv").write_text("", encoding="utf-8")
    (tmp_path / "stray.csv").write_text("", encoding="utf-8")
    assert latest_run(tmp_path) == tmp_path / "20260102T000000Z.csv"


def test_latest_run_is_none_when_empty(tmp_path):
    assert latest_run(tmp_path) is None


def _row(run: str, metric: str, value: float) -> dict[str, str]:
    return {
        "run_id": run,
        "config": "pinned",
        "slice": "overall",
        "metric": metric,
        "value": str(value),
    }


def test_diff_results_reports_per_metric_deltas():
    deltas = diff_results(
        [_row("base", "hit_at_k", 0.7), _row("base", "mrr", 0.45)],
        [_row("latest", "hit_at_k", 0.65), _row("latest", "mrr", 0.45)],
    )
    assert len(deltas) == 2
    assert deltas[0].metric == "hit_at_k"
    assert abs(deltas[0].delta - (-0.05)) < 1e-9
    assert deltas[1].delta == 0.0


def test_diff_results_skips_metrics_missing_from_one_side():
    deltas = diff_results(
        [_row("base", "hit_at_k", 0.7), _row("base", "mrr", 0.45)],
        [_row("latest", "hit_at_k", 0.65)],
    )
    assert [delta.metric for delta in deltas] == ["hit_at_k"]


def test_metric_keys_identifies_missing_metrics():
    baseline = [_row("base", "hit_at_k", 0.7), _row("base", "mrr", 0.45)]
    latest = [_row("latest", "hit_at_k", 0.65)]
    missing = metric_keys(baseline) - metric_keys(latest)
    assert missing == {("pinned", "overall", "mrr")}


def test_manifest_mismatch_flags_incomparable_runs():
    manifest = manifest_row(_manifest(), embedder_provider="local", rerank_enabled=True)
    other = dict(manifest, judge_model="different", judged_sample="7")
    mismatch = manifest_mismatch(
        [{**manifest, "metric": "hit_at_k"}],
        [{**other, "metric": "hit_at_k"}],
    )
    assert mismatch == {
        "judge_model": ("judge", "different"),
        "judged_sample": ("", "7"),
    }


def test_manifest_mismatch_is_empty_for_the_same_configuration():
    manifest = manifest_row(_manifest(), embedder_provider="local", rerank_enabled=True)
    assert manifest_mismatch([manifest], [dict(manifest)]) == {}


def test_copy_baseline(tmp_path):
    latest = tmp_path / "run.csv"
    latest.write_text("run_id,config\nrun1,pinned\n", encoding="utf-8")
    baseline = tmp_path / "baseline.csv"
    copy_baseline(latest, baseline)
    assert baseline.read_text(encoding="utf-8") == latest.read_text(encoding="utf-8")


def test_result_fields_are_stable():
    from eval.results import MANIFEST_FIELDS, RESULT_FIELDS

    assert RESULT_FIELDS[:5] == ["run_id", "config", "slice", "metric", "value"]
    assert RESULT_FIELDS[5:] == MANIFEST_FIELDS
    assert len(MANIFEST_FIELDS) == 20