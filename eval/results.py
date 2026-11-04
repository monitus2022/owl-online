"""Eval result CSV and baseline diff (V2 D1, #76).

One run writes one row per (config, slice, metric). Every row repeats the
manifest values, so two runs are comparable even after the manifest changes.
Timestamped runs stay local; the pinned baseline is committed.
"""

from __future__ import annotations

import csv
import re
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.pipeline.retrieve.retriever import QUERY_CANDIDATES

REPO = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO / "config" / "manifest.toml"
RESULTS_DIR = REPO / "eval" / "results"
BASELINE_PATH = RESULTS_DIR / "baseline.csv"
RUN_ID_RE = re.compile(r"^\d{8}T\d{6}Z$")

# Flattened manifest columns. Every result row carries all of them.
MANIFEST_FIELDS = [
    "generator_model",
    "judge_model",
    "reranker_model",
    "reranker_pool",
    "embedder_provider",
    "embedder_model",
    "embedder_dims",
    "chunk_size",
    "chunk_overlap",
    "chunk_min_size",
    "top_k",
    "rrf_k",
    "candidates",
    "judged_sample",
    "gold_hash",
    "rerank_min_score",
]

RESULT_FIELDS = ["run_id", "config", "slice", "metric", "value", *MANIFEST_FIELDS]


def load_manifest(path: Path = MANIFEST_PATH) -> dict:
    """Read the repro manifest."""
    return tomllib.loads(path.read_text(encoding="utf-8"))


def manifest_row(
    manifest: Mapping,
    *,
    embedder_provider: str,
    rerank_enabled: bool,
    top_k: int | None = None,
    reranker_pool: int | None = None,
    candidates: int | None = None,
    judged_sample: int | None = None,
    reranker_model: str | None = None,
    embedder_model: str | None = None,
    embedder_dims: int | None = None,
    gold_hash: str | None = None,
    rerank_min_score: float | None = None,
) -> dict[str, str]:
    """Flatten the manifest plus the run-time choices into CSV columns.

    `top_k`, `reranker_pool`, `candidates` and `judged_sample` can be passed
    when the run used a value other than the manifest default (for example
    `--k` or `--sample`). The model overrides record the effective settings
    when an `OWL_*` variable changes the manifest slug. With rerank off the
    per-leg candidate count is the retriever's own default, not the pool.
    """
    embedder_key = "cloud" if embedder_provider == "bedrock" else "local"
    embedder = manifest["embedder"][embedder_key]
    retrieval = manifest["retrieval"]
    chunking = manifest["chunking"]
    reranker = manifest["reranker"]
    actual_pool = reranker_pool if reranker_pool is not None else reranker["pool"]
    actual_candidates = candidates if candidates is not None else (
        retrieval["candidates"] if rerank_enabled else QUERY_CANDIDATES
    )
    return {
        "generator_model": str(manifest["generator"]["model"]),
        "judge_model": str(manifest["judge"]["model"]),
        "reranker_model": str(
            reranker_model if reranker_model is not None else reranker["model"]
        )
        if rerank_enabled
        else "none",
        "reranker_pool": str(actual_pool) if rerank_enabled else "0",
        "embedder_provider": embedder_provider,
        "embedder_model": str(
            embedder_model if embedder_model is not None else embedder["model"]
        ),
        "embedder_dims": str(
            embedder_dims if embedder_dims is not None else embedder["dimensions"]
        ),
        "chunk_size": str(chunking["size"]),
        "chunk_overlap": str(chunking["overlap"]),
        "chunk_min_size": str(chunking["min_size"]),
        "top_k": str(top_k if top_k is not None else retrieval["top_k"]),
        "rrf_k": str(retrieval["rrf_k"]),
        "candidates": str(actual_candidates),
        "judged_sample": str(judged_sample) if judged_sample is not None else "",
        "gold_hash": gold_hash or "",
        "rerank_min_score": (
            str(rerank_min_score) if rerank_min_score is not None else ""
        ),
    }


def timestamp_run_id(now: datetime | None = None) -> str:
    """A sortable UTC timestamp, used as the run id and the CSV filename."""
    moment = now or datetime.now(UTC)
    return moment.strftime("%Y%m%dT%H%M%SZ")


@dataclass(frozen=True)
class ResultRow:
    """One metric for one configuration and slice, plus the manifest values."""

    run_id: str
    config: str
    slice: str
    metric: str
    value: float | int | str
    manifest: Mapping[str, str]

    def as_dict(self) -> dict[str, str]:
        row = {
            "run_id": self.run_id,
            "config": self.config,
            "slice": self.slice,
            "metric": self.metric,
            "value": str(self.value),
        }
        for field in MANIFEST_FIELDS:
            row[field] = str(self.manifest.get(field, ""))
        return row


def write_results(path: Path, rows: Iterable[ResultRow]) -> None:
    """Write result rows with a stable header."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.as_dict())


def read_results(path: Path) -> list[dict[str, str]]:
    """Read a result CSV as dictionaries."""
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def latest_run(results_dir: Path = RESULTS_DIR) -> Path | None:
    """The newest timestamped CSV, excluding the pinned baseline."""
    candidates = sorted(
        path
        for path in results_dir.glob("*.csv")
        if RUN_ID_RE.fullmatch(path.stem) and path.name != BASELINE_PATH.name
    )
    return candidates[-1] if candidates else None


def copy_baseline(latest: Path, baseline: Path = BASELINE_PATH) -> None:
    """Pin the latest run as the baseline."""
    baseline.parent.mkdir(parents=True, exist_ok=True)
    baseline.write_text(latest.read_text(encoding="utf-8"), encoding="utf-8")


@dataclass(frozen=True)
class MetricDelta:
    """The movement of one metric from the baseline to the latest run."""

    config: str
    slice: str
    metric: str
    baseline: float
    latest: float
    delta: float


def diff_results(
    baseline_rows: Iterable[Mapping[str, str]],
    latest_rows: Iterable[Mapping[str, str]],
) -> list[MetricDelta]:
    """Per-metric deltas, keyed by (config, slice, metric).

    A metric present in only one side is skipped; the caller reports the
    missing keys separately so a renamed metric cannot look like a zero delta.
    """
    latest = {
        (row["config"], row["slice"], row["metric"]): row for row in latest_rows
    }
    deltas: list[MetricDelta] = []
    for row in baseline_rows:
        key = (row["config"], row["slice"], row["metric"])
        other = latest.get(key)
        if other is None:
            continue
        try:
            before = float(row["value"])
            after = float(other["value"])
        except (TypeError, ValueError):
            continue
        deltas.append(
            MetricDelta(
                config=key[0],
                slice=key[1],
                metric=key[2],
                baseline=before,
                latest=after,
                delta=round(after - before, 4),
            )
        )
    return deltas


def metric_keys(rows: Iterable[Mapping[str, str]]) -> set[tuple[str, str, str]]:
    """The (config, slice, metric) keys present in a result file."""
    return {(row["config"], row["slice"], row["metric"]) for row in rows}


def manifest_mismatch(
    baseline_rows: Iterable[Mapping[str, str]],
    latest_rows: Iterable[Mapping[str, str]],
) -> dict[str, tuple[str, str]]:
    """Manifest fields whose recorded values differ between two runs.

    Result rows repeat the manifest, so the first row of each file is enough.
    `--check` refuses to diff runs that were produced with different models,
    chunking or retrieval settings: the deltas would not be comparable.
    """
    baseline = next(iter(baseline_rows), {})
    latest = next(iter(latest_rows), {})
    mismatch: dict[str, tuple[str, str]] = {}
    for field in MANIFEST_FIELDS:
        before = str(baseline.get(field, ""))
        after = str(latest.get(field, ""))
        if before != after:
            mismatch[field] = (before, after)
    return mismatch