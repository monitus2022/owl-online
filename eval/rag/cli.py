"""CLI for the lesson + multi-turn RAG eval (#248)."""

from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
from pathlib import Path

from app.config import Settings
from eval.rag.check import CheckError, check_rag, render_check
from eval.rag.report import (
    latest_report,
    load_report,
    render_report,
    to_dict,
    write_report,
)
from eval.rag.runner import run_rag_eval
from eval.results import REPO, RESULTS_DIR


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the RAG eval")
    parser.add_argument(
        "--lesson",
        type=Path,
        default=REPO / "eval" / "rag" / "fixtures" / "lesson.jsonl",
    )
    parser.add_argument(
        "--multiturn",
        type=Path,
        default=REPO / "eval" / "rag" / "fixtures" / "multiturn.jsonl",
    )
    parser.add_argument("--cache", type=Path, default=REPO / "eval" / ".cache" / "rag")
    parser.add_argument("--results", type=Path, default=RESULTS_DIR)
    parser.add_argument(
        "--baseline",
        type=Path,
        default=RESULTS_DIR / "rag-baseline.json",
    )
    parser.add_argument("--sample", type=int, default=30)
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument(
        "--force-baseline",
        action="store_true",
        help="replace a baseline even when the fixture or settings differ",
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--latest",
        type=Path,
        default=None,
        help="gate this report instead of the newest rag-*.json",
    )
    return parser


def _check(args: argparse.Namespace) -> int:
    latest = args.latest or latest_report(args.results)
    if latest is None:
        print(f"no RAG reports in {args.results}; run the eval first", file=sys.stderr)
        return 1
    try:
        report = check_rag(args.baseline, latest)
    except CheckError as error:
        print(error, file=sys.stderr)
        return 1
    print(render_check(report))
    return 0 if report.passed else 1


async def _run(args: argparse.Namespace) -> int:
    settings = Settings(
        persona=True,
        lesson_mode=True,
        lesson_fallback=True,
    )
    report = await run_rag_eval(
        settings=settings,
        lesson_path=args.lesson,
        multiturn_path=args.multiturn,
        cache_dir=args.cache,
        sample=args.sample,
    )
    path = args.results / f"rag-{report.run_id}.json"
    write_report(path, report)
    print(render_report(report))
    if args.write_baseline:
        payload = to_dict(report)
        if args.baseline.exists() and not args.force_baseline:
            existing = load_report(args.baseline)
            changed = [
                key
                for key in (
                    "lesson_fixture_sha",
                    "multiturn_fixture_sha",
                    "lesson_sample",
                    "settings",
                )
                if existing.get(key) != payload.get(key)
            ]
            if changed:
                print(
                    "refusing to replace the baseline: "
                    + ", ".join(changed)
                    + " changed; pass --force-baseline to replace it deliberately",
                    file=sys.stderr,
                )
                return 1
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, args.baseline)
        print(f"pinned baseline: {args.baseline}")
    print(f"wrote {path}")
    print(
        f"next: write a run record in docs/runs/ (run id {report.run_id}; see docs/runs/README.md)"
    )
    return 0 if report.ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.check and args.write_baseline:
        parser.error("--check and --write-baseline are mutually exclusive")
    if args.latest is not None and not args.check:
        parser.error("--latest is only used with --check")
    if args.sample < 1:
        parser.error("--sample must be at least 1")
    if args.write_baseline and args.sample != 30:
        parser.error("--write-baseline requires the pinned --sample 30")
    if args.check:
        return _check(args)
    return asyncio.run(_run(args))


__all__ = ["main"]
