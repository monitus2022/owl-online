"""HTTP request and response models for the API."""

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    """A single revision question."""

    question: str = Field(min_length=1, max_length=1000)


class AskResponse(BaseModel):
    """A grounded answer with the chunk ids it cites."""

    answer: str
    citations: list[str]
    abstained: bool
