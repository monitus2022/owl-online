"""Grounded ask(): retrieve evidence, generate a cited answer, or abstain.

The model is never trusted for facts: it may only restate the retrieved
excerpts, and every citation must be a retrieved chunk id. No evidence, a weak
top hit, or an uncited answer means abstain rather than guess.
"""

import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Literal

from app.pipeline.generate.verify import verify_draft
from app.pipeline.retrieve.retriever import DEFAULT_RRF_K, QUERY_CANDIDATES
from app.providers.contracts import Llm, Retriever
from app.schemas import Chunk

logger = logging.getLogger(__name__)

ABSTAIN_MESSAGE = "I cannot answer that from the books."
DEFAULT_TOP_K = 5
# One extra draft when deterministic verification rejects the first one. A
# deliberate refusal is final, so this costs one call only on a real failure.
DEFAULT_MAX_RETRIES = 1
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

RETRY_SYSTEM_PROMPT = (
    SYSTEM_PROMPT
    + " Your previous draft failed verification because it cited no excerpt. "
    "Answer again in one short paragraph and finish with at least one excerpt id "
    "in square brackets, copied exactly from the excerpts."
)

_CITATION = re.compile(r"\[([^\]]+)\]")
_ID_SEPARATOR = re.compile(r"[,\s]+")
# The model is told to reply with ABSTAIN_MESSAGE verbatim. Real replies drift,
# so common paraphrases also count as a refusal and are never retried.
_REFUSAL_PREFIX = re.compile(
    r"^(i (cannot|can't|can not) answer|i (do not|don't) know|"
    r"the (excerpts|books|passages) (do not|don't) (say|contain|mention|cover)|"
    r"there is no (information|evidence))",
    re.IGNORECASE,
)
# A refusal that trails on into "so I am unable ..." stays a refusal.
_REFUSAL_CLAUSE = re.compile(
    r"^(?:(?:so|and|therefore|thus|also)\b[,:\s]*)?"
    r"(i (cannot|can't|can not) (answer|say|confirm|help)|"
    r"i (do not|don't) know|i am (unable|not able)|"
    r"no (information|evidence|answer|mention)|"
    r"not (enough|sufficient) (information|evidence)|"
    r"the (excerpts|books|passages) (do not|don't) (say|contain|mention|cover)|"
    r"nothing (in|about))",
    re.IGNORECASE,
)
# Clause boundaries inside the refusal tail: punctuation and contrast.
_CLAUSE_SPLIT = re.compile(
    r"[.;:,!?]|\b(?:but|however|although|though|yet)\b", re.IGNORECASE
)

TokenSink = Callable[[str], None]
StageSink = Callable[[str], None]
AbstainReason = Literal["no_evidence", "uncited", "refused"]


@dataclass(frozen=True)
class AskResult:
    """A grounded answer plus the chunk ids it rests on.

    `attempts` counts drafts generated; it is 0 when retrieval abstained before
    any draft. `abstain_reason` separates a weak retrieval (`no_evidence`) from a
    draft that cited nothing (`uncited`) or refused (`refused`), so callers do
    not have to infer it from the text.
    """

    answer: str
    citations: list[str] = field(default_factory=list)
    abstained: bool = False
    chunks: list[Chunk] = field(default_factory=list)
    attempts: int = 0
    retry_reason: str | None = None
    abstain_reason: AbstainReason | None = None


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
        return AskResult(
            ABSTAIN_MESSAGE, abstained=True, chunks=chunks, abstain_reason="uncited"
        )
    return AskResult(
        _drop_unknown_citations(answer, allowed),
        citations,
        chunks=chunks,
    )


async def ask(
    question: str,
    *,
    retriever: Retriever,
    llm: Llm,
    top_k: int = DEFAULT_TOP_K,
    min_score: float | None = None,
    on_token: TokenSink | None = None,
    on_reset: Callable[[], None] | None = None,
    on_stage: StageSink | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> AskResult:
    """Answer from the corpus, citing chunk ids, or abstain on weak retrieval.

    One draft is generated and verified deterministically. A draft that is empty
    or uncited is regenerated at most `max_retries` times with a stricter prompt;
    a deliberate abstention is final, because forcing an answer would trade
    grounding for coverage.

    When on_token is supplied, generation streams and forwards each token.
    on_reset runs once before a retry so the client can discard the rejected
    draft. The grounding check still runs on the complete answer, so a streamed
    draft can still end in abstention.
    """
    floor = retrieval_floor(retriever, min_score)
    if on_stage is not None:
        on_stage("retrieve")
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
        return AskResult(
            ABSTAIN_MESSAGE,
            abstained=True,
            chunks=chunks,
            attempts=0,
            abstain_reason="no_evidence",
        )

    prompt = build_prompt(question, chunks)
    if on_stage is not None:
        on_stage("generate")
    generate_start = time.perf_counter()
    attempt = 0
    retry_reason: str | None = None
    while True:
        attempt += 1
        system = SYSTEM_PROMPT if attempt == 1 else RETRY_SYSTEM_PROMPT
        draft = await _one_draft(system, prompt, llm, on_token)
        result = ground_answer(draft, chunks)
        verdict = verify_draft(draft, result)
        refusal = _is_refusal(draft, cited=bool(result.citations))
        if verdict.ok or refusal or attempt > max_retries:
            break
        retry_reason = verdict.reason
        logger.info(
            "retry (%s): attempt=%d of %d",
            verdict.reason,
            attempt + 1,
            max_retries + 1,
        )
        if on_reset is not None:
            on_reset()
    generate_ms = (time.perf_counter() - generate_start) * 1000
    if _is_refusal(draft, cited=bool(result.citations)):
        # A refusal is final even when the draft also carries a citation: the
        # answer says it cannot answer, so it must not be returned as grounded.
        result = AskResult(
            ABSTAIN_MESSAGE,
            abstained=True,
            chunks=chunks,
            abstain_reason="refused",
        )
    result = replace(result, attempts=attempt, retry_reason=retry_reason)

    if result.abstained:
        logger.info(
            "abstain (%s): hits=%d attempts=%d generate=%.0fms",
            result.abstain_reason or "uncited",
            len(chunks),
            result.attempts,
            generate_ms,
        )
        return result

    logger.info(
        "answered: model=%s hits=%d citations=%d attempts=%d top=%.4f "
        "retrieve=%.0fms generate=%.0fms",
        getattr(llm, "name", "?"),
        len(chunks),
        len(result.citations),
        result.attempts,
        chunks[0].score,
        retrieve_ms,
        generate_ms,
    )
    return result


async def _one_draft(
    system: str, prompt: str, llm: Llm, on_token: TokenSink | None
) -> str:
    """Generate one draft, streaming it when the caller wants tokens."""
    if on_token is None:
        return await llm.generate(system, prompt)
    pieces: list[str] = []
    async for token in llm.stream(system, prompt):
        pieces.append(token)
        on_token(token)
    return "".join(pieces)


def _is_refusal(draft: str, *, cited: bool) -> bool:
    """A model that says it cannot answer is not a verification failure.

    The verbatim sentinel is a refusal even when a citation follows it. A
    paraphrase refusal is final when it cites nothing, or when every clause
    after the refusal statement is itself a refusal or a bare object. A cited
    partial answer that moves on to a clause stating content is kept.
    """
    text = draft.strip()
    if text.startswith(ABSTAIN_MESSAGE):
        return True
    clean = _CITATION.sub(" ", text).strip()
    if _REFUSAL_PREFIX.match(clean) is None:
        return False
    if not cited:
        return True
    clauses = [part.strip() for part in _CLAUSE_SPLIT.split(clean) if part.strip()]
    for clause in clauses[1:]:
        words = re.findall(r"[A-Za-z0-9]+", clause)
        if len(words) >= 2 and _REFUSAL_CLAUSE.match(clause) is None:
            return False
    return True


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
