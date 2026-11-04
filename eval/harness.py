"""Mini-eval harness: retrieval metrics and a judged generation sample.

Deliberately small (V1 D5, #51). The full harness as a CI gate is V2 (#9-#12).
Retrieval is scored on chunk ids; generation is scored by a second model.
"""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

from app.pipeline.generate import DEFAULT_TOP_K, ask
from app.providers.contracts import Llm, Retriever

# Judge pinned in config/manifest.toml (AGENTS.md: a different family from the
# Qwen generator). The eval reads it from the manifest rather than restating it.
JUDGE_MODEL = tomllib.loads(
    (Path(__file__).resolve().parents[1] / "config" / "manifest.toml").read_text(encoding="utf-8")
)["judge"]["model"]

JUDGE_SYSTEM = (
    "You grade a revision answer against the book excerpts provided. "
    'Reply with JSON only, no prose: {"correctness": "correct" | "partial" | '
    '"wrong", "grounded": true | false}. correctness is how well the answer '
    "matches the excerpts; grounded is whether every claim is supported by them."
)


@dataclass(frozen=True)
class GoldItem:
    """One gold question; expected_chunk_ids is empty for unanswerable items."""

    id: str
    question: str
    answerable: bool
    expected_chunk_ids: list[str]


def load_gold(path: Path) -> list[GoldItem]:
    """Read the gold JSONL into GoldItem records."""
    items: list[GoldItem] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        items.append(
            GoldItem(
                id=row["id"],
                question=row["question"],
                answerable=bool(row["answerable"]),
                expected_chunk_ids=list(row.get("expected_chunk_ids", [])),
            )
        )
    return items


@dataclass(frozen=True)
class RetrievalMetrics:
    """Hit@k, Recall@k and MRR over the answerable gold items."""

    n: int
    hit_at_k: float
    recall_at_k: float
    mrr: float


async def retrieval_metrics(
    retriever: Retriever, items: list[GoldItem], k: int
) -> RetrievalMetrics:
    """Score retrieval on chunk ids: hit if any expected id is in the top k."""
    answerable = [item for item in items if item.answerable]
    hits = 0
    recall = 0.0
    reciprocal = 0.0
    for item in answerable:
        retrieved = [chunk.id for chunk in await retriever.retrieve(item.question, k)]
        expected = set(item.expected_chunk_ids)
        found = expected.intersection(retrieved)
        if found:
            hits += 1
        recall += len(found) / len(expected) if expected else 0.0
        for rank, chunk_id in enumerate(retrieved, start=1):
            if chunk_id in expected:
                reciprocal += 1.0 / rank
                break
    n = len(answerable) or 1
    return RetrievalMetrics(len(answerable), hits / n, recall / n, reciprocal / n)


@dataclass(frozen=True)
class AbstentionMetrics:
    """How often ask() refused on the unanswerable gold items."""

    n: int
    refused: int

    @property
    def rate(self) -> float:
        return self.refused / self.n if self.n else 0.0


async def abstention_metrics(
    retriever: Retriever, llm: Llm, items: list[GoldItem], top_k: int = DEFAULT_TOP_K
) -> AbstentionMetrics:
    """Run the unanswerable items through ask() and count refusals."""
    unanswerable = [item for item in items if not item.answerable]
    refused = 0
    for item in unanswerable:
        result = await ask(item.question, retriever=retriever, llm=llm, top_k=top_k)
        if result.abstained:
            refused += 1
    return AbstentionMetrics(len(unanswerable), refused)


@dataclass(frozen=True)
class JudgeVerdict:
    """One judged answer: correctness bucket, grounded flag, or abstained."""

    question_id: str
    correctness: str
    grounded: bool
    abstained: bool


def _as_bool(value: object) -> bool:
    """Accept JSON booleans and the string forms a judge might emit."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "1"}


def parse_verdict(raw: str) -> tuple[str, bool]:
    """Pull correctness and grounded from a judge reply; tolerate extra prose."""
    # First flat JSON object only: a greedy match could span several objects.
    match = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
    if not match:
        return "wrong", False
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return "wrong", False
    correctness = str(data.get("correctness", "wrong")).lower()
    if correctness not in {"correct", "partial", "wrong"}:
        correctness = "wrong"
    return correctness, _as_bool(data.get("grounded", False))


async def judge_sample(
    retriever: Retriever,
    llm: Llm,
    judge: Llm,
    items: list[GoldItem],
    sample: int = 10,
    top_k: int = DEFAULT_TOP_K,
) -> list[JudgeVerdict]:
    """Generate answers for the first `sample` answerable items and judge them."""
    answerable = [item for item in items if item.answerable][:sample]
    verdicts: list[JudgeVerdict] = []
    for item in answerable:
        chunks = await retriever.retrieve(item.question, top_k)
        result = await ask(item.question, retriever=retriever, llm=llm, top_k=top_k)
        if result.abstained:
            verdicts.append(JudgeVerdict(item.id, "abstained", False, True))
            continue
        evidence = "\n\n".join(f"[{chunk.id}] {chunk.text}" for chunk in chunks)
        prompt = (
            f"Excerpts:\n{evidence}\n\n"
            f"Question: {item.question}\n\n"
            f"Answer: {result.answer}"
        )
        correctness, grounded = parse_verdict(await judge.generate(JUDGE_SYSTEM, prompt))
        verdicts.append(JudgeVerdict(item.id, correctness, grounded, False))
    return verdicts


class CachedLlm:
    """Llm wrapper caching generate() by (name, input) on disk (AGENTS.md)."""

    def __init__(self, inner: Llm, name: str, cache_dir: Path) -> None:
        self.name = name
        self._inner = inner
        self._dir = cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)

    async def generate(self, system: str, prompt: str, *, context: str | None = None) -> str:
        key = hashlib.sha256(
            json.dumps([self.name, system, prompt, context]).encode("utf-8")
        ).hexdigest()
        path = self._dir / f"{key}.txt"
        if path.exists():
            return path.read_text(encoding="utf-8")
        output = await self._inner.generate(system, prompt, context=context)
        path.write_text(output, encoding="utf-8")
        return output

    def stream(
        self, system: str, prompt: str, *, context: str | None = None
    ) -> AsyncIterator[str]:
        # Not cached: the eval only calls generate(); stream is passed through.
        return self._inner.stream(system, prompt, context=context)
