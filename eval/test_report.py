"""Eval run reporting tests: row shape and rendered text, no network."""

from pathlib import Path

from eval.check import CheckReport, render_check
from eval.harness import AbstentionMetrics, GenerationMetrics, RetrievalMetrics
from eval.report import (
    RunReport,
    abstention_rows,
    generation_rows,
    render_run,
    retrieval_rows,
)
from eval.results import MetricDelta


def _manifest() -> dict[str, str]:
    return {"generator_model": "gen", "judge_model": "judge", "top_k": "5"}


def test_retrieval_rows_cover_overall_and_slices():
    overall = RetrievalMetrics(2, 0.5, 0.25, 0.5)
    by_slice = {"simple": RetrievalMetrics(2, 0.5, 0.25, 0.5)}
    rows = retrieval_rows("run1", "pinned", _manifest(), overall, by_slice)
    assert [(row.slice, row.metric) for row in rows] == [
        ("overall", "retrieval_n"),
        ("overall", "hit_at_k"),
        ("overall", "recall_at_k"),
        ("overall", "mrr"),
        ("simple", "retrieval_n"),
        ("simple", "hit_at_k"),
        ("simple", "recall_at_k"),
        ("simple", "mrr"),
    ]
    assert rows[0].value == 2
    assert rows[1].value == 0.5


def test_abstention_rows_use_the_rate_property():
    overall = AbstentionMetrics(4, 3)
    rows = abstention_rows("run1", "pinned", _manifest(), overall, {})
    assert [(row.metric, row.value) for row in rows] == [
        ("abstention_n", 4),
        ("abstention_refused", 3),
        ("abstention_rate", 0.75),
    ]


def test_generation_rows_include_faithfulness_counts():
    overall = GenerationMetrics(
        n=3,
        answered=2,
        abstained=1,
        em=0.33,
        f1=0.5,
        correct=1,
        partial=1,
        wrong=0,
        grounded=2,
        faithful=1,
        faithfulness_n=2,
    )
    rows = generation_rows("run1", "pinned", _manifest(), overall, {})
    values = {row.metric: row.value for row in rows}
    assert values["faithfulness_n"] == 2
    assert values["faithful"] == 1
    assert values["faithfulness_rate"] == 0.5
    assert values["judge_correct_rate"] == 0.5
    assert values["judge_parse_failures"] == 0
    assert values["abstained"] == 1


def test_render_run_reports_sections_and_paths():
    retrieval = RetrievalMetrics(50, 0.7, 0.53, 0.45)
    report = RunReport(
        run_path=Path("eval/results/20260101T000000Z.csv"),
        baseline_path=Path("eval/results/baseline.csv"),
        config="pinned",
        generator="openrouter/gen",
        judge="openrouter/judge",
        reranker="bedrock",
        gold_total=60,
        answerable=50,
        unanswerable=10,
        k=5,
        retrieval=retrieval,
        retrieval_by_slice={},
        abstention=AbstentionMetrics(10, 9),
        abstention_by_slice={},
        generation=GenerationMetrics(15, 15, 0, 0.2, 0.4, 9, 5, 1, 15, 14, 15),
        generation_by_slice={},
    )
    text = render_run(report)
    assert "gold: 60 items (50 answerable, 10 unanswerable)" in text
    assert "retrieval\n  overall" in text
    assert "abstention\n  overall" in text
    assert "generation (judged sample)" in text
    assert "wrote eval/results/20260101T000000Z.csv" in text
    assert "wrote baseline eval/results/baseline.csv" in text


def test_render_run_omits_baseline_line_when_not_pinned():
    report = RunReport(
        run_path=Path("eval/results/run.csv"),
        baseline_path=None,
        config="no-rerank",
        generator="openrouter/gen",
        judge="openrouter/judge",
        reranker="none",
        gold_total=60,
        answerable=50,
        unanswerable=10,
        k=5,
        retrieval=RetrievalMetrics(50, 0.6, 0.42, 0.45),
        retrieval_by_slice={},
        abstention=AbstentionMetrics(10, 9),
        abstention_by_slice={},
        generation=GenerationMetrics(15, 15, 0, 0.2, 0.4, 9, 5, 1, 15, 14, 15),
        generation_by_slice={},
    )
    assert "wrote baseline" not in render_run(report)


def test_render_check_lists_missing_metrics_and_deltas():
    report = CheckReport(
        baseline=Path("base.csv"),
        latest=Path("latest.csv"),
        missing=(("pinned", "overall", "mrr"),),
        added=(),
        deltas=(
            MetricDelta("pinned", "overall", "hit_at_k", 0.7, 0.65, -0.05),
        ),
    )
    text = render_check(report)
    assert "metrics missing from the latest run:" in text
    assert "('pinned', 'overall', 'mrr')" in text
    assert "delta=-0.0500" in text
    assert "metrics only in the latest run:" not in text


def test_render_check_says_when_nothing_compares():
    report = CheckReport(
        baseline=Path("base.csv"),
        latest=Path("latest.csv"),
        missing=(),
        added=(),
        deltas=(),
    )
    assert "no comparable metrics" in render_check(report)