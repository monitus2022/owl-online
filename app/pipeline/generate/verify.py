"""Deterministic verification of one generated draft.

No model call: the rules are cheap, explainable and reproducible, so the runtime
and the eval harness can gate a retry on the same check. A draft fails when it is
empty or when it cites nothing that grounds it. Retrieval abstention is not a
failure: with no evidence a second draft cannot become grounded.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.pipeline.generate.generate import AskResult

VerifyReason = Literal["empty", "uncited"]


@dataclass(frozen=True)
class Verification:
    """Whether a draft may be returned, and why not when it may not be."""

    ok: bool
    reason: VerifyReason | None = None


def verify_draft(draft: str, result: AskResult) -> Verification:
    """Judge one draft against two deterministic rules.

    `result` is the grounded form of the same draft, so a missing citation means
    the answer is ungrounded even when the draft text is long. A weak retrieval
    (`abstain_reason="no_evidence"`) is not a draft failure: there is nothing to
    re-cite.
    """
    if result.abstain_reason == "no_evidence" or (
        result.abstain_reason is None and not result.chunks
    ):
        return Verification(True)
    if not draft.strip():
        return Verification(False, "empty")
    if result.abstained or not result.citations:
        return Verification(False, "uncited")
    return Verification(True)
