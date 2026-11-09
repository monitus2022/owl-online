"""Records for exam grading (#192).

The models are the contract between the grader, the serving layer (#193) and
the frontend. They carry the criterion marks, the judge configuration and the
bank pins with every result so a regrade is reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.grading.bands import Band, band_for


class _StrictModel(BaseModel):
    """Unknown fields raise; a grading result that grows an unrecorded field fails."""

    model_config = ConfigDict(extra="forbid")


def _non_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must not be blank")
    return value.strip()


@dataclass(frozen=True)
class JudgeConfig:
    """The pinned judge configuration used for a grading run."""

    model: str
    temperature: float
    prompt_version: str
    provider: str = "openrouter"
    max_tokens: int = 2000


class AttemptAnswer(_StrictModel):
    """One student answer: an option id for MCQ or text for a short answer."""

    item_id: str
    option_id: str | None = None
    answer_text: str | None = None

    @field_validator("item_id")
    @classmethod
    def _item_id(cls, value: str) -> str:
        return _non_blank(value)

    @field_validator("option_id")
    @classmethod
    def _option_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("answer_text")
    @classmethod
    def _answer_text(cls, value: str | None) -> str | None:
        return None if value is None else value.strip()

    @model_validator(mode="after")
    def _one_shape(self) -> AttemptAnswer:
        if self.option_id is not None and self.answer_text is not None:
            raise ValueError("an answer is either an option id or answer text, not both")
        return self


class CriterionGrade(_StrictModel):
    """One rubric criterion's awarded marks and reason."""

    criterion_id: str
    awarded: int = Field(ge=0)
    max_marks: int = Field(gt=0)
    reason: str

    @field_validator("criterion_id", "reason")
    @classmethod
    def _text(cls, value: str) -> str:
        return _non_blank(value)

    @model_validator(mode="after")
    def _range(self) -> CriterionGrade:
        if self.awarded > self.max_marks:
            raise ValueError("awarded marks exceed the criterion maximum")
        return self


class QuestionGrade(_StrictModel):
    """One graded question: MCQ key or judged short answer."""

    item_id: str
    kind: Literal["mcq", "short_answer"]
    marks_awarded: int | None = Field(default=None, ge=0)
    max_marks: int = Field(gt=0)
    correct: bool | None = None
    correct_option_id: str | None = None
    model_answer: str | None = None
    criteria: tuple[CriterionGrade, ...] = ()
    feedback: str
    material_id: str
    evidence_ids: tuple[str, ...] = ()
    canon_tier: str = "primary"
    rubric_version: str
    needs_review: bool = False
    judge_response_sha256: str | None = None

    @field_validator("item_id", "feedback", "material_id", "rubric_version")
    @classmethod
    def _text(cls, value: str) -> str:
        return _non_blank(value)

    @model_validator(mode="after")
    def _shape(self) -> QuestionGrade:
        if self.marks_awarded is not None and self.marks_awarded > self.max_marks:
            raise ValueError("awarded marks exceed the question maximum")
        if self.needs_review and self.marks_awarded is not None:
            raise ValueError("a question marked needs_review cannot carry marks")
        if not self.needs_review and self.marks_awarded is None:
            raise ValueError("a graded question must carry marks")
        if not self.evidence_ids:
            raise ValueError("a graded question must cite at least one evidence id")
        if self.canon_tier != "primary":
            raise ValueError("exam grades are primary canon only")
        if self.kind == "mcq":
            if self.criteria:
                raise ValueError("MCQ grades do not carry rubric criteria")
            if self.correct is None or self.correct_option_id is None:
                raise ValueError("MCQ grades need correct and correct_option_id")
        else:
            if self.correct is not None or self.correct_option_id is not None:
                raise ValueError("short-answer grades do not carry a correct flag")
            if not self.needs_review:
                if not self.criteria:
                    raise ValueError("short-answer grades need rubric criteria")
                if sum(criterion.max_marks for criterion in self.criteria) != self.max_marks:
                    raise ValueError("criterion maxima must sum to the question maximum")
                if sum(criterion.awarded for criterion in self.criteria) != self.marks_awarded:
                    raise ValueError("criterion marks must sum to the question total")
        return self


class AttemptGrade(_StrictModel):
    """One graded attempt: question results, deterministic total and band."""

    bank_version: str
    subject: str
    judge_model: str
    judge_temperature: float
    judge_prompt_version: str
    graded_at: str
    questions: tuple[QuestionGrade, ...] = Field(min_length=1)
    total: int | None = Field(default=None, ge=0)
    max_marks: int = Field(gt=0)
    band: Band | None = None
    needs_review: bool = False
    judge_output_sha256: str | None = None

    @field_validator("bank_version", "subject", "judge_model", "judge_prompt_version", "graded_at")
    @classmethod
    def _text(cls, value: str) -> str:
        return _non_blank(value)

    @model_validator(mode="after")
    def _totals(self) -> AttemptGrade:
        if sum(question.max_marks for question in self.questions) != self.max_marks:
            raise ValueError("question maxima must sum to the attempt maximum")
        marks = [question.marks_awarded for question in self.questions]
        unresolved = any(mark is None for mark in marks)
        if unresolved:
            if self.total is not None or self.band is not None:
                raise ValueError("an unresolved attempt cannot carry a total or band")
        else:
            expected = sum(mark for mark in marks if mark is not None)
            if self.total != expected:
                raise ValueError("total must be the sum of the question marks")
            if self.band != band_for(expected, self.max_marks):
                raise ValueError("band must match the deterministic band")
        if self.needs_review != any(question.needs_review for question in self.questions):
            raise ValueError("needs_review must match the question flags")
        if self.needs_review != unresolved:
            raise ValueError("an attempt with an unresolved question must be needs_review")
        return self


__all__ = [
    "AttemptAnswer",
    "AttemptGrade",
    "CriterionGrade",
    "JudgeConfig",
    "QuestionGrade",
]
