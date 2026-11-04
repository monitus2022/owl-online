"""Eval gate tests: threshold loading, pass/fail, missing metrics, no network."""

import pytest

from eval.check import CheckError, check, load_thresholds, render_check
from eval.results import ResultRow, manifest_row, write_results


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
        "retrieval": {"top_k": 5, "rrf_k": 60, "candidates": 50},
    }


def _row(run_id: str, metric: str, value: float, slice_name: str = "overall") -> ResultRow:
    manifest = manifest_row(
        _manifest(),
        embedder_provider="local",
        rerank_enabled=True,
        judged_sample=15,
    )
    return ResultRow(run_id, "pinned", slice_name, metric, value, manifest)


def _files(tmp_path, baseline_values, latest_values):
    baseline = tmp_path / "baseline.csv"
    latest = tmp_path / "20260101T000000Z.csv"
    write_results(baseline, [_row("base", metric, value) for metric, value in baseline_values])
    write_results(latest, [_row("latest", metric, value) for metric, value in latest_values])
    return tmp_path, baseline


def test_thresholds_load_the_real_file():
    thresholds = load_thresholds()
    assert thresholds.baseline == "eval/results/baseline.csv"
    assert thresholds.bands["hit_at_k"] == 0.05
    assert thresholds.band("hit_at_k", "overall") == 0.05
    assert thresholds.band("hit_at_k", "named_reference") == 0.13


def test_gate_passes_inside_the_band(tmp_path):
    results, baseline = _files(tmp_path, [("hit_at_k", 0.70)], [("hit_at_k", 0.66)])
    report = check(results, baseline)
    assert report.passed
    assert "gate: PASS" in render_check(report)


def test_gate_fails_beyond_the_band(tmp_path):
    results, baseline = _files(tmp_path, [("hit_at_k", 0.70)], [("hit_at_k", 0.60)])
    report = check(results, baseline)
    assert not report.passed
    assert len(report.failures) == 1
    assert report.failures[0].drop == pytest.approx(0.10)
    text = render_check(report)
    assert "gate: FAIL" in text
    assert "dropped 0.1000" in text


def test_slice_band_allows_one_item_on_an_eight_item_slice(tmp_path):
    results, baseline = _files(
        tmp_path,
        [("hit_at_k", 0.50)],
        [("hit_at_k", 0.375)],
    )
    # Rewrite the rows onto the named_reference slice.
    write_results(
        baseline, [_row("base", "hit_at_k", 0.50, "named_reference")]
    )
    write_results(
        results / "20260101T000000Z.csv",
        [_row("latest", "hit_at_k", 0.375, "named_reference")],
    )
    assert check(results, baseline).passed


def test_missing_gated_metric_fails_the_gate(tmp_path):
    results, baseline = _files(tmp_path, [("hit_at_k", 0.70), ("f1", 0.30)], [("hit_at_k", 0.70)])
    report = check(results, baseline)
    assert not report.passed
    assert ("pinned", "overall", "f1") in report.failing_missing
    assert "missing gated metric" in render_check(report)


def test_config_mismatch_is_refused(tmp_path):
    results, baseline = _files(tmp_path, [("hit_at_k", 0.70)], [("hit_at_k", 0.70)])
    latest = results / "20260101T000000Z.csv"
    manifest = manifest_row(
        _manifest(), embedder_provider="local", rerank_enabled=True, judged_sample=15
    )
    manifest["judge_model"] = "other"
    write_results(latest, [ResultRow("latest", "pinned", "overall", "hit_at_k", 0.70, manifest)])
    with pytest.raises(CheckError, match="different configurations"):
        check(results, baseline)


def test_no_runs_is_an_error(tmp_path):
    with pytest.raises(CheckError, match="no runs"):
        check(tmp_path, tmp_path / "baseline.csv")
