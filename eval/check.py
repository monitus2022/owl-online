"""Baseline diff and eval gate for `run_eval.py --check`."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from eval.results import (
    MetricDelta,
    diff_results,
    latest_run,
    manifest_mismatch,
    metric_keys,
    read_results,
)

MetricKey = tuple[str, str, str]

THRESHOLDS_PATH = Path(__file__).resolve().parents[1] / "eval" / "thresholds.toml"

# Metrics the gate compares. Counts are included with a zero band so a gold-set
# or sample change cannot pass as an ordinary metric movement. EM is reported
# but not gated: it is structurally low for sentence answers.
GATED_METRICS = frozenset(
    {
        "abstention_n",
        "abstention_rate",
        "faithfulness_rate",
        "f1",
        "generation_n",
        "hit_at_k",
        "judge_correct_rate",
        "mrr",
        "recall_at_k",
        "retrieval_n",
    }
)


class CheckError(RuntimeError):
    """The check cannot run: no result files, no baseline, or a bad config."""


@dataclass(frozen=True)
class Thresholds:
    """The baseline path and the allowed absolute drop per metric."""

    baseline: str
    bands: Mapping[str, float]
    slice_bands: Mapping[str, float]

    def band(self, metric: str, slice_name: str) -> float:
        """The band for one metric, using slice overrides where present."""
        if slice_name != "overall" and metric in self.slice_bands:
            return self.slice_bands[metric]
        return self.bands.get(metric, 0.0)


@dataclass(frozen=True)
class GateFailure:
    """One metric that fell further than its band allows."""

    delta: MetricDelta
    band: float

    @property
    def drop(self) -> float:
        return -self.delta.delta


@dataclass(frozen=True)
class CheckReport:
    """Baseline and latest run, with the metrics that moved or went missing."""

    baseline: Path
    latest: Path
    missing: tuple[MetricKey, ...]
    added: tuple[MetricKey, ...]
    deltas: tuple[MetricDelta, ...]
    failures: tuple[GateFailure, ...] = ()
    failing_missing: tuple[MetricKey, ...] = ()
    thresholds: Thresholds | None = None

    @property
    def passed(self) -> bool:
        """True only when every gated metric was compared and stayed in band."""
        return bool(self.deltas) and not self.failures and not self.failing_missing


def load_thresholds(path: Path = THRESHOLDS_PATH) -> Thresholds:
    """Read the gate thresholds from TOML."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    bands = {str(key): float(value) for key, value in data.get("bands", {}).items()}
    slice_bands = {
        str(key): float(value) for key, value in data.get("slice_bands", {}).items()
    }
    unknown = (set(bands) | set(slice_bands)) - GATED_METRICS
    if unknown:
        names = ", ".join(sorted(unknown))
        raise CheckError(f"unknown gated metrics in {path}: {names}")
    return Thresholds(
        baseline=str(data.get("baseline", "eval/results/baseline.csv")),
        bands=bands,
        slice_bands=slice_bands,
    )


def check(
    results_dir: Path,
    baseline: Path,
    thresholds_path: Path = THRESHOLDS_PATH,
) -> CheckReport:
    """Diff the newest run against the pinned baseline and apply the gate."""
    latest = latest_run(results_dir)
    if latest is None:
        raise CheckError(f"no runs in {results_dir}; run the eval first")
    if not baseline.exists():
        raise CheckError(
            f"no baseline at {baseline}; run once with --write-baseline to pin one"
        )

    thresholds = load_thresholds(thresholds_path)
    baseline_rows = read_results(baseline)
    latest_rows = read_results(latest)
    mismatch = manifest_mismatch(baseline_rows, latest_rows)
    if mismatch:
        details = ", ".join(
            f"{field} {before!r} -> {after!r}"
            for field, (before, after) in mismatch.items()
        )
        raise CheckError(
            "baseline and latest run used different configurations "
            f"({details}); rerun with --write-baseline after a deliberate change"
        )
    baseline_keys = metric_keys(baseline_rows)
    latest_keys = metric_keys(latest_rows)
    missing = tuple(sorted(baseline_keys - latest_keys))
    deltas = tuple(diff_results(baseline_rows, latest_rows))
    failures = tuple(
        GateFailure(delta, thresholds.band(delta.metric, delta.slice))
        for delta in deltas
        if delta.metric in GATED_METRICS
        and delta.delta < -thresholds.band(delta.metric, delta.slice)
    )
    return CheckReport(
        baseline=baseline,
        latest=latest,
        missing=missing,
        added=tuple(sorted(latest_keys - baseline_keys)),
        deltas=deltas,
        failures=failures,
        failing_missing=tuple(key for key in missing if key[2] in GATED_METRICS),
        thresholds=thresholds,
    )


def _delta_line(delta: MetricDelta) -> str:
    sign = "+" if delta.delta >= 0 else ""
    return (
        f"  {delta.config:<10} {delta.slice:<22} {delta.metric:<18} "
        f"baseline={delta.baseline:.4f} latest={delta.latest:.4f} "
        f"delta={sign}{delta.delta:.4f}"
    )


def render_check(report: CheckReport) -> str:
    """Render the baseline diff and the gate verdict."""
    lines = [f"baseline: {report.baseline}", f"latest:   {report.latest}"]
    if report.missing:
        lines.append("metrics missing from the latest run:")
        lines.extend(f"  {key}" for key in report.missing)
    if report.added:
        lines.append("metrics only in the latest run:")
        lines.extend(f"  {key}" for key in report.added)
    if report.deltas:
        lines.append("deltas:")
        lines.extend(_delta_line(delta) for delta in report.deltas)
    else:
        lines.append("no comparable metrics")

    if report.passed:
        lines.append("gate: PASS")
        return "\n".join(lines)

    lines.append("gate: FAIL")
    for failure in report.failures:
        lines.append(
            f"  {failure.delta.slice:<22} {failure.delta.metric:<18} "
            f"dropped {failure.drop:.4f}, band {failure.band:.4f}"
        )
    for key in report.failing_missing:
        lines.append(f"  missing gated metric: {key}")
    return "\n".join(lines)
