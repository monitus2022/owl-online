"""Eval gate tests: thresholds, pass/fail, missing and invalid values, no network."""

import pytest

from eval.check import (
    DENOMINATOR_COUNTS,
    DROP_METRICS,
    GATED_METRICS,
    RATE_DENOMINATOR,
    RISE_METRICS,
    THRESHOLDS_PATH,
    CheckError,
    check,
    load_thresholds,
    render_check,
)
from eval.results import ResultRow, manifest_row, write_results

OVERALL = {
    "retrieval_n": 50,
    "hit_at_k": 0.70,
    "recall_at_k": 0.50,
    "mrr": 0.40,
    "abstention_n": 10,
    "abstention_refused": 10,
    "abstention_rate": 1.0,
    "generation_n": 15,
    "answered": 15,
    "abstained": 0,
    "abstained_rate": 0.0,
    "f1": 0.30,
    "judged": 15,
    "faithfulness_n": 15,
    "faithful": 12,
    "faithfulness_rate": 0.80,
    "judge_correct": 12,
    "judge_partial": 2,
    "judge_wrong": 1,
    "judge_correct_rate": 0.80,
    "grounded": 12,
    "grounded_rate": 0.80,
    "judge_parse_failures": 0,
    "faithful_parse_failures": 0,
}

NAMED = {
    "retrieval_n": 8,
    "hit_at_k": 0.50,
    "recall_at_k": 0.50,
    "mrr": 0.40,
    "generation_n": 5,
    "answered": 5,
    "abstained": 0,
    "abstained_rate": 0.0,
    "f1": 0.25,
    "judged": 5,
    "faithfulness_n": 5,
    "faithful": 4,
    "faithfulness_rate": 0.80,
    "judge_correct": 4,
    "judge_partial": 1,
    "judge_wrong": 0,
    "judge_correct_rate": 0.80,
    "grounded": 4,
    "grounded_rate": 0.80,
    "judge_parse_failures": 0,
    "faithful_parse_failures": 0,
}


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


def _rows(run_id: str, values: dict[str, float], slice_name: str = "overall") -> list[ResultRow]:
    manifest = manifest_row(
        _manifest(),
        embedder_provider="local",
        rerank_enabled=True,
        judged_sample=15,
        gold_hash="abc123",
        rerank_min_score=0.0,
    )
    return [
        ResultRow(run_id, "pinned", slice_name, metric, value, manifest)
        for metric, value in values.items()
    ]


def _files(tmp_path, baseline: dict[str, float], latest: dict[str, float]):
    baseline_path = tmp_path / "baseline.csv"
    latest_path = tmp_path / "20260101T000000Z.csv"
    write_results(baseline_path, _rows("base", baseline))
    write_results(latest_path, _rows("latest", latest))
    return tmp_path, baseline_path


def test_every_gated_metric_has_exactly_one_rule():
    assert DENOMINATOR_COUNTS | DROP_METRICS | RISE_METRICS == GATED_METRICS
    assert not (DENOMINATOR_COUNTS & DROP_METRICS)
    assert not (DENOMINATOR_COUNTS & RISE_METRICS)
    assert not (DROP_METRICS & RISE_METRICS)
    assert set(RATE_DENOMINATOR) <= DROP_METRICS | RISE_METRICS
    assert set(RATE_DENOMINATOR.values()) <= GATED_METRICS


def test_thresholds_load_and_validate_the_real_file():
    thresholds = load_thresholds()
    assert thresholds.baseline == "eval/results/baseline.csv"
    assert thresholds.bands["hit_at_k"] == 0.05
    assert thresholds.band("hit_at_k", 50) == 0.05
    assert thresholds.band("hit_at_k", 8) == 0.125
    assert thresholds.band("f1", 15) == pytest.approx(1 / 15)
    assert thresholds.band("retrieval_n", 50) == 0.0


def test_gate_passes_inside_the_band(tmp_path):
    latest = dict(OVERALL, hit_at_k=0.66)
    results, baseline = _files(tmp_path, OVERALL, latest)
    report = check(results, baseline)
    assert report.passed
    assert "gate: PASS" in render_check(report)


def test_gate_fails_beyond_the_band(tmp_path):
    latest = dict(OVERALL, hit_at_k=0.60)
    results, baseline = _files(tmp_path, OVERALL, latest)
    report = check(results, baseline)
    assert not report.passed
    assert len(report.failures) == 1
    assert report.failures[0].amount == pytest.approx(0.10)
    text = render_check(report)
    assert "gate: FAIL" in text
    assert "dropped 0.1000, band 0.0500" in text


def test_slice_band_allows_one_item_and_fails_on_two(tmp_path):
    baseline_path = tmp_path / "baseline.csv"
    latest_path = tmp_path / "20260101T000000Z.csv"
    write_results(baseline_path, _rows("base", NAMED, "named_reference"))
    write_results(
        latest_path, _rows("latest", dict(NAMED, hit_at_k=0.375), "named_reference")
    )
    assert check(tmp_path, baseline_path).passed

    write_results(
        latest_path, _rows("latest", dict(NAMED, hit_at_k=0.25), "named_reference")
    )
    report = check(tmp_path, baseline_path)
    assert not report.passed
    assert report.failures[0].band == pytest.approx(0.125)


def test_count_change_fails_with_a_zero_band(tmp_path):
    latest = dict(OVERALL, retrieval_n=49)
    results, baseline = _files(tmp_path, OVERALL, latest)
    report = check(results, baseline)
    assert not report.passed
    assert any(f.delta.metric == "retrieval_n" for f in report.failures)


def test_answerability_change_fails_even_when_rates_rise(tmp_path):
    latest = dict(
        OVERALL,
        answered=13,
        abstained=2,
        abstained_rate=2 / 15,
        judged=13,
        faithfulness_n=13,
    )
    results, baseline = _files(tmp_path, OVERALL, latest)
    report = check(results, baseline)
    assert not report.passed
    failed = {f.delta.metric for f in report.failures}
    assert {"abstained_rate", "judged", "faithfulness_n"} <= failed


def test_fewer_abstentions_is_an_improvement(tmp_path):
    baseline = dict(
        OVERALL,
        answered=13,
        abstained=2,
        abstained_rate=2 / 15,
        judged=13,
        faithfulness_n=13,
    )
    latest = dict(OVERALL)
    results, baseline_path = _files(tmp_path, baseline, latest)
    report = check(results, baseline_path)
    assert report.passed


def test_one_item_f1_drop_is_inside_the_band(tmp_path):
    latest = dict(OVERALL, f1=0.30 - 1 / 15)
    results, baseline = _files(tmp_path, OVERALL, latest)
    report = check(results, baseline)
    assert report.passed


def test_improving_outcome_counts_do_not_fail(tmp_path):
    latest = dict(
        OVERALL,
        faithful=13,
        faithfulness_rate=13 / 15,
        judge_correct=13,
        judge_partial=1,
        judge_correct_rate=13 / 15,
        grounded=13,
        grounded_rate=13 / 15,
    )
    results, baseline = _files(tmp_path, OVERALL, latest)
    report = check(results, baseline)
    assert report.passed
    assert "gate: PASS" in render_check(report)


def test_missing_gated_metric_fails_the_gate(tmp_path):
    latest = {k: v for k, v in OVERALL.items() if k != "f1"}
    results, baseline = _files(tmp_path, OVERALL, latest)
    report = check(results, baseline)
    assert not report.passed
    assert ("pinned", "overall", "f1") in report.failing_missing
    assert "missing gated metric from latest" in render_check(report)


def test_truncated_baseline_fails_the_gate(tmp_path):
    results, baseline = _files(tmp_path, {"hit_at_k": 0.70}, OVERALL)
    report = check(results, baseline)
    assert not report.passed
    assert ("pinned", "overall", "f1") in report.missing_baseline
    assert "missing gated metric from baseline" in render_check(report)


def test_nan_value_fails_the_gate(tmp_path):
    latest = dict(OVERALL)
    latest["f1"] = "nan"
    results, baseline = _files(tmp_path, OVERALL, latest)
    report = check(results, baseline)
    assert not report.passed
    assert ("pinned", "overall", "f1") in report.invalid
    assert "invalid value" in render_check(report)


def test_empty_latest_run_is_an_error(tmp_path):
    results, baseline = _files(tmp_path, OVERALL, OVERALL)
    latest = results / "20260101T000000Z.csv"
    latest.write_text("", encoding="utf-8")
    with pytest.raises(CheckError, match="latest run is empty"):
        check(results, baseline)


def test_unknown_threshold_key_is_an_error(tmp_path):
    path = tmp_path / "thresholds.toml"
    path.write_text('baseline = "baseline.csv"\n[bands]\nnot_a_metric = 0.1\n')
    with pytest.raises(CheckError, match="unknown gated metrics"):
        load_thresholds(path)


def test_config_mismatch_is_refused(tmp_path):
    results, baseline = _files(tmp_path, OVERALL, OVERALL)
    latest = results / "20260101T000000Z.csv"
    manifest = manifest_row(
        _manifest(),
        embedder_provider="local",
        rerank_enabled=True,
        judged_sample=15,
        gold_hash="abc123",
        rerank_min_score=0.0,
    )
    manifest["judge_model"] = "other"
    write_results(
        latest, [ResultRow("latest", "pinned", "overall", "hit_at_k", 0.70, manifest)]
    )
    with pytest.raises(CheckError, match="different configurations"):
        check(results, baseline)


def test_self_comparison_is_refused(tmp_path):
    results, baseline = _files(tmp_path, OVERALL, OVERALL)
    latest = results / "20260101T000000Z.csv"
    with pytest.raises(CheckError, match="same file"):
        check(results, latest, latest_path=latest)


def test_baseline_copy_of_latest_is_refused(tmp_path):
    results, baseline = _files(tmp_path, OVERALL, OVERALL)
    latest = results / "20260101T000000Z.csv"
    baseline.write_text(latest.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(CheckError, match="baseline copy"):
        check(results, baseline)


def test_toml_baseline_path_is_used_when_omitted(tmp_path):
    results, baseline = _files(tmp_path, OVERALL, OVERALL)
    text = THRESHOLDS_PATH.read_text(encoding="utf-8")
    thresholds_path = tmp_path / "thresholds.toml"
    thresholds_path.write_text(
        text.replace(
            'baseline = "eval/results/baseline.csv"',
            f'baseline = "{baseline}"',
        ),
        encoding="utf-8",
    )
    report = check(results, None, thresholds_path)
    assert report.passed


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "true", "-0.01"])
def test_invalid_bands_are_rejected(tmp_path, value):
    text = THRESHOLDS_PATH.read_text(encoding="utf-8")
    path = tmp_path / "thresholds.toml"
    path.write_text(
        text.replace("hit_at_k = 0.05", f"hit_at_k = {value}"),
        encoding="utf-8",
    )
    with pytest.raises(CheckError, match="finite non-negative"):
        load_thresholds(path)


def test_unknown_slice_is_rejected(tmp_path):
    results, baseline = _files(tmp_path, OVERALL, OVERALL)
    latest = results / "20260101T000000Z.csv"
    write_results(latest, _rows("latest", OVERALL, "new_slice"))
    with pytest.raises(CheckError, match="unknown slice"):
        check(results, baseline)


def test_no_runs_is_an_error(tmp_path):
    with pytest.raises(CheckError, match="no runs"):
        check(tmp_path, tmp_path / "baseline.csv")
