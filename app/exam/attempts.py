"""Paper sampling and the pre-submission attempt view (#193).

A paper is sampled once, persisted, and served from the persisted view. The
correct option id is stored server-side on the attempt question and is never
part of the view the client receives before grading.
"""

from __future__ import annotations

import random
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.exam.bank import ExamBank
from app.grading import Band
from app.grading.models import AttemptGrade


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _non_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must not be blank")
    return value.strip()


class ServedOption(_StrictModel):
    """One of the four options sampled for a served MCQ."""

    option_id: str
    text: str

    @model_validator(mode="after")
    def _shape(self) -> ServedOption:
        _non_blank(self.option_id)
        _non_blank(self.text)
        return self


class AttemptQuestion(_StrictModel):
    """One persisted question in an attempt."""

    position: int = Field(ge=0)
    item_id: str
    kind: Literal["mcq", "short_answer"]
    prompt: str
    marks: int = Field(gt=0)
    options: tuple[ServedOption, ...] = ()
    correct_option_id: str | None = None

    @model_validator(mode="after")
    def _kind_rules(self) -> AttemptQuestion:
        _non_blank(self.item_id)
        _non_blank(self.prompt)
        if self.kind == "mcq":
            if len(self.options) != 4:
                raise ValueError("a served MCQ needs exactly four options")
            option_ids = [option.option_id for option in self.options]
            if len(set(option_ids)) != len(option_ids):
                raise ValueError("served option ids must be unique")
            if self.correct_option_id not in option_ids:
                raise ValueError("the correct option must be one of the served options")
        else:
            if self.options or self.correct_option_id is not None:
                raise ValueError("short-answer questions do not serve options")
        return self

    def view(self) -> QuestionView:
        return QuestionView(
            position=self.position,
            item_id=self.item_id,
            kind=self.kind,
            prompt=self.prompt,
            marks=self.marks,
            options=self.options,
        )


class AttemptRecord(_StrictModel):
    """The server-side attempt: questions, the stored key and the later grade."""

    attempt_id: str
    paper_id: str
    subject: str
    bank_version: str
    created_at: str
    session_id: str = ""
    questions: tuple[AttemptQuestion, ...] = Field(min_length=1)
    graded_at: str | None = None
    grade: AttemptGrade | None = None

    @property
    def item_ids(self) -> tuple[str, ...]:
        return tuple(question.item_id for question in self.questions)

    def view(self) -> AttemptView:
        return AttemptView(
            attempt_id=self.attempt_id,
            paper_id=self.paper_id,
            subject=self.subject,
            version=self.bank_version,
            created_at=self.created_at,
            marks=sum(question.marks for question in self.questions),
            questions=tuple(question.view() for question in self.questions),
        )


class AttemptSummary(_StrictModel):
    """One graded attempt as the session history list may see it."""

    attempt_id: str
    paper_id: str
    subject: str
    version: str
    created_at: str
    graded_at: str
    total: int | None = None
    max_marks: int = Field(gt=0)
    band: Band | None = None
    needs_review: bool = False

    @model_validator(mode="after")
    def _totals(self) -> AttemptSummary:
        _non_blank(self.attempt_id)
        _non_blank(self.paper_id)
        _non_blank(self.subject)
        _non_blank(self.version)
        _non_blank(self.created_at)
        _non_blank(self.graded_at)
        if self.needs_review:
            if self.total is not None or self.band is not None:
                raise ValueError("an unresolved attempt cannot carry a total or band")
        elif self.total is None or self.band is None:
            raise ValueError("a resolved attempt needs a total and band")
        return self


class QuestionView(_StrictModel):
    """One question as the client may see it before submission."""

    position: int
    item_id: str
    kind: Literal["mcq", "short_answer"]
    prompt: str
    marks: int
    options: tuple[ServedOption, ...] = ()


class AttemptView(_StrictModel):
    """The pre-submission attempt payload; no key, golden answer or evidence."""

    attempt_id: str
    paper_id: str
    subject: str
    version: str
    created_at: str
    marks: int
    questions: tuple[QuestionView, ...]


def sample_attempt(
    bank: ExamBank,
    *,
    attempt_id: str,
    paper_id: str,
    created_at: str,
    session_id: str = "",
    mcq_count: int = 6,
    short_count: int = 4,
    rng: random.Random | None = None,
) -> AttemptRecord:
    """Sample the paper and persist the four-option MCQ view server-side."""
    rng = rng or random.Random()
    mcqs = [item for item in bank.items if item.kind == "mcq"]
    shorts = [item for item in bank.items if item.kind == "short_answer"]
    if len(mcqs) < mcq_count:
        raise ValueError(f"bank has {len(mcqs)} MCQs; needs {mcq_count}")
    if len(shorts) < short_count:
        raise ValueError(f"bank has {len(shorts)} short answers; needs {short_count}")

    questions: list[AttemptQuestion] = []
    for position, item in enumerate(rng.sample(mcqs, mcq_count)):
        if item.correct_option_id is None:
            raise ValueError(f"{item.item_id}: MCQ has no key")
        correct = next(
            option
            for option in item.options
            if option.option_id == item.correct_option_id
        )
        distractors = [
            option
            for option in item.options
            if option.option_id != item.correct_option_id
        ]
        sampled = [correct, *rng.sample(distractors, 3)]
        rng.shuffle(sampled)
        questions.append(
            AttemptQuestion(
                position=position,
                item_id=item.item_id,
                kind="mcq",
                prompt=item.prompt,
                marks=item.marks,
                options=tuple(
                    ServedOption(option_id=option.option_id, text=option.text)
                    for option in sampled
                ),
                correct_option_id=item.correct_option_id,
            )
        )
    for position, item in enumerate(
        rng.sample(shorts, short_count), start=mcq_count
    ):
        questions.append(
            AttemptQuestion(
                position=position,
                item_id=item.item_id,
                kind="short_answer",
                prompt=item.prompt,
                marks=item.marks,
            )
        )
    return AttemptRecord(
        attempt_id=attempt_id,
        paper_id=paper_id,
        subject=bank.manifest.subject,
        bank_version=bank.manifest.version,
        created_at=created_at,
        session_id=session_id,
        questions=tuple(questions),
    )


__all__ = [
    "AttemptQuestion",
    "AttemptRecord",
    "AttemptSummary",
    "AttemptView",
    "QuestionView",
    "ServedOption",
    "sample_attempt",
]
