"""Material records: grounded text plus the source refs and references that
justify it.

A `Material` is the unit the exam builder and lesson mode read. It carries its
own canonical text and must be traceable: `source_refs` point into the book
corpus (chunk id, book, chapter, quote, per-chunk text hash, index hash), and
`references` are optional secondary links (a Lexicon entry, with title, URL,
publisher and access date) for discovery and attribution, never the truth of
the pack.

Source policy inherited from `docs/workplan.md` and `docs/lexicon-canon-index.md`:
- primary tier implies books scope; a film or game citation is excluded;
- no Lexicon prose: a reference is a link plus access date, not copied text;
- a material with no source ref is invalid at the pack level (not here), so
  record-level checks stay structural and pack validation does the corpus join.

`chunk_text_hash` matches the index builder's convention (sha256, first 16
hex chars) so a SourceRef hash is comparable to the corpus the index was built
from.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.knowledge.taxonomy import (
    CANON_SCOPE_SET,
    CANON_TIER_SET,
    KIND_SET,
    NOVEL_BOOKS,
    REVIEW_SET,
)

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_URL_RE = re.compile(r"^https?://")


def chunk_text_hash(text: str) -> str:
    """The first 16 hex chars of the text's sha256; the same shape as the
    index builder's per-corpus hash, computed per chunk."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class _StrictModel(BaseModel):
    """Unknown fields raise instead of being silently dropped.

    The source policy is load-bearing: a build step that smuggles prose (a
    `text` key on a ReferenceLink, for instance) must fail loudly, not have
    the extra quietly ignored.
    """

    model_config = ConfigDict(extra="forbid")


class SourceRef(_StrictModel):
    """One grounding pointer into the book corpus."""

    chunk_id: str
    book: int
    chapter: int
    quote: str
    text_hash: str
    index_text_hash: str
    citation_bucket: str = "books"

    @field_validator("chunk_id")
    @classmethod
    def _chunk_id_shape(cls, value: str) -> str:
        if not re.match(r"^b[1-7]-c\d{2}-\d{4}$", value):
            raise ValueError(f"chunk_id must look like bN-cNN-NNNN, got {value!r}")
        return value

    @field_validator("citation_bucket")
    @classmethod
    def _books_only(cls, value: str) -> str:
        if value != "books":
            raise ValueError("source refs must cite the books bucket")
        return value

    @field_validator("book")
    @classmethod
    def _book_is_a_novel(cls, value: int) -> int:
        if value not in NOVEL_BOOKS:
            raise ValueError("source refs point at the seven novels only")
        return value

    @field_validator("quote", "text_hash", "index_text_hash")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("source ref fields must not be blank")
        return value.strip()

    @property
    def in_epilogue_chapter(self) -> bool:
        """True when the chunk is in book 7 chapter 36 - the chapter whose
        tail carries the epilogue. The epilogue starts inside `b7-c36-0103`,
        so this is a chapter hint, not an epilogue proof; #127 slices on the
        marker (docs/lexicon-canon-index.md)."""
        return self.chunk_id.startswith("b7-c36-")


class ReferenceLink(_StrictModel):
    """An optional secondary source: a Lexicon entry or similar, attributed."""

    title: str
    url: str
    publisher: str
    accessed: date

    @field_validator("title", "publisher")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reference title and publisher must not be blank")
        return value.strip()

    @field_validator("url")
    @classmethod
    def _absolute_http_url(cls, value: str) -> str:
        if not _URL_RE.match(value):
            raise ValueError("reference url must be absolute http(s)")
        return value


class Material(_StrictModel):
    """One grounded piece of subject content shown to the generator."""

    material_id: str
    subject: str
    topic: str
    concept: str
    kind: str
    text: str
    canon_tier: str = "primary"
    canon_scope: str = "books"
    review_status: str = "draft"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_refs: list[SourceRef] = Field(default_factory=list)
    references: list[ReferenceLink] = Field(default_factory=list)

    @field_validator("material_id", "topic", "concept")
    @classmethod
    def _id_shape(cls, value: str) -> str:
        if not _ID_RE.match(value):
            raise ValueError(f"identifier must be lowercase [a-z0-9._-], got {value!r}")
        return value

    @field_validator("text")
    @classmethod
    def _text_present(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("material text must not be blank")
        return value

    @field_validator("kind")
    @classmethod
    def _kind_known(cls, value: str) -> str:
        if value not in KIND_SET:
            raise ValueError(f"kind must be one of {sorted(KIND_SET)}")
        return value

    @field_validator("canon_tier")
    @classmethod
    def _tier_known(cls, value: str) -> str:
        if value not in CANON_TIER_SET:
            raise ValueError(f"canon_tier must be one of {sorted(CANON_TIER_SET)}")
        return value

    @field_validator("canon_scope")
    @classmethod
    def _scope_known(cls, value: str) -> str:
        if value not in CANON_SCOPE_SET:
            raise ValueError(f"canon_scope must be one of {sorted(CANON_SCOPE_SET)}")
        return value

    @field_validator("review_status")
    @classmethod
    def _status_known(cls, value: str) -> str:
        if value not in REVIEW_SET:
            raise ValueError(f"review_status must be one of {sorted(REVIEW_SET)}")
        return value

    @model_validator(mode="after")
    def _primary_is_books(self) -> Material:
        # The policy is one-directional: a secondary fact may be scoped to
        # films; a primary fact may never be.
        if self.canon_tier == "primary" and self.canon_scope != "books":
            raise ValueError("primary material must be books-scoped")
        return self
