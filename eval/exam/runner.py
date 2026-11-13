"""Run a subject bank evaluation (#191): deterministic, independent, calibration."""

from __future__ import annotations

from pathlib import Path

from app.exam.bank import load_exam_bank
from app.grading import judge_llm_from_bank
from app.knowledge.packs import load_subject_pack
from app.pipeline.index.builder import load_chunks, text_hash
from app.providers.factory import make_embedder
from eval.exam.calibration import (
    file_sha256,
    load_calibration,
    run_calibration_repeated,
)
from eval.exam.checks import run_deterministic_checks
from eval.exam.independent import run_independent_checks
from eval.exam.models import ExamEvalReport


def _mae_text(value: float | None) -> str:
    return f"{value:.4f}" if value is not None else "None"


async def run_exam_eval(
    *,
    bank_path: Path,
    subjects_path: Path,
    chunks_path: Path,
    calibration_path: Path,
    embedder_provider: str = "local",
    embedder_model: str | None = None,
    concurrency: int = 4,
    independent: bool = True,
    calibration: bool = True,
    calibration_repeats: int = 1,
    coverage_targets: bool = True,
) -> ExamEvalReport:
    """Load the published bank and run the selected checks."""
    bank = load_exam_bank(bank_path)
    pack = load_subject_pack(subjects_path / bank.manifest.subject)
    chunks = load_chunks(chunks_path)
    index_hash = text_hash(chunks)
    embedder = make_embedder(embedder_provider, model=embedder_model)
    targets = None if coverage_targets else {}
    deterministic = await run_deterministic_checks(
        bank,
        pack,
        {chunk.id: chunk for chunk in chunks},
        index_hash,
        embedder=embedder,
        topic_targets=targets,
        difficulty_targets=targets,
        material_targets=coverage_targets,
    )
    independent_report = None
    calibration_report = None
    if independent or calibration:
        llm = judge_llm_from_bank(bank)
        try:
            if independent:
                independent_report = await run_independent_checks(
                    bank, pack, llm, concurrency=concurrency
                )
            if calibration:
                cases = load_calibration(calibration_path)
                calibration_report = await run_calibration_repeated(
                    bank,
                    cases,
                    llm,
                    repeats=calibration_repeats,
                    set_sha256=file_sha256(calibration_path),
                )
        finally:
            await llm.aclose()
    return ExamEvalReport(
        bank_version=bank.manifest.version,
        subject=bank.manifest.subject,
        deterministic=deterministic,
        independent=independent_report,
        calibration=calibration_report,
    )


def render_report(report: ExamEvalReport) -> str:
    """Render the structure-only summary that goes into the run record."""
    lines = [f"exam eval: {report.subject} {report.bank_version}", "", "Deterministic checks:"]
    for check in report.deterministic.checks:
        gate = "" if check.gated else " (diagnostic)"
        status = "PASS" if check.ok else ("WARN" if not check.gated else "FAIL")
        lines.append(f"  {check.name:22} {status}{gate}  {check.detail}")
    metrics = report.deterministic.metrics
    lines.extend(
        [
            "",
            "Deterministic metrics:",
            f"  max_jaccard={metrics.get('max_jaccard')}",
            f"  max_jaccard_pair={metrics.get('max_jaccard_pair')}",
            f"  max_cosine={metrics.get('max_cosine')}",
            f"  max_cosine_pair={metrics.get('max_cosine_pair')}",
            f"  option_length_bias={metrics.get('option_length_bias')}",
            f"  option_length_mean_gap={metrics.get('option_length_mean_gap')}",
            f"  answer_positions={metrics.get('answer_positions')}",
        ]
    )
    if report.independent is not None:
        independent = report.independent
        lines.extend(
            [
                "",
                "Independent checks:",
                f"  model={independent.model} temperature={independent.temperature} "
                f"prompt={independent.prompt_version}",
                f"  MCQ key matches={independent.mcq_key_matches}/{independent.mcq_total}",
                f"  MCQ mismatches={independent.mcq_mismatch_ids}",
                f"  MCQ ambiguities={independent.mcq_ambiguities}",
                f"  MCQ ambiguity ids={independent.mcq_ambiguous_ids}",
                f"  Short golden={independent.short_golden_ok}/{independent.short_total}",
                f"  Short candidate correct and complete={independent.short_candidate_ok}",
                f"  Short review ids={independent.short_review_ids}",
                f"  Short missing points={independent.short_missing_points}",
                f"  Errors={len(independent.errors)}",
            ]
        )
    if report.calibration is not None:
        calibration = report.calibration
        label = (
            f"Calibration (median of {calibration.repeats} runs):"
            if calibration.repeats > 1
            else "Calibration:"
        )
        lines.extend(
            [
                "",
                label,
                f"  model={calibration.model} provider={calibration.provider} "
                f"temperature={calibration.temperature} "
                f"prompt={calibration.prompt_version}",
                f"  set_sha256={calibration.set_sha256}",
                f"  all cases: n={calibration.n} "
                f"exact={calibration.exact:.4f} "
                f"adjacent={calibration.adjacent:.4f} "
                f"MAE={_mae_text(calibration.mae)}",
                f"  gated:     n={calibration.gated.n} "
                f"exact={calibration.gated.exact:.4f} "
                f"adjacent={calibration.gated.adjacent:.4f} "
                f"MAE={_mae_text(calibration.gated.mae)}",
            ]
        )
        if calibration.mid_band.n:
            lines.append(
                f"  mid-band:  n={calibration.mid_band.n} "
                f"exact={calibration.mid_band.exact:.4f} "
                f"adjacent={calibration.mid_band.adjacent:.4f} "
                f"MAE={_mae_text(calibration.mid_band.mae)}"
            )
        lines.extend(
            [
                f"  per_criterion={calibration.per_criterion}",
                f"  calls={calibration.calls} passes={calibration.passes} "
                f"retries={calibration.retries} needs_review={calibration.needs_review}",
                f"  verbose_delta={calibration.verbose_delta} "
                f"word_count_correlation={calibration.word_count_correlation}",
            ]
        )
        if calibration.repeats > 1:
            lines.extend(
                [
                    "",
                    "Calibration stability (gate uses the gated slice):",
                    "| Run | Gated exact | Gated adjacent | Gated MAE | Calls | Retries | Gate |",
                    "|---|---:|---:|---:|---:|---|---|",
                ]
            )
            for index, run in enumerate(calibration.runs, 1):
                lines.append(
                    f"| {index} | {run.gated.exact:.4f} | "
                    f"{run.gated.adjacent:.4f} | {_mae_text(run.gated.mae)} | "
                    f"{run.calls} | {run.retries} | "
                    f"{'PASS' if run.ok else 'FAIL'} |"
                )
        if calibration.mid_band.n:
            lines.extend(
                [
                    "",
                    "Mid-band completeness (diagnostic, not gated):",
                    "| Run | Cases | Exact | Adjacent | MAE | Needs review |",
                    "|---|---:|---:|---:|---:|---|",
                ]
            )
            for index, run in enumerate(calibration.runs, 1):
                lines.append(
                    f"| {index} | {run.mid_band.n} | "
                    f"{run.mid_band.exact:.4f} | {run.mid_band.adjacent:.4f} | "
                    f"{_mae_text(run.mid_band.mae)} | "
                    f"{run.mid_band.needs_review} |"
                )
        if calibration.repeats > 1 and calibration.representative_run:
            run = calibration.runs[calibration.representative_run - 1]
            cases_label = (
                "Calibration cases (representative run "
                f"{calibration.representative_run} of {calibration.repeats}: "
                f"exact={run.exact:.4f} adjacent={run.adjacent:.4f} "
                f"MAE={_mae_text(run.mae)}):"
            )
        else:
            cases_label = "Calibration cases:"
        lines.extend(
            [
                "",
                cases_label,
                "| Item | Variant | Human | Judge | Delta | Words | Needs review |",
                "|---|---|---:|---:|---:|---:|---|",
            ]
        )
        for detail in calibration.details:
            lines.append(
                f"| `{detail.item_id}` | {detail.variant} | {detail.human} | "
                f"{detail.judge} | {detail.delta} | {detail.word_count} | "
                f"{detail.needs_review} |"
            )
    lines.extend(["", f"gate: {'PASS' if report.ok else 'FAIL'}"])
    return "\n".join(lines)


__all__ = ["render_report", "run_exam_eval"]
