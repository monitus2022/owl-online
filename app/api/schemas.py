"""HTTP request and response models for the API."""

from pydantic import BaseModel, Field, field_validator


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


class AskResponse(BaseModel):
    """A grounded answer with the chunk ids it cites."""

    answer: str
    citations: list[str]
    abstained: bool
