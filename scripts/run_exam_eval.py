"""Run a subject exam-bank evaluation (#191, #261).

The command needs the local bank, pack, corpus and model keys because the bank
prose and corpus are not in git. It runs the deterministic checks, the independent
model checks and the short-answer calibration, then prints the record summary.

Run:
    uv run python scripts/run_exam_eval.py
    uv run python scripts/run_exam_eval.py --subject charms
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

from app.exam.bank import load_exam_bank  # noqa: E402
from eval.exam import render_report, run_exam_eval  # noqa: E402

FIXTURES = REPO / "eval" / "exam" / "fixtures"
# The five subjects with published banks; the taxonomy has twelve subjects.
SUBJECTS = ("dada", "charms", "potions", "transfiguration", "herbology")


def calibration_file(subject: str) -> Path:
    """DADA keeps the original fixture name; later subjects are suffixed."""
    if subject == "dada":
        return FIXTURES / "calibration.jsonl"
    return FIXTURES / f"calibration-{subject}.jsonl"


def resolve_paths(
    subject: str,
    bank: Path | None = None,
    calibration: Path | None = None,
) -> tuple[Path, Path]:
    """Resolve the bank and calibration paths for a subject."""
    bank_path = bank if bank is not None else REPO / "data" / "exams" / subject
    calibration_path = (
        calibration if calibration is not None else calibration_file(subject)
    )
    return bank_path, calibration_path


def coverage_targets_for(subject: str, skip: bool) -> bool:
    """The coverage targets are DADA-specific; other subjects skip them."""
    return subject == "dada" and not skip


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", choices=SUBJECTS, default=None)
    parser.add_argument("--bank", type=Path, default=None)
    parser.add_argument("--subjects", type=Path, default=REPO / "data" / "subjects")
    parser.add_argument("--chunks", type=Path, default=REPO / "data" / "chunks.jsonl")
    parser.add_argument("--calibration", type=Path, default=None)
    parser.add_argument("--embedder-provider", default="local")
    parser.add_argument("--embedder-model", default=None)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--no-independent", action="store_true")
    parser.add_argument("--no-calibration", action="store_true")
    parser.add_argument(
        "--skip-coverage-targets",
        action="store_true",
        help=(
            "skip the DADA topic, difficulty and one-item-per-material gate; "
            "non-DADA subjects skip the DADA targets automatically"
        ),
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="optional local JSON artifact under the gitignored data tree",
    )
    args = parser.parse_args()

    subject = args.subject
    bank_subject = None
    if args.bank is not None:
        try:
            bank_subject = load_exam_bank(args.bank).manifest.subject
        except Exception as error:
            parser.error(f"cannot read bank {args.bank}: {error}")
        if subject is None:
            subject = bank_subject
        elif subject != bank_subject:
            parser.error(
                f"--subject {subject} does not match bank subject {bank_subject}"
            )
    elif subject is None:
        subject = "dada"
    bank_path, calibration_path = resolve_paths(
        subject, bank=args.bank, calibration=args.calibration
    )
    if not args.no_calibration and not calibration_path.is_file():
        parser.error(
            f"calibration set not found: {calibration_path} "
            "(pass --no-calibration to skip)"
        )
    report = asyncio.run(
        run_exam_eval(
            bank_path=bank_path,
            subjects_path=args.subjects,
            chunks_path=args.chunks,
            calibration_path=calibration_path,
            embedder_provider=args.embedder_provider,
            embedder_model=args.embedder_model,
            concurrency=args.concurrency,
            independent=not args.no_independent,
            calibration=not args.no_calibration,
            coverage_targets=coverage_targets_for(
                subject, args.skip_coverage_targets
            ),
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
