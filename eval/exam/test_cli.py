"""Runner and CLI tests, no network."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from eval.exam.models import BankCheckReport, Check, ExamEvalReport
from eval.exam.runner import render_report

REPO = Path(__file__).resolve().parents[2]


def test_render_report_names_the_subject_and_gate() -> None:
    report = ExamEvalReport(
        bank_version="1.0.0",
        subject="dada",
        deterministic=BankCheckReport(
            checks=[Check("sample", True, "ok")]
        ),
    )
    text = render_report(report)
    assert "exam eval: dada 1.0.0" in text
    assert "gate: PASS" in text


def test_cli_exits_nonzero_on_a_missing_bank(tmp_path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "run_exam_eval.py"),
            "--bank",
            str(tmp_path / "missing"),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
