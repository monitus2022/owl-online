"""Grounded ask(): retrieve evidence, generate a cited answer, or abstain.

The model is never trusted for facts: it may only restate the retrieved
excerpts, and every citation must be a retrieved chunk id. No evidence, a weak
top hit, or an uncited answer means abstain rather than guess.
"""

import re
from dataclasses import dataclass, field

from app.providers.contracts import Llm, Retriever
from app.schemas import Chunk

ABSTAIN_MESSAGE = "I cannot answer that from the books."
DEFAULT_TOP_K = 5
# Set floor for RRF retrieval score
# Current preset from esimate of lab
# TODO: Update based on the retrieval score distribution of the corpus.
DEFAULT_MIN_SCORE = 0.015

_SYSTEM = (
    "You are O.W.L. Online, a revision assistant grounded only in the excerpts "
    "provided by the user. Use only those excerpts. Cite the id of every excerpt "
    "you use in square brackets, exactly as given, for example [b1-c03-0000]. "
    "If the excerpts do not contain the answer, reply exactly: "
    f"{ABSTAIN_MESSAGE}"
)

_CITATION = re.compile(r"\[([^\]]+)\]")


@dataclass(frozen=True)
class AskResult:
    """A grounded answer plus the chunk ids it rests on."""

    answer: str
    citations: list[str] = field(default_factory=list)
    abstained: bool = False


async def ask(
    question: str,
    *,
    retriever: Retriever,
    llm: Llm,
    top_k: int = DEFAULT_TOP_K,
    min_score: float = DEFAULT_MIN_SCORE,
) -> AskResult:
    """Answer from the corpus, citing chunk ids, or abstain on weak retrieval."""
    chunks = await retriever.retrieve(question, top_k)
    if not chunks or chunks[0].score < min_score:
        return AskResult(ABSTAIN_MESSAGE, abstained=True)
    answer = await llm.generate(_SYSTEM, _prompt(question, chunks))
    citations = _citations(answer, chunks)
    if not citations:
        # No excerpt cited: the answer is ungrounded, so do not return it.
        return AskResult(ABSTAIN_MESSAGE, abstained=True)
    return AskResult(answer.strip(), citations)


def _prompt(question: str, chunks: list[Chunk]) -> str:
    evidence = "\n\n".join(
        f"[{c.id}] (Book {c.metadata.book_num}, {c.metadata.chapter_name}):\n{c.text}"
        for c in chunks
    )
    return f"Excerpts:\n\n{evidence}\n\nQuestion: {question}\n\nAnswer:"


def _citations(answer: str, chunks: list[Chunk]) -> list[str]:
    """Cited ids that actually appear in the retrieved set, in order, unique."""
    allowed = {c.id for c in chunks}
    seen: list[str] = []
    for raw in _CITATION.findall(answer):
        cid = raw.strip()
        if cid in allowed and cid not in seen:
            seen.append(cid)
    return seen