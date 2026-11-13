"""Short-answer judge calibration for a subject exam bank (#191, #261).

The calibration set is committed under eval/exam/fixtures. Each case is an
original student-style answer with human criterion marks. The judge grades each
pass (one answer per item), and the report measures exact and adjacent agreement,
mean absolute error, per-criterion agreement, retries and length bias.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from pathlib import Path

from app.config import settings
from app.exam.bank import ExamBank
from app.grading import AttemptAnswer, grade_attempt
from app.providers.contracts import Llm
from eval.exam.models import CalibrationCase, CalibrationDetail, CalibrationReport

VARIANTS = (
    "full",
    "partial",
    "wrong",
    "verbose",
    "missing_key_term",
    "off_topic",
    "contradictory",
    "blank",
)


class CountingLlm:
    """Count generate() calls so the calibration can report retries."""

    def __init__(self, inner: Llm) -> None:
        self.inner = inner
        self.calls = 0

    async def generate(self, system: str, prompt: str, *, context=None) -> str:
        self.calls += 1
        return await self.inner.generate(system, prompt, context=context)

    def stream(self, system: str, prompt: str, *, context=None):
        return self.inner.stream(system, prompt, context=context)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _non_empty(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def load_calibration(
    path: Path,
    *,
    min_items: int = 8,
    max_items: int = 12,
) -> list[CalibrationCase]:
    """Read and structurally validate the committed calibration set."""
    cases: list[CalibrationCase] = []
    seen: set[tuple[str, str]] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {error}") from error
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number}: calibration row must be an object")
        item_id = _non_empty(row.get("item_id"), "item_id")
        variant = _non_empty(row.get("variant"), "variant")
        pass_name = _non_empty(row.get("pass"), "pass")
        answer = row.get("answer")
        if not isinstance(answer, str):
            raise ValueError(f"{path}:{line_number}: answer must be a string")
        marks = row.get("marks")
        if not isinstance(marks, dict) or not marks:
            raise ValueError(f"{path}:{line_number}: marks must be a non-empty object")
        clean_marks: dict[str, int] = {}
        for criterion_id, mark in marks.items():
            if not isinstance(criterion_id, str) or not criterion_id.strip():
                raise ValueError(f"{path}:{line_number}: criterion ids must be strings")
            if not isinstance(mark, int) or isinstance(mark, bool) or mark < 0:
                raise ValueError(
                    f"{path}:{line_number}: marks must be non-negative integers"
                )
            clean_marks[criterion_id] = mark
        if variant not in VARIANTS:
            raise ValueError(f"{path}:{line_number}: unknown variant {variant!r}")
        if variant != "blank" and not answer.strip():
            raise ValueError(
                f"{path}:{line_number}: only the blank variant may have an empty answer"
            )
        key = (pass_name, item_id)
        if key in seen:
            raise ValueError(f"{path}:{line_number}: duplicate case {key}")
        seen.add(key)
        cases.append(
            CalibrationCase(
                item_id=item_id,
                variant=variant,
                pass_name=pass_name,
                answer=answer,
                marks=clean_marks,
                note=str(row.get("note", "")),
            )
        )
    item_ids = {case.item_id for case in cases}
    if not min_items <= len(item_ids) <= max_items:
        raise ValueError(
            f"{path}: calibration set has {len(item_ids)} items; "
            f"expected {min_items}-{max_items}"
        )
    per_item: dict[str, int] = {}
    for case in cases:
        per_item[case.item_id] = per_item.get(case.item_id, 0) + 1
    bad_counts = {
        item_id: count for item_id, count in per_item.items()
        if not 3 <= count <= 4
    }
    if bad_counts:
        raise ValueError(
            f"{path}: each item needs 3-4 answers; got {bad_counts}"
        )
    return cases


def _validate_against_bank(bank: ExamBank, cases: Sequence[CalibrationCase]) -> None:
    for case in cases:
        item = bank.find_item(case.item_id)
        if item is None:
            raise ValueError(f"calibration item {case.item_id!r} is not in the bank")
        if item.kind != "short_answer":
            raise ValueError(f"calibration item {case.item_id!r} is not a short answer")
        expected = {criterion.criterion_id for criterion in item.rubric}
        if set(case.marks) != expected:
            raise ValueError(
                f"{case.item_id}: marks must name exactly {sorted(expected)}"
            )
        for criterion in item.rubric:
            if case.marks[criterion.criterion_id] > criterion.max_marks:
                raise ValueError(
                    f"{case.item_id}: {criterion.criterion_id} mark exceeds "
                    f"{criterion.max_marks}"
                )


def _pearson(pairs: Sequence[tuple[float, float]]) -> float | None:
    if len(pairs) < 2:
        return None
    mean_x = sum(x for x, _ in pairs) / len(pairs)
    mean_y = sum(y for _, y in pairs) / len(pairs)
    cov = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
    var_x = sum((x - mean_x) ** 2 for x, _ in pairs)
    var_y = sum((y - mean_y) ** 2 for _, y in pairs)
    if not var_x or not var_y:
        return None
    return cov / math.sqrt(var_x * var_y)


async def run_calibration(
    bank: ExamBank,
    cases: Sequence[CalibrationCase],
    llm: Llm,
    *,
    set_sha256: str = "",
) -> CalibrationReport:
    """Run the judge over the calibration set and compare with the human marks."""
    _validate_against_bank(bank, cases)
    by_pass: dict[str, list[CalibrationCase]] = {}
    for case in cases:
        by_pass.setdefault(case.pass_name, []).append(case)

    counting = CountingLlm(llm)
    details: list[CalibrationDetail] = []
    passes_with_calls = 0
    for group in by_pass.values():
        if any(case.answer.strip() for case in group):
            passes_with_calls += 1
        result = await grade_attempt(
            bank,
            [case.item_id for case in group],
            [
                AttemptAnswer(item_id=case.item_id, answer_text=case.answer)
                for case in group
            ],
            llm=counting,
        )
        by_item = {question.item_id: question for question in result.questions}
        for case in group:
            question = by_item[case.item_id]
            judge_total = question.marks_awarded
            delta = (
                judge_total - case.total if judge_total is not None else None
            )
            criteria = {
                criterion.criterion_id: (
                    criterion.awarded,
                    case.marks[criterion.criterion_id],
                )
                for criterion in question.criteria
            }
            details.append(
                CalibrationDetail(
                    item_id=case.item_id,
                    variant=case.variant,
                    human=case.total,
                    judge=judge_total,
                    delta=delta,
                    needs_review=question.needs_review,
                    criteria=criteria,
                    word_count=len(case.answer.split()),
                )
            )

    n = len(details)
    exact = sum(1 for detail in details if detail.judge == detail.human) / n
    adjacent = (
        sum(
            1
            for detail in details
            if detail.judge is not None and abs(detail.judge - detail.human) <= 1
        )
        / n
    )
    resolved = [detail for detail in details if detail.judge is not None]
    mae = (
        sum(abs(detail.judge - detail.human) for detail in resolved) / len(resolved)
        if resolved
        else None
    )
    criterion_ids = sorted(
        {
            criterion_id
            for detail in details
            for criterion_id in detail.criteria
        }
    )
    per_criterion = {
        criterion_id: sum(
            1
            for detail in details
            if detail.criteria.get(criterion_id, (None, None))[0]
            == detail.criteria.get(criterion_id, (None, None))[1]
            and detail.criteria.get(criterion_id, (None, None))[0] is not None
        )
        / n
        for criterion_id in criterion_ids
    }
    verbose = [detail for detail in resolved if detail.variant == "verbose"]
    verbose_delta = (
        sum(detail.delta for detail in verbose) / len(verbose) if verbose else None
    )
    correlation = _pearson(
        [
            (float(detail.word_count), float(detail.delta))
            for detail in resolved
            if detail.delta is not None
        ]
    )
    retries = max(0, counting.calls - passes_with_calls)
    return CalibrationReport(
        model=bank.manifest.judge_model,
        provider=settings.exam_judge_provider,
        temperature=bank.manifest.judge_temperature or 0.0,
        prompt_version=bank.manifest.judge_prompt_version,
        set_sha256=set_sha256,
        n=n,
        exact=exact,
        adjacent=adjacent,
        mae=mae,
        per_criterion=per_criterion,
        calls=counting.calls,
        passes=passes_with_calls,
        retries=retries,
        needs_review=sum(1 for detail in details if detail.needs_review),
        verbose_delta=verbose_delta,
        word_count_correlation=correlation,
        details=details,
    )


__all__ = [
    "CountingLlm",
    "VARIANTS",
    "file_sha256",
    "load_calibration",
    "run_calibration",
]
