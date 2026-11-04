"""Baseline diff and eval gate for `run_eval.py --check`."""

from __future__ import annotations

import math
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from eval.results import (
    REPO,
    MetricDelta,
    diff_results,
    latest_run,
    manifest_mismatch,
    metric_keys,
    read_results,
)

MetricKey = tuple[str, str, str]

THRESHOLDS_PATH = REPO / "eval" / "thresholds.toml"

RETRIEVAL_METRICS = frozenset({"retrieval_n", "hit_at_k", "recall_at_k", "mrr"})
ABSTENTION_METRICS = frozenset({"abstention_n", "abstention_refused", "abstention_rate"})
GENERATION_METRICS = frozenset(
    {
        "generation_n",
        "answered",
        "abstained",
        "f1",
        "faithfulness_n",
        "faithful",
        "faithfulness_rate",
        "judge_correct",
        "judge_partial",
        "judge_wrong",
        "judge_correct_rate",
        "grounded",
        "judge_parse_failures",
        "faithful_parse_failures",
    }
)
UNANSWERABLE_SLICES = frozenset({"near_miss_unanswerable", "off_topic"})

# Metrics the gate compares. EM is reported but not gated: it is structurally
# low for sentence answers.
GATED_METRICS = RETRIEVAL_METRICS | ABSTENTION_METRICS | GENERATION_METRICS

# Count metrics use the base band directly. A change in any of them means the
# gold set, the judged sample or the answerability mix moved, which makes the
# rate deltas incomparable.
COUNT_METRICS = frozenset(
    {
        "retrieval_n",
        "abstention_n",
        "abstention_refused",
        "generation_n",
        "answered",
        "abstained",
        "faithfulness_n",
        "faithful",
        "judge_correct",
        "judge_partial",
        "judge_wrong",
        "grounded",
        "judge_parse_failures",
        "faithful_parse_failures",
    }
)

# Rate metric -> the count that sets its denominator, used for the 1/n floor.
RATE_DENOMINATOR = {
    "hit_at_k": "retrieval_n",
    "recall_at_k": "retrieval_n",
    "mrr": "retrieval_n",
    "f1": "generation_n",
    "faithfulness_rate": "faithfulness_n",
    "judge_correct_rate": "faithfulness_n",
    "abstention_rate": "abstention_n",
}


class CheckError(RuntimeError):
    """The check cannot run: no result files, no baseline, or a bad config."""


@dataclass(frozen=True)
class Thresholds:
    """The baseline path and the absolute bands keyed by metric."""

    baseline: str
    bands: Mapping[str, float]

    def band(self, metric: str, n: float | None) -> float:
        """The band for one metric, widened to one item for rate metrics."""
        base = self.bands[metric]
        if metric in COUNT_METRICS or n is None or n <= 0:
            return base
        return max(base, 1.0 / n)


@dataclass(frozen=True)
class GateFailure:
    """One metric that moved further than its band allows."""

    delta: MetricDelta
    band: float

    @property
    def drop(self) -> float:
        return -self.delta.delta

    @property
    def change(self) -> float:
        return self.delta.delta


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
    missing_baseline: tuple[MetricKey, ...] = ()
    invalid: tuple[MetricKey, ...] = ()
    thresholds: Thresholds | None = None

    @property
    def passed(self) -> bool:
        """True only when every gated metric was compared and stayed in band."""
        return (
            bool(self.deltas)
            and not self.failures
            and not self.failing_missing
            and not self.missing_baseline
            and not self.invalid
        )


def _expected_metrics(slice_name: str) -> frozenset[str]:
    """The gated metrics a slice must carry, based on what the run emits."""
    if slice_name == "overall":
        return GATED_METRICS
    if slice_name in UNANSWERABLE_SLICES:
        return ABSTENTION_METRICS
    return RETRIEVAL_METRICS | GENERATION_METRICS


def load_thresholds(path: Path = THRESHOLDS_PATH) -> Thresholds:
    """Read and validate the gate thresholds from TOML."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CheckError(f"cannot read thresholds at {path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise CheckError(f"invalid TOML in {path}: {exc}") from exc

    try:
        bands = {str(key): float(value) for key, value in data["bands"].items()}
    except (KeyError, TypeError, ValueError) as exc:
        raise CheckError(f"invalid bands in {path}: {exc}") from exc

    unknown = set(bands) - GATED_METRICS
    missing = GATED_METRICS - set(bands)
    if unknown:
        names = ", ".join(sorted(unknown))
        raise CheckError(f"unknown gated metrics in {path}: {names}")
    if missing:
        names = ", ".join(sorted(missing))
        raise CheckError(f"missing gated metrics in {path}: {names}")
    return Thresholds(
        baseline=str(data.get("baseline", "eval/results/baseline.csv")),
        bands=bands,
    )


def _number(row: Mapping[str, str] | None) -> float | None:
    """A finite float from a result cell, or None when absent or invalid."""
    if row is None:
        return None
    try:
        value = float(row["value"])
    except (KeyError, TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def check(
    results_dir: Path,
    baseline: Path | None = None,
    thresholds_path: Path = THRESHOLDS_PATH,
) -> CheckReport:
    """Diff the newest run against the pinned baseline and apply the gate."""
    thresholds = load_thresholds(thresholds_path)
    if baseline is None:
        baseline = REPO / thresholds.baseline
    latest = latest_run(results_dir)
    if latest is None:
        raise CheckError(f"no runs in {results_dir}; run the eval first")
    if not baseline.exists():
        raise CheckError(
            f"no baseline at {baseline}; run once with --write-baseline to pin one"
        )

    baseline_rows = read_results(baseline)
    latest_rows = read_results(latest)
    if not baseline_rows:
        raise CheckError(f"baseline is empty: {baseline}")
    if not latest_rows:
        raise CheckError(f"latest run is empty: {latest}")
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
    config_slices = {
        (row["config"], row["slice"]) for row in baseline_rows
    } | {(row["config"], row["slice"]) for row in latest_rows}
    expected = {
        (config, slice_name, metric)
        for config, slice_name in config_slices
        for metric in _expected_metrics(slice_name)
    }
    missing = tuple(sorted(baseline_keys - latest_keys))
    failing_missing = tuple(sorted(expected - latest_keys))
    missing_baseline = tuple(sorted(expected - baseline_keys))

    baseline_values = {
        (row["config"], row["slice"], row["metric"]): row for row in baseline_rows
    }
    latest_values = {
        (row["config"], row["slice"], row["metric"]): row for row in latest_rows
    }
    invalid = tuple(
        sorted(
            key
            for key in expected
            if (key in baseline_values and _number(baseline_values[key]) is None)
            or (key in latest_values and _number(latest_values[key]) is None)
        )
    )

    deltas = tuple(diff_results(baseline_rows, latest_rows))
    failures: list[GateFailure] = []
    for delta in deltas:
        if delta.metric not in GATED_METRICS:
            continue
        denominator = RATE_DENOMINATOR.get(delta.metric)
        n = (
            _number(
                latest_values.get(
                    (delta.config, delta.slice, denominator)
                )
            )
            if denominator is not None
            else None
        )
        band = thresholds.band(delta.metric, n)
        if delta.metric in COUNT_METRICS:
            if abs(delta.delta) > band:
                failures.append(GateFailure(delta, band))
        elif delta.delta < -band:
            failures.append(GateFailure(delta, band))

    return CheckReport(
        baseline=baseline,
        latest=latest,
        missing=missing,
        added=tuple(sorted(latest_keys - baseline_keys)),
        deltas=deltas,
        failures=tuple(failures),
        failing_missing=failing_missing,
        missing_baseline=missing_baseline,
        invalid=invalid,
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
        verb = "dropped" if failure.change < 0 else "changed"
        amount = failure.drop if failure.change < 0 else failure.change
        sign = "" if failure.change < 0 else "+"
        lines.append(
            f"  {failure.delta.slice:<22} {failure.delta.metric:<18} "
            f"{verb} {sign}{amount:.4f}, band {failure.band:.4f}"
        )
    for key in report.failing_missing:
        lines.append(f"  missing gated metric from latest: {key}")
    for key in report.missing_baseline:
        lines.append(f"  missing gated metric from baseline: {key}")
    for key in report.invalid:
        lines.append(f"  invalid value: {key}")
    return "\n".join(lines)
