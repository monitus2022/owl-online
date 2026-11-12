"""Render and persist the lesson + multi-turn RAG report."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from eval.rag.metrics import RagReport


def to_dict(report: RagReport) -> dict[str, object]:
    """The JSON shape written to eval/results/rag-<run_id>.json."""
    return dataclasses.asdict(report)


def write_report(path: Path, report: RagReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(to_dict(report), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_report(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_report(results_dir: Path) -> Path | None:
    """The newest rag-*.json that is not the pinned baseline."""
    paths = [path for path in results_dir.glob("rag-*.json") if path.name != "rag-baseline.json"]
    return max(paths, key=lambda path: path.name) if paths else None


def flatten(report: dict[str, object]) -> dict[str, float]:
    """Flatten the nested report into the metrics the gate compares."""
    lesson = report.get("lesson", {})
    multiturn = report.get("multiturn", {})
    if not isinstance(lesson, dict) or not isinstance(multiturn, dict):
        raise ValueError("report must carry lesson and multiturn objects")
    metrics: dict[str, float] = {}
    for key, value in lesson.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            metrics[f"lesson_{key}"] = float(value)
    for key, value in multiturn.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            metrics[f"multiturn_{key}"] = float(value)
    return metrics


def _rate(value: float) -> str:
    return f"{value:.4f}"


def render_report(report: RagReport) -> str:
    """The printed summary for a run."""
    lesson = report.lesson
    multiturn = report.multiturn
    lines = [
        f"run_id: {report.run_id}",
        f"config: {report.config}",
        f"generator: {report.generator}",
        f"judge: {report.judge}",
        f"lesson fixture: {report.lesson_fixture_sha} (judged sample {report.lesson_sample})",
        f"multi-turn fixture: {report.multiturn_fixture_sha}",
        "",
        "lesson",
        f"  total={lesson.total} answerable={lesson.answerable} unanswerable={lesson.unanswerable}",
        f"  selection precision@3={_rate(lesson.selection_precision_at_3)} "
        f"recall@3={_rate(lesson.selection_recall_at_3)}",
        f"  scope accuracy={_rate(lesson.scope_accuracy)} "
        f"citation recall={_rate(lesson.citation_recall)}",
        f"  false refusal={_rate(lesson.false_refusal_rate)} "
        f"abstention accuracy={_rate(lesson.abstention_accuracy)}",
        f"  citation validity={_rate(lesson.citation_validity_rate)} "
        f"source hash={_rate(lesson.source_hash_rate)}",
        f"  judged={lesson.judged} faithfulness={_rate(lesson.faithfulness_rate)}",
        "",
        "multi-turn",
        f"  conversations={multiturn.conversations} turns={multiturn.turns}",
        f"  query accuracy={_rate(multiturn.query_accuracy)} "
        f"mode accuracy={_rate(multiturn.mode_accuracy)}",
        f"  citation accuracy={_rate(multiturn.citation_accuracy)} "
        f"false refusal={_rate(multiturn.false_refusal_rate)}",
        f"  abstention accuracy={_rate(multiturn.abstention_accuracy)}",
        f"  referral target accuracy={_rate(multiturn.referral_target_accuracy)} "
        f"comparison accuracy={_rate(multiturn.comparison_accuracy)}",
        f"  context contamination={multiturn.context_contamination}",
        "",
        f"errors: {report.errors}",
    ]
    return "\n".join(lines)


__all__ = [
    "flatten",
    "latest_report",
    "load_report",
    "render_report",
    "to_dict",
    "write_report",
]
