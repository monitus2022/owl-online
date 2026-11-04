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

RETRIEVAL_GATED = frozenset({"retrieval_n", "hit_at_k", "recall_at_k", "mrr"})
ABSTENTION_GATED = frozenset({"abstention_n", "abstention_rate"})
GENERATION_GATED = frozenset(
    {
        "generation_n",
        "judged",
        "f1",
        "faithfulness_n",
        "faithfulness_rate",
        "judge_correct_rate",
        "grounded_rate",
        "abstained_rate",
        "judge_parse_failures",
        "faithful_parse_failures",
    }
)

# Denominator counts must not change; a gold-set or sample edit would otherwise
# hide inside a rate. `judged` and `faithfulness_n` are answerability outcomes:
# they fail on a drop (over-abstention) but may rise when abstentions fall.
DENOMINATOR_COUNTS = frozenset(
    {"retrieval_n", "abstention_n", "generation_n"}
)

# Quality metrics fail on a drop; over-abstention and parser failures fail on a
# rise. EM is reported but not gated: it is structurally low for sentence answers.
DROP_METRICS = frozenset(
    {
        "hit_at_k",
        "recall_at_k",
        "mrr",
        "f1",
        "faithfulness_rate",
        "judge_correct_rate",
        "grounded_rate",
        "abstention_rate",
        "judged",
        "faithfulness_n",
    }
)
RISE_METRICS = frozenset(
    {"abstained_rate", "judge_parse_failures", "faithful_parse_failures"}
)

GATED_METRICS = (
    RETRIEVAL_GATED | ABSTENTION_GATED | GENERATION_GATED
)

# Rate metric -> the count that sets its denominator, used for the 1/n floor.
RATE_DENOMINATOR = {
    "hit_at_k": "retrieval_n",
    "recall_at_k": "retrieval_n",
    "mrr": "retrieval_n",
    "f1": "generation_n",
    "faithfulness_rate": "faithfulness_n",
    "judge_correct_rate": "judged",
    "grounded_rate": "generation_n",
    "abstained_rate": "generation_n",
    "abstention_rate": "abstention_n",
}


class CheckError(RuntimeError):
    """The check cannot run: no result files, no baseline, or a bad config."""


@dataclass(frozen=True)
class Thresholds:
    """The baseline path, the absolute bands and the slice kinds."""

    baseline: str
    bands: Mapping[str, float]
    slice_kinds: Mapping[str, str]

    def band(self, metric: str, n: float | None) -> float:
        """The band for one metric, widened to one item for rate metrics."""
        base = self.bands[metric]
        if metric in DENOMINATOR_COUNTS or metric in {
            "judge_parse_failures",
            "faithful_parse_failures",
        }:
            return base
        if n is None or n <= 0:
            return base
        return max(base, 1.0 / n)


@dataclass(frozen=True)
class GateFailure:
    """One metric that moved further than its band allows."""

    delta: MetricDelta
    band: float
    direction: str

    @property
    def amount(self) -> float:
        return abs(self.delta.delta)


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


def _expected_metrics(
    slice_name: str, slice_kinds: Mapping[str, str]
) -> frozenset[str]:
    """The gated metrics a slice must carry, based on its gold-set kind."""
    if slice_name == "overall":
        return GATED_METRICS
    kind = slice_kinds.get(slice_name)
    if kind is None:
        raise CheckError(
            f"unknown slice {slice_name!r}; add it to [slice_kinds] in "
            "eval/thresholds.toml"
        )
    if kind == "unanswerable":
        return ABSTENTION_GATED
    return RETRIEVAL_GATED | GENERATION_GATED


def _finite(value: object) -> float | None:
    """A finite, non-boolean float, or None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def load_thresholds(path: Path = THRESHOLDS_PATH) -> Thresholds:
    """Read and validate the gate thresholds from TOML."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CheckError(f"cannot read thresholds at {path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise CheckError(f"invalid TOML in {path}: {exc}") from exc

    raw_bands = data.get("bands")
    if not isinstance(raw_bands, dict):
        raise CheckError(f"missing [bands] table in {path}")
    bands: dict[str, float] = {}
    for key, value in raw_bands.items():
        number = _finite(value)
        if number is None or number < 0:
            raise CheckError(f"band for {key!r} must be a finite non-negative number")
        bands[str(key)] = number

    unknown = set(bands) - GATED_METRICS
    missing = GATED_METRICS - set(bands)
    if unknown:
        names = ", ".join(sorted(unknown))
        raise CheckError(f"unknown gated metrics in {path}: {names}")
    if missing:
        names = ", ".join(sorted(missing))
        raise CheckError(f"missing gated metrics in {path}: {names}")

    raw_kinds = data.get("slice_kinds")
    if not isinstance(raw_kinds, dict) or not raw_kinds:
        raise CheckError(f"missing [slice_kinds] table in {path}")
    slice_kinds: dict[str, str] = {}
    for key, value in raw_kinds.items():
        if value not in {"answerable", "unanswerable"}:
            raise CheckError(
                f"slice kind for {key!r} must be 'answerable' or 'unanswerable'"
            )
        slice_kinds[str(key)] = str(value)

    return Thresholds(
        baseline=str(data.get("baseline", "eval/results/baseline.csv")),
        bands=bands,
        slice_kinds=slice_kinds,
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
    latest_path: Path | None = None,
) -> CheckReport:
    """Diff the newest run against the pinned baseline and apply the gate."""
    thresholds = load_thresholds(thresholds_path)
    if baseline is None:
        baseline = REPO / thresholds.baseline
    latest = latest_path if latest_path is not None else latest_run(results_dir)
    if latest is None:
        raise CheckError(f"no runs in {results_dir}; run the eval first")
    if not latest.exists():
        raise CheckError(f"latest run does not exist: {latest}")
    if latest.resolve() == baseline.resolve():
        raise CheckError(
            f"latest run and baseline are the same file: {latest}; "
            "gate the run the job just produced"
        )
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
    if baseline_rows[0].get("run_id") == latest_rows[0].get("run_id"):
        raise CheckError(
            "latest run is the baseline copy "
            f"({latest_rows[0].get('run_id')}); gate a fresh run"
        )
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
        for metric in _expected_metrics(slice_name, thresholds.slice_kinds)
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
            for key, row in {**baseline_values, **latest_values}.items()
            if key[2] in GATED_METRICS
            and (
                (key in baseline_values and _number(baseline_values[key]) is None)
                or (key in latest_values and _number(latest_values[key]) is None)
            )
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
        if delta.metric in DENOMINATOR_COUNTS:
            if abs(delta.delta) > band:
                failures.append(GateFailure(delta, band, "changed"))
        elif delta.metric in RISE_METRICS:
            if delta.delta > band:
                failures.append(GateFailure(delta, band, "rose"))
        elif delta.delta < -band:
            failures.append(GateFailure(delta, band, "dropped"))

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
        if failure.direction == "changed":
            amount = failure.delta.delta
            sign = "+" if amount >= 0 else ""
        elif failure.direction == "rose":
            amount = failure.delta.delta
            sign = "+"
        else:
            amount = -failure.delta.delta
            sign = ""
        lines.append(
            f"  {failure.delta.config:<10} {failure.delta.slice:<22} "
            f"{failure.delta.metric:<18} {failure.direction} "
            f"{sign}{amount:.4f}, band {failure.band:.4f}"
        )
    for key in report.failing_missing:
        lines.append(f"  missing gated metric from latest: {key}")
    for key in report.missing_baseline:
        lines.append(f"  missing gated metric from baseline: {key}")
    for key in report.invalid:
        lines.append(f"  invalid value: {key}")
    return "\n".join(lines)
