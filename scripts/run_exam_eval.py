"""Run the DADA bank evaluation (#191).

The command needs the local bank, pack, corpus and model keys because the bank
prose and corpus are not in git. It runs the deterministic checks, the independent
model checks and the short-answer calibration, then prints the record summary.

Run:
    uv run python scripts/run_exam_eval.py
    uv run python scripts/run_exam_eval.py --no-independent --no-calibration
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from eval.exam import render_report, run_exam_eval  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank", type=Path, default=REPO / "data" / "exams" / "dada")
    parser.add_argument("--subjects", type=Path, default=REPO / "data" / "subjects")
    parser.add_argument("--chunks", type=Path, default=REPO / "data" / "chunks.jsonl")
    parser.add_argument(
        "--calibration",
        type=Path,
        default=REPO / "eval" / "exam" / "fixtures" / "calibration.jsonl",
    )
    parser.add_argument("--embedder-provider", default="local")
    parser.add_argument("--embedder-model", default=None)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--no-independent", action="store_true")
    parser.add_argument("--no-calibration", action="store_true")
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="optional local JSON artifact under the gitignored data tree",
    )
    args = parser.parse_args()

    report = asyncio.run(
        run_exam_eval(
            bank_path=args.bank,
            subjects_path=args.subjects,
            chunks_path=args.chunks,
            calibration_path=args.calibration,
            embedder_provider=args.embedder_provider,
            embedder_model=args.embedder_model,
            concurrency=args.concurrency,
            independent=not args.no_independent,
            calibration=not args.no_calibration,
        )
    )
    print(render_report(report))
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(dataclasses.asdict(report), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {args.json}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
