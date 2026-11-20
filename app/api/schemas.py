"""HTTP request and response models for the API."""

import re
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
    # The display name collected at the welcome. It is data, not instructions:
    # the validator admits letters and a small set of name punctuation only.
    student_name: str | None = Field(default=None, max_length=40)

    @field_validator("question")
    @classmethod
    def _strip_and_require_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be blank")
        return stripped

    @field_validator("student_name")
    @classmethod
    def _clean_student_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("student_name must not contain control characters")
        collapsed = " ".join(value.split())
        if not collapsed:
            return None
        if len(collapsed) > 40:
            raise ValueError("student_name must be 40 characters or fewer")
        if not collapsed[0].isalpha():
            raise ValueError("student_name must start with a letter")
        if not all(char.isalpha() or char in " .'-" for char in collapsed):
            raise ValueError(
                "student_name may contain letters, spaces, apostrophes, "
                "hyphens and full stops"
            )
        return collapsed


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
    thread_id: str | None = Field(default=None, max_length=256)

    @field_validator("thread_id")
    @classmethod
    def _thread_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        if re.fullmatch(r"[A-Za-z0-9_-]{8,64}", stripped) is None:
            raise ValueError("thread_id must be 8-64 letters, digits, hyphens or underscores")
        return stripped

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


class EvidenceChunk(BaseModel):
    """One retrieved chunk in the operator-only evidence report."""

    id: str
    book: int
    chapter: int
    score: float
    text: str


class EvidenceReport(BaseModel):
    """Operator-only retrieval and verification details (#295).

    Present only when OWL_DEV_EVIDENCE is on. It can carry copyrighted corpus
    text, so it is never enabled in deployment and must not be shown to
    students.
    """

    chunks: list[EvidenceChunk] = Field(default_factory=list)
    prompt_sha256: str = Field(
        default="",
        description="First 16 hex chars of the prompt hash; matches the trace prompt_sha.",
    )
    prompt_chars: int = 0
    attempts: int = 0
    model_calls: int = 0
    abstained: bool = False
    abstain_reason: str | None = None
    retry_reason: str | None = None
    scope: str | None = None
    selected_material_ids: list[str] = Field(default_factory=list)
    selection_scores: dict[str, float] = Field(default_factory=dict)
    uncovered_terms: list[str] = Field(default_factory=list)
    multi_book: bool = False


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
    evidence: EvidenceReport | None = Field(
        default=None,
        description=(
            "Operator-only retrieval and verification details. Present only "
            "when OWL_DEV_EVIDENCE is on; never enabled in deployment."
        ),
    )


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


class MaterialSourceRef(BaseModel):
    """A book locator behind a reviewed material; the corpus quote stays home."""

    chunk_id: str
    book: int
    chapter: int


class MaterialDetail(BaseModel):
    """One reviewed material note, safe to render outside the chat prompt.

    The text is the project's authored pack prose. The source refs expose the
    book, chapter and chunk id; they deliberately omit the corpus quote and
    hashes, so this route never distributes novel text.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "material_id": "dada-dark-creatures-boggarts-counter",
                    "subject": "dada",
                    "topic": "dark-creatures",
                    "topic_title": "Dark creatures",
                    "concept": "boggarts",
                    "concept_title": "Boggarts",
                    "text": "The counter-charm is Riddikulus.",
                    "pack_version": "1.0.0",
                    "source_refs": [
                        {"chunk_id": "b3-c07-0041", "book": 3, "chapter": 7}
                    ],
                }
            ]
        }
    )

    material_id: str
    subject: str
    topic: str
    topic_title: str
    concept: str
    concept_title: str
    text: str
    pack_version: str
    source_refs: list[MaterialSourceRef] = Field(default_factory=list)


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
                    "duration_minutes": 60,
                    "timed": False,
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
    # Advisory only. The room is untimed practice: the server does not start a
    # clock, expire an attempt or reject a late grade.
    duration_minutes: int
    timed: bool = False


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
