# Pydantic classes for schema

from pydantic import BaseModel, Field


class ChunkMetadata(BaseModel):
    """Metadata for a chunk of Harry Potter raw text
    book_num is restricted to 1-7."""

    book_num: int = Field(ge=1, le=7)
    chapter_num: int
    book_name: str
    chapter_name: str


class Chunk(BaseModel, extra="allow"):
    """A chunk of Harry Potter raw text with metadata."""

    id: str
    text: str
    metadata: ChunkMetadata
    score: float = 0.0
