"""HTTP request and response models for the API."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.knowledge.packs import PackSummary


class AskRequest(BaseModel):
    """A single revision question."""

    question: str = Field(min_length=1, max_length=1000)

    @field_validator("question")
    @classmethod
    def _strip_and_require_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be blank")
        return stripped


class StreamRequest(AskRequest):
    """A question plus an optional chat-intent override and answer to review."""

    mode: Literal["auto", "answer", "practice", "feedback", "lesson"] = "auto"
    student_answer: str | None = Field(default=None, max_length=6000)

    @field_validator("student_answer")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def _check_student_answer_mode(self) -> "StreamRequest":
        if self.student_answer and self.mode in ("answer", "practice", "lesson"):
            raise ValueError("student_answer is only valid with auto or feedback mode")
        return self


class AskResponse(BaseModel):
    """A grounded answer with the book chunk ids and lore ids it cites."""

    answer: str
    citations: list[str]
    abstained: bool
    lore_citations: list[str] = Field(default_factory=list)
    material_citations: list[str] = Field(default_factory=list)


class SubjectsResponse(BaseModel):
    """The published subject packs the API can serve."""

    subjects: list[PackSummary]
