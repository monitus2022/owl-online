"""Grounded ask(): retrieve evidence, generate a cited answer, or abstain.

The model is never trusted for facts: it may only restate the retrieved
excerpts, and every citation must be a retrieved chunk id. No evidence, a weak
top hit, or an uncited answer means abstain rather than guess.
"""

import logging
import re
import time
from dataclasses import dataclass, field

from app.pipeline.retrieve.retriever import DEFAULT_RRF_K, QUERY_CANDIDATES
from app.providers.contracts import Llm, Retriever
from app.schemas import Chunk

logger = logging.getLogger(__name__)

ABSTAIN_MESSAGE = "I cannot answer that from the books."
DEFAULT_TOP_K = 5
# A chunk reached by one leg scores at most 1/(rrf_k+1); reached by both legs, at
# least 2/(rrf_k+candidates). The floor sits in that gap, so abstention means "no
# chunk was found by both the dense and the lexical leg" — a question the corpus
# does not lexically cover. Tunable in #51 against the measured distribution.
DEFAULT_MIN_SCORE = 2.0 / (DEFAULT_RRF_K + QUERY_CANDIDATES)

_SYSTEM = (
    "You are O.W.L. Online, a revision assistant grounded only in the excerpts "
    "provided by the user. Use only those excerpts. Cite the id of every excerpt "
    "you use in square brackets, exactly as given, for example [b1-c03-0000]. "
    "If the excerpts do not contain the answer, reply exactly: "
    f"{ABSTAIN_MESSAGE}"
)

_CITATION = re.compile(r"\[([^\]]+)\]")
_ID_SEPARATOR = re.compile(r"[,\s]+")


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
    min_score: float | None = None,
) -> AskResult:
    """Answer from the corpus, citing chunk ids, or abstain on weak retrieval."""
    # Prefer the retriever's own floor so it tracks the rrf_k/candidates it was
    # built with; fall back to the module default for simple/fake retrievers.
    floor = (
        min_score
        if min_score is not None
        else getattr(retriever, "min_score", DEFAULT_MIN_SCORE)
    )
    retrieve_start = time.perf_counter()
    chunks = await retriever.retrieve(question, top_k)
    retrieve_ms = (time.perf_counter() - retrieve_start) * 1000
    if not chunks or chunks[0].score < floor:
        logger.info(
            "abstain (no evidence): hits=%d top=%s floor=%.4f retrieve=%.0fms",
            len(chunks),
            f"{chunks[0].score:.4f}" if chunks else "none",
            floor,
            retrieve_ms,
        )
        return AskResult(ABSTAIN_MESSAGE, abstained=True)

    generate_start = time.perf_counter()
    answer = await llm.generate(_SYSTEM, _prompt(question, chunks))
    generate_ms = (time.perf_counter() - generate_start) * 1000

    allowed = {c.id for c in chunks}
    citations = [cid for cid in _cited_ids(answer) if cid in allowed]
    if not citations:
        # No excerpt cited: the answer is ungrounded, so do not return it.
        logger.info("abstain (uncited): hits=%d generate=%.0fms", len(chunks), generate_ms)
        return AskResult(ABSTAIN_MESSAGE, abstained=True)

    logger.info(
        "answered: model=%s hits=%d citations=%d top=%.4f retrieve=%.0fms generate=%.0fms",
        getattr(llm, "name", "?"),
        len(chunks),
        len(citations),
        chunks[0].score,
        retrieve_ms,
        generate_ms,
    )
    return AskResult(_drop_unknown_citations(answer, allowed), citations)


def _prompt(question: str, chunks: list[Chunk]) -> str:
    evidence = "\n\n".join(
        f"[{c.id}] (Book {c.metadata.book_num}, {c.metadata.chapter_name}):\n{c.text}"
        for c in chunks
    )
    return f"Excerpts:\n\n{evidence}\n\nQuestion: {question}\n\nAnswer:"


def _cited_ids(answer: str) -> list[str]:
    """Every id the answer cites, in order, unique; handles [a, b] groups."""
    seen: list[str] = []
    for raw in _CITATION.findall(answer):
        for cid in _ID_SEPARATOR.split(raw.strip()):
            if cid and cid not in seen:
                seen.append(cid)
    return seen


def _drop_unknown_citations(answer: str, allowed: set[str]) -> str:
    """Remove citations the model invented; keep only retrieved ids in the text."""

    def keep(raw: str) -> str:
        known = [cid for cid in _ID_SEPARATOR.split(raw.strip()) if cid in allowed]
        return f"[{', '.join(known)}]" if known else ""

    return _CITATION.sub(lambda match: keep(match.group(1)), answer).strip()
