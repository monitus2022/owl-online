"""Baseline diff for `run_eval.py --check`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from eval.results import (
    MetricDelta,
    diff_results,
    latest_run,
    metric_keys,
    read_results,
)

MetricKey = tuple[str, str, str]


class CheckError(RuntimeError):
    """The check cannot run: no result files, or no pinned baseline."""


@dataclass(frozen=True)
class CheckReport:
    """Baseline and latest run, with the metrics that moved or went missing."""

    baseline: Path
    latest: Path
    missing: tuple[MetricKey, ...]
    added: tuple[MetricKey, ...]
    deltas: tuple[MetricDelta, ...]


def check(results_dir: Path, baseline: Path) -> CheckReport:
    """Diff the newest run against the pinned baseline."""
    latest = latest_run(results_dir)
    if latest is None:
        raise CheckError(f"no runs in {results_dir}; run the eval first")
    if not baseline.exists():
        raise CheckError(
            f"no baseline at {baseline}; run once with --write-baseline to pin one"
        )

    baseline_rows = read_results(baseline)
    latest_rows = read_results(latest)
    baseline_keys = metric_keys(baseline_rows)
    latest_keys = metric_keys(latest_rows)
    return CheckReport(
        baseline=baseline,
        latest=latest,
        missing=tuple(sorted(baseline_keys - latest_keys)),
        added=tuple(sorted(latest_keys - baseline_keys)),
        deltas=tuple(diff_results(baseline_rows, latest_rows)),
    )


def _delta_line(delta: MetricDelta) -> str:
    sign = "+" if delta.delta >= 0 else ""
    return (
        f"  {delta.config:<10} {delta.slice:<22} {delta.metric:<18} "
        f"baseline={delta.baseline:.4f} latest={delta.latest:.4f} "
        f"delta={sign}{delta.delta:.4f}"
    )


def render_check(report: CheckReport) -> str:
    """Render the baseline diff as the text the CLI prints."""
    lines = [f"baseline: {report.baseline}", f"latest:   {report.latest}"]
    if report.missing:
        lines.append("metrics missing from the latest run:")
        lines.extend(f"  {key}" for key in report.missing)
    if report.added:
        lines.append("metrics only in the latest run:")
        lines.extend(f"  {key}" for key in report.added)
    if not report.deltas:
        lines.append("no comparable metrics")
        return "\n".join(lines)
    lines.append("deltas:")
    lines.extend(_delta_line(delta) for delta in report.deltas)
    return "\n".join(lines)