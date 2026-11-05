"""Grounded ask(): retrieve evidence, generate a cited answer, or abstain.

The model is never trusted for facts: it may only restate the retrieved
excerpts, and every citation must be a retrieved chunk id. No evidence, a weak
top hit, or an uncited answer means abstain rather than guess.
"""

import logging
import re
import time
from collections.abc import Callable
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

SYSTEM_PROMPT = (
    "You are O.W.L. Online, a revision assistant grounded only in the excerpts "
    "provided by the user. Use only those excerpts. Cite the id of every excerpt "
    "you use in square brackets, exactly as given, for example [b1-c03-0000]. "
    "If the excerpts do not contain the answer, reply exactly: "
    f"{ABSTAIN_MESSAGE}"
)

_CITATION = re.compile(r"\[([^\]]+)\]")
_ID_SEPARATOR = re.compile(r"[,\s]+")

TokenSink = Callable[[str], None]


@dataclass(frozen=True)
class AskResult:
    """A grounded answer plus the chunk ids it rests on."""

    answer: str
    citations: list[str] = field(default_factory=list)
    abstained: bool = False


def retrieval_floor(
    retriever: Retriever, min_score: float | None = None
) -> float:
    """Prefer the retriever's own floor so it tracks its rrf_k and candidates."""
    if min_score is not None:
        return min_score
    return getattr(retriever, "min_score", DEFAULT_MIN_SCORE)


def render_evidence(chunks: list[Chunk]) -> str:
    """The excerpt block shared by answer, generate and grade prompts."""
    return "\n\n".join(
        f"[{c.id}] (Book {c.metadata.book_num}, {c.metadata.chapter_name}):\n{c.text}"
        for c in chunks
    )


def build_prompt(question: str, chunks: list[Chunk]) -> str:
    return f"Excerpts:\n\n{render_evidence(chunks)}\n\nQuestion: {question}\n\nAnswer:"


def ground_answer(answer: str, chunks: list[Chunk]) -> AskResult:
    """Accept only citations that name a retrieved chunk; otherwise abstain."""
    allowed = {c.id for c in chunks}
    citations = [cid for cid in _cited_ids(answer) if cid in allowed]
    if not citations:
        return AskResult(ABSTAIN_MESSAGE, abstained=True)
    return AskResult(_drop_unknown_citations(answer, allowed), citations)


async def ask(
    question: str,
    *,
    retriever: Retriever,
    llm: Llm,
    top_k: int = DEFAULT_TOP_K,
    min_score: float | None = None,
    on_token: TokenSink | None = None,
) -> AskResult:
    """Answer from the corpus, citing chunk ids, or abstain on weak retrieval.

    When on_token is supplied, generation uses llm.stream and forwards each
    token. The grounding check still runs on the complete answer, so a streamed
    draft can still end in abstention.
    """
    floor = retrieval_floor(retriever, min_score)
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

    prompt = build_prompt(question, chunks)
    generate_start = time.perf_counter()
    if on_token is None:
        answer = await llm.generate(SYSTEM_PROMPT, prompt)
    else:
        pieces: list[str] = []
        async for token in llm.stream(SYSTEM_PROMPT, prompt):
            pieces.append(token)
            on_token(token)
        answer = "".join(pieces)
    generate_ms = (time.perf_counter() - generate_start) * 1000

    result = ground_answer(answer, chunks)
    if result.abstained:
        logger.info("abstain (uncited): hits=%d generate=%.0fms", len(chunks), generate_ms)
        return result

    logger.info(
        "answered: model=%s hits=%d citations=%d top=%.4f retrieve=%.0fms generate=%.0fms",
        getattr(llm, "name", "?"),
        len(chunks),
        len(result.citations),
        chunks[0].score,
        retrieve_ms,
        generate_ms,
    )
    return result


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
