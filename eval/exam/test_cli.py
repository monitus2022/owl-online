"""Runner and CLI tests, no network."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from app.exam.bank import write_exam_bank
from eval.exam.fixtures import build_bank
from eval.exam.models import BankCheckReport, Check, ExamEvalReport
from eval.exam.runner import render_report
from scripts.run_exam_eval import (
    calibration_file,
    coverage_targets_for,
    resolve_paths,
)

REPO = Path(__file__).resolve().parents[2]


def test_resolve_paths_defaults_to_the_subject_bank_and_calibration() -> None:
    dada_bank, dada_calibration = resolve_paths("dada")
    assert dada_bank == REPO / "data" / "exams" / "dada"
    assert dada_calibration == REPO / "eval" / "exam" / "fixtures" / "calibration.jsonl"

    charms_bank, charms_calibration = resolve_paths("charms")
    assert charms_bank == REPO / "data" / "exams" / "charms"
    assert (
        charms_calibration
        == REPO / "eval" / "exam" / "fixtures" / "calibration-charms.jsonl"
    )
    assert calibration_file("charms").name == "calibration-charms.jsonl"


def test_resolve_paths_accepts_explicit_overrides(tmp_path) -> None:
    bank = tmp_path / "bank"
    calibration = tmp_path / "calibration.jsonl"
    assert resolve_paths("charms", bank=bank, calibration=calibration) == (
        bank,
        calibration,
    )


def test_coverage_targets_are_dada_only() -> None:
    assert coverage_targets_for("dada", skip=False) is True
    assert coverage_targets_for("dada", skip=True) is False
    assert coverage_targets_for("charms", skip=False) is False


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


def test_cli_rejects_a_missing_calibration_fixture() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "run_exam_eval.py"),
            "--subject",
            "potions",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "calibration set not found" in result.stderr
    assert "--no-calibration" in result.stderr


def test_cli_rejects_a_subject_bank_mismatch(tmp_path) -> None:
    bank, *_ = build_bank()
    write_exam_bank(bank, tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "run_exam_eval.py"),
            "--subject",
            "charms",
            "--bank",
            str(tmp_path),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "does not match bank subject" in result.stderr
