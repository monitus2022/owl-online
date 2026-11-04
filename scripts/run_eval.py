"""Run the O.W.L. eval.

Params and dispatch only; the run logic lives in `eval`.

Run:
  uv run python scripts/run_eval.py
  uv run python scripts/run_eval.py --write-baseline
  uv run python scripts/run_eval.py --check
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from eval.check import CheckError, check, load_thresholds, render_check  # noqa: E402
from eval.report import render_run  # noqa: E402
from eval.results import RESULTS_DIR  # noqa: E402
from eval.runner import run  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the O.W.L. eval")
    parser.add_argument("--gold", type=Path, default=REPO / "eval" / "gold" / "questions.jsonl")
    parser.add_argument("--chunks", type=Path, default=REPO / "data" / "chunks.jsonl")
    parser.add_argument("--index", type=Path, default=REPO / "data" / "index" / "chroma")
    parser.add_argument("--cache", type=Path, default=REPO / "eval" / ".cache")
    parser.add_argument("--results", type=Path, default=RESULTS_DIR)
    parser.add_argument("--baseline", type=Path, default=None)
    parser.add_argument(
        "--thresholds", type=Path, default=REPO / "eval" / "thresholds.toml"
    )
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--sample", type=int, default=15)
    parser.add_argument(
        "--embedder-model",
        default=None,
        help="override the local/Bedrock embedder model slug",
    )
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--latest",
        type=Path,
        default=None,
        help="gate this CSV instead of the newest timestamped run",
    )
    args = parser.parse_args()
    if args.check and args.write_baseline:
        parser.error("--check and --write-baseline are mutually exclusive")
    if args.latest is not None and not args.check:
        parser.error("--latest is only used with --check")

    try:
        thresholds = load_thresholds(args.thresholds)
    except CheckError as error:
        print(error, file=sys.stderr)
        return 1
    baseline = args.baseline or REPO / thresholds.baseline

    if args.check:
        try:
            report = check(args.results, baseline, args.thresholds, args.latest)
        except CheckError as error:
            print(error, file=sys.stderr)
            return 1
        print(render_check(report))
        return 0 if report.passed else 1

    run_report = asyncio.run(
        run(
            gold_path=args.gold,
            chunks_path=args.chunks,
            index_dir=args.index,
            cache_dir=args.cache,
            results_dir=args.results,
            baseline=baseline,
            k=args.k,
            sample=args.sample,
            pin_baseline=args.write_baseline,
            embedder_model=args.embedder_model,
        )
    )
    print(render_run(run_report))
    print(
        "next: write a run record in docs/runs/ "
        f"(run id {run_report.run_path.stem}; see docs/runs/README.md)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())