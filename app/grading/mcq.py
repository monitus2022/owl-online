"""Deterministic MCQ scoring (#192).

MCQ marks never go through a model. The answer is an option id, the key is the
stored option id, and the marks are the item's stored marks.
"""

from __future__ import annotations

from app.exam.bank import BankItem
from app.grading.models import QuestionGrade


def score_mcq(item: BankItem, option_id: str | None) -> QuestionGrade:
    """Score one MCQ by option id; `None` means the question was left blank."""
    if item.kind != "mcq":
        raise ValueError(f"{item.item_id} is not an MCQ")
    if item.correct_option_id is None:
        raise ValueError(f"{item.item_id} has no correct option id")
    options = {option.option_id: option.text for option in item.options}
    if item.correct_option_id not in options:
        raise ValueError(f"{item.item_id} key is not one of its options")
    if option_id is not None and option_id not in options:
        raise ValueError(f"{item.item_id}: unknown option id {option_id!r}")

    correct = option_id is not None and option_id == item.correct_option_id
    if correct:
        feedback = "Correct."
    elif option_id is None:
        feedback = "No option selected."
    else:
        feedback = "Incorrect."
    return QuestionGrade(
        item_id=item.item_id,
        kind="mcq",
        marks_awarded=item.marks if correct else 0,
        max_marks=item.marks,
        correct=correct,
        correct_option_id=item.correct_option_id,
        model_answer=options[item.correct_option_id],
        criteria=(),
        feedback=feedback,
        material_id=item.material_id,
        evidence_ids=(item.evidence_snapshot.chunk_id,),
        canon_tier=item.canon_tier,
        rubric_version=item.prompt_version,
    )


__all__ = ["score_mcq"]
