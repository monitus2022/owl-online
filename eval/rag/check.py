"""Baseline gate for the lesson + multi-turn RAG eval."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from eval.rag.report import flatten, load_report

# Quality metrics fail on a drop. False refusal and contamination fail on a
# rise. Denominator counts have a zero band so a fixture edit cannot hide in a
# rate.
DROP_METRICS = frozenset(
    {
        "lesson_selection_precision_at_3",
        "lesson_selection_recall_at_3",
        "lesson_scope_accuracy",
        "lesson_citation_recall",
        "lesson_abstention_accuracy",
        "lesson_citation_validity_rate",
        "lesson_source_hash_rate",
        "lesson_faithfulness_rate",
        "multiturn_query_accuracy",
        "multiturn_mode_accuracy",
        "multiturn_citation_accuracy",
        "multiturn_abstention_accuracy",
        "multiturn_comparison_accuracy",
    }
)
# Referral target accuracy is reported but not gated until #253 adds the
# referral contract and a mode that can produce it.
RISE_METRICS = frozenset(
    {
        "lesson_false_refusal_rate",
        "multiturn_false_refusal_rate",
        "multiturn_context_contamination",
        "lesson_errors",
        "multiturn_errors",
    }
)
COUNT_METRICS = frozenset(
    {
        "lesson_total",
        "lesson_answerable",
        "lesson_unanswerable",
        "lesson_judged",
        "multiturn_conversations",
        "multiturn_turns",
    }
)


class CheckError(RuntimeError):
    """The gate cannot run."""


@dataclass(frozen=True)
class MetricDelta:
    name: str
    baseline: float
    latest: float

    @property
    def delta(self) -> float:
        return self.latest - self.baseline


@dataclass(frozen=True)
class GateFailure:
    delta: MetricDelta
    band: float
    direction: str


@dataclass(frozen=True)
class RagCheckReport:
    baseline: Path
    latest: Path
    deltas: tuple[MetricDelta, ...]
    failures: tuple[GateFailure, ...]
    missing: tuple[str, ...]
    added: tuple[str, ...]
    fixture_mismatch: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return not self.failures and not self.missing and not self.fixture_mismatch


def _band(name: str, default: float) -> float:
    if name in COUNT_METRICS:
        return 0.0
    return default


def check_rag(
    baseline_path: Path,
    latest_path: Path,
    *,
    band: float = 0.05,
) -> RagCheckReport:
    """Diff the latest report against the pinned RAG baseline."""
    if not baseline_path.exists():
        raise CheckError(
            f"no RAG baseline at {baseline_path}; run once with "
            "`run_eval.py --rag --write-baseline`"
        )
    if not latest_path.exists():
        raise CheckError(f"latest RAG report does not exist: {latest_path}")
    baseline_report = load_report(baseline_path)
    latest_report = load_report(latest_path)
    fixture_mismatch = tuple(
        key
        for key in (
            "lesson_fixture_sha",
            "multiturn_fixture_sha",
            "lesson_sample",
            "settings",
        )
        if baseline_report.get(key) != latest_report.get(key)
    )
    baseline = flatten(baseline_report)
    latest = flatten(latest_report)
    missing = tuple(sorted(set(baseline) - set(latest)))
    added = tuple(sorted(set(latest) - set(baseline)))
    deltas: list[MetricDelta] = []
    failures: list[GateFailure] = []
    for name, before in sorted(baseline.items()):
        if name not in latest:
            continue
        after = latest[name]
        delta = MetricDelta(name, before, after)
        deltas.append(delta)
        allowed = _band(name, band)
        if name in COUNT_METRICS:
            if after != before:
                failures.append(GateFailure(delta, allowed, "count"))
        elif name in RISE_METRICS:
            if after > before + allowed:
                failures.append(GateFailure(delta, allowed, "rise"))
        elif name in DROP_METRICS:
            if after < before - allowed:
                failures.append(GateFailure(delta, allowed, "drop"))
    return RagCheckReport(
        baseline=baseline_path,
        latest=latest_path,
        deltas=tuple(deltas),
        failures=tuple(failures),
        missing=missing,
        added=added,
        fixture_mismatch=fixture_mismatch,
    )


def render_check(report: RagCheckReport) -> str:
    """A short gate summary."""
    lines = [
        f"baseline: {report.baseline}",
        f"latest:   {report.latest}",
    ]
    for delta in report.deltas:
        if abs(delta.delta) > 1e-9:
            lines.append(
                f"  {delta.name:<44} {delta.baseline:.4f} -> "
                f"{delta.latest:.4f} ({delta.delta:+.4f})"
            )
    if report.fixture_mismatch:
        lines.append("  fixture mismatch: " + ", ".join(report.fixture_mismatch))
    if report.missing:
        lines.append("  missing: " + ", ".join(report.missing))
    if report.added:
        lines.append("  added: " + ", ".join(report.added))
    if report.failures:
        lines.append("failures:")
        for failure in report.failures:
            lines.append(
                f"  {failure.delta.name}: {failure.direction} "
                f"{failure.delta.delta:+.4f} (band {failure.band:.4f})"
            )
    lines.append("gate: " + ("PASS" if report.passed else "FAIL"))
    return "\n".join(lines)


__all__ = [
    "COUNT_METRICS",
    "CheckError",
    "DROP_METRICS",
    "GateFailure",
    "MetricDelta",
    "RISE_METRICS",
    "RagCheckReport",
    "check_rag",
    "render_check",
]
