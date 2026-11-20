"""Operator-only evidence for local reviews (#295).

The report carries the retrieved chunk text, scores, prompt fingerprint and
the verification state. That text is copyrighted, so the report exists only
when OWL_DEV_EVIDENCE is on. The deployment leaves it off, the response field
is documented as operator-only, and the student UI never requests it.
"""

from __future__ import annotations

from app.api.schemas import EvidenceChunk, EvidenceReport
from app.pipeline.generate import AskResult


def evidence_payload(result: AskResult, *, enabled: bool) -> EvidenceReport | None:
    """The report for one result, or None when the operator flag is off."""
    if not enabled:
        return None
    return EvidenceReport(
        chunks=[
            EvidenceChunk(
                id=chunk.id,
                book=chunk.metadata.book_num,
                chapter=chunk.metadata.chapter_num,
                score=chunk.score,
                text=chunk.text,
            )
            for chunk in result.chunks
        ],
        prompt_sha256=result.prompt_sha256,
        prompt_chars=result.prompt_length,
        attempts=result.attempts,
        model_calls=result.model_calls,
        abstained=result.abstained,
        abstain_reason=result.abstain_reason,
        retry_reason=result.retry_reason,
        scope=result.scope,
        selected_material_ids=list(result.selected_material_ids),
        selection_scores=dict(result.selection_scores),
        uncovered_terms=list(result.uncovered_terms),
        multi_book=result.multi_book,
    )
