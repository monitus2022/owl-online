"""HTTP request and response models for the API."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.grading import Band, QuestionGrade
from app.knowledge.packs import PackSummary


class AskRequest(BaseModel):
    """A single revision question."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"question": "What is a Boggart?", "subject": "dada"}
            ]
        }
    )

    question: str = Field(min_length=1, max_length=1000)
    # The department the question is asked in. Empty means the exam/persona
    # default subject. The server uses it to scope the live persona card.
    subject: str = Field(default="", max_length=64)

    @field_validator("question")
    @classmethod
    def _strip_and_require_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be blank")
        return stripped


class StreamRequest(AskRequest):
    """A question plus an optional chat-intent override and answer to review."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "question": "What is a Boggart?",
                    "subject": "dada",
                    "mode": "lesson",
                }
            ]
        }
    )

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

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "answer": "A Boggart takes the shape of what the watcher fears most.",
                    "citations": ["b1-c01-0000"],
                    "abstained": False,
                    "lore_citations": [],
                    "material_citations": [],
                    "typed_citations": [
                        "lesson:b1-c01-0000#b1-c01-0000"
                    ],
                    "citation_errors": [],
                }
            ]
        }
    )

    answer: str
    citations: list[str]
    abstained: bool
    lore_citations: list[str] = Field(default_factory=list)
    material_citations: list[str] = Field(default_factory=list)
    typed_citations: list[str] = Field(default_factory=list)
    citation_errors: list[str] = Field(default_factory=list)


class SubjectsResponse(BaseModel):
    """The published subject packs the API can serve, plus the live flags."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "subjects": [],
                    "lesson": True,
                    "lesson_subject": "dada",
                    "lesson_subjects": ["dada"],
                    "lesson_fallback": True,
                    "persona": True,
                    "persona_subject": "dada",
                    "persona_subjects": ["dada"],
                }
            ]
        }
    )

    subjects: list[PackSummary]
    lesson: bool = False
    lesson_subject: str = ""
    lesson_subjects: list[str] = Field(default_factory=list)
    lesson_fallback: bool = True
    persona: bool = False
    persona_subject: str = ""
    persona_subjects: list[str] = Field(default_factory=list)


class ExamPaper(BaseModel):
    """One served paper descriptor; the questions are sampled per attempt."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "paper_id": "dada-1.0.0",
                    "subject": "dada",
                    "version": "1.0.0",
                    "title": "Defense Against the Dark Arts",
                    "question_count": 10,
                    "mcq_count": 6,
                    "short_answer_count": 4,
                    "marks": 50,
                    "duration_minutes": 120,
                }
            ]
        }
    )

    paper_id: str
    subject: str
    version: str
    title: str
    question_count: int
    mcq_count: int
    short_answer_count: int
    marks: int
    duration_minutes: int


class ExamAnswer(BaseModel):
    """One submitted answer: an option id for MCQ or text for a short answer."""

    item_id: str
    option_id: str | None = Field(default=None, max_length=64)
    answer_text: str | None = Field(default=None, max_length=6000)

    @field_validator("item_id")
    @classmethod
    def _item_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("item_id must not be blank")
        return stripped

    @field_validator("option_id", "answer_text")
    @classmethod
    def _optional_text(cls, value: str | None) -> str | None:
        return None if value is None else value.strip()

    @model_validator(mode="after")
    def _one_shape(self) -> "ExamAnswer":
        if self.option_id is not None and self.answer_text is not None:
            raise ValueError("an answer is either an option id or answer text, not both")
        return self


class GradeAttemptRequest(BaseModel):
    """The answers for one attempt; omitted questions are left blank."""

    answers: list[ExamAnswer] = Field(default_factory=list, max_length=50)


class ExamGradeResponse(BaseModel):
    """The graded attempt: per-question results and the deterministic band."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "attempt_id": "V1StGXR8_Z5jdHi6B-myT",
                    "paper_id": "dada-1.0.0",
                    "total": 45,
                    "max_marks": 50,
                    "band": "O",
                    "needs_review": False,
                    "graded_at": "2026-11-11T00:00:00Z",
                    "questions": [],
                }
            ]
        }
    )

    attempt_id: str
    paper_id: str
    total: int | None
    max_marks: int
    band: Band | None
    needs_review: bool
    graded_at: str
    questions: list[QuestionGrade]
