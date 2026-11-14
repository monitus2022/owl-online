"""Runner and CLI tests, no network."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from app.exam.bank import write_exam_bank
from eval.exam.fixtures import build_bank
from eval.exam.models import (
    BankCheckReport,
    CalibrationReport,
    CalibrationRun,
    Check,
    ExamEvalReport,
    SliceMetrics,
)
from eval.exam.runner import render_report
from scripts.run_exam_eval import (
    calibration_file,
    calibration_repeats_for,
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


def test_calibration_repeats_default_to_three_for_dada() -> None:
    assert calibration_repeats_for("dada", None) == 3
    assert calibration_repeats_for("charms", None) == 1
    assert calibration_repeats_for("dada", 1) == 1
    assert calibration_repeats_for("dada", 5) == 5
    with pytest.raises(ValueError):
        calibration_repeats_for("dada", 0)


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


def test_render_report_shows_the_median_and_representative_run() -> None:
    runs = [
        CalibrationRun(
            exact=0.5, adjacent=1.0, mae=0.25, per_criterion={},
            calls=3, passes=3, retries=0, needs_review=0,
            verbose_delta=0.0, word_count_correlation=0.0,
            gated=SliceMetrics(n=3, exact=0.5, adjacent=1.0, mae=0.25),
            mid_band=SliceMetrics(n=0, exact=0.0, adjacent=0.0, mae=None),
        ),
        CalibrationRun(
            exact=0.5, adjacent=0.875, mae=0.5, per_criterion={},
            calls=3, passes=3, retries=0, needs_review=0,
            verbose_delta=0.0, word_count_correlation=0.0,
            gated=SliceMetrics(n=3, exact=0.5, adjacent=0.875, mae=0.5),
            mid_band=SliceMetrics(n=0, exact=0.0, adjacent=0.0, mae=None),
        ),
    ]
    calibration = CalibrationReport(
        model="judge", provider="openrouter", temperature=0.0,
        prompt_version="v", set_sha256="sha", n=3, exact=0.5,
        adjacent=1.0, mae=0.25, per_criterion={}, calls=6, passes=6,
        retries=0, needs_review=0, verbose_delta=0.0,
        word_count_correlation=0.0,
        gated=SliceMetrics(n=3, exact=0.5, adjacent=1.0, mae=0.25),
        mid_band=SliceMetrics(n=0, exact=0.0, adjacent=0.0, mae=None),
        repeats=2, runs=runs, representative_run=1,
    )
    report = ExamEvalReport(
        bank_version="1.1.0",
        subject="dada",
        deterministic=BankCheckReport(checks=[Check("sample", True, "ok")]),
        calibration=calibration,
    )
    text = render_report(report)
    assert "Calibration (median of 2 runs):" in text
    assert "Calibration stability (gate uses the gated slice):" in text
    assert "representative run 1 of 2" in text
    assert "| 2 | 0.5000 | 0.8750 | 0.5000 | 3 | 0 | FAIL |" in text


def test_render_report_handles_a_missing_mae() -> None:
    run = CalibrationRun(
        exact=0.0, adjacent=0.0, mae=None, per_criterion={},
        calls=1, passes=1, retries=0, needs_review=0,
        verbose_delta=None, word_count_correlation=None,
        gated=SliceMetrics(n=1, exact=0.0, adjacent=0.0, mae=None),
        mid_band=SliceMetrics(n=0, exact=0.0, adjacent=0.0, mae=None),
    )
    calibration = CalibrationReport(
        model="judge", provider="openrouter", temperature=0.0,
        prompt_version="v", set_sha256="sha", n=1, exact=0.0,
        adjacent=0.0, mae=None, per_criterion={}, calls=2, passes=2,
        retries=0, needs_review=0, verbose_delta=None,
        word_count_correlation=None,
        gated=SliceMetrics(n=1, exact=0.0, adjacent=0.0, mae=None),
        mid_band=SliceMetrics(n=0, exact=0.0, adjacent=0.0, mae=None),
        repeats=2, runs=[run, run], representative_run=1,
    )
    report = ExamEvalReport(
        bank_version="1.0.0",
        subject="dada",
        deterministic=BankCheckReport(checks=[Check("sample", True, "ok")]),
        calibration=calibration,
    )
    text = render_report(report)
    assert "MAE=None" in text
    assert "| 1 | 0.0000 | 0.0000 | None |" in text
    assert "representative run 1 of 2" in text


def test_render_report_reports_the_mid_band_without_gating_it() -> None:
    run = CalibrationRun(
        exact=0.9, adjacent=0.9, mae=0.1, per_criterion={},
        calls=4, passes=4, retries=0, needs_review=0,
        verbose_delta=0.0, word_count_correlation=0.0,
        gated=SliceMetrics(n=3, exact=1.0, adjacent=1.0, mae=0.0),
        mid_band=SliceMetrics(n=1, exact=0.0, adjacent=0.0, mae=2.0),
    )
    calibration = CalibrationReport(
        model="judge", provider="openrouter", temperature=0.0,
        prompt_version="v", set_sha256="sha", n=4, exact=0.9,
        adjacent=0.9, mae=0.1, per_criterion={}, calls=4, passes=4,
        retries=0, needs_review=0, verbose_delta=0.0,
        word_count_correlation=0.0,
        gated=SliceMetrics(n=3, exact=1.0, adjacent=1.0, mae=0.0),
        mid_band=SliceMetrics(n=1, exact=0.0, adjacent=0.0, mae=2.0),
        repeats=1, runs=[run], representative_run=1,
    )
    report = ExamEvalReport(
        bank_version="1.0.0",
        subject="dada",
        deterministic=BankCheckReport(checks=[Check("sample", True, "ok")]),
        calibration=calibration,
    )
    text = render_report(report)
    assert "Mid-band completeness (diagnostic, not gated):" in text
    assert "gate: PASS" in text
    assert "| 1 | 1 | 0.0000 | 0.0000 | 2.0000 | 0 |" in text


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


def test_cli_rejects_zero_calibration_repeats() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "run_exam_eval.py"),
            "--subject",
            "dada",
            "--calibration-repeats",
            "0",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "at least 1" in result.stderr


def test_cli_rejects_a_missing_calibration_fixture(tmp_path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "run_exam_eval.py"),
            "--subject",
            "charms",
            "--calibration",
            str(tmp_path / "missing.jsonl"),
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
