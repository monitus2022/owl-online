"""Deterministic verification: no model call, no network."""

from app.pipeline.generate import ABSTAIN_MESSAGE, AskResult, verify_draft
from app.pipeline.generate.generate import AbstainReason
from app.pipeline.generate.verify import Verification
from app.schemas import Chunk, ChunkMetadata

_TWO_LEG = 2.0 / 61


def _chunk() -> Chunk:
    return Chunk(
        id="b1-c01-0000",
        text="Rowan trims the wick.",
        metadata=ChunkMetadata(
            book_num=1, chapter_num=1, book_name="Book 1", chapter_name="Chapter 1"
        ),
        score=_TWO_LEG,
    )


def _result(
    answer: str = "Rowan trims the wick [b1-c01-0000].",
    citations: list[str] | None = None,
    abstained: bool = False,
    chunks: list[Chunk] | None = None,
    abstain_reason: AbstainReason | None = None,
) -> AskResult:
    return AskResult(
        answer=answer,
        citations=["b1-c01-0000"] if citations is None else citations,
        abstained=abstained,
        chunks=[_chunk()] if chunks is None else chunks,
        abstain_reason=abstain_reason,
    )


def test_grounded_draft_passes():
    verdict = verify_draft("Rowan trims the wick [b1-c01-0000].", _result())
    assert verdict == Verification(True)


def test_empty_draft_fails():
    assert verify_draft("   ", _result()) == Verification(False, "empty")


def test_uncited_draft_fails():
    result = _result(
        answer=ABSTAIN_MESSAGE,
        citations=[],
        abstained=True,
        abstain_reason="uncited",
    )
    assert verify_draft("Rowan trims the wick.", result) == Verification(False, "uncited")


def test_empty_retrieval_is_not_a_failure():
    result = _result(
        answer=ABSTAIN_MESSAGE,
        citations=[],
        abstained=True,
        chunks=[],
        abstain_reason="no_evidence",
    )
    assert verify_draft(ABSTAIN_MESSAGE, result) == Verification(True)


def test_weak_retrieval_with_hits_is_not_a_failure():
    # The retriever can return hits that score below the floor; ask() abstains
    # without drafting, so verification must not mistake that for an uncited
    # answer just because chunks is non-empty.
    result = _result(
        answer=ABSTAIN_MESSAGE,
        citations=[],
        abstained=True,
        abstain_reason="no_evidence",
    )
    assert result.chunks
    assert verify_draft(ABSTAIN_MESSAGE, result) == Verification(True)
