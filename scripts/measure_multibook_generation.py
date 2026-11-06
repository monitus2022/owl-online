"""Measure the multi-book answer path on the held-out aggregation fixture.

This is a generation run, not a retrieval run: it calls `ask()` with the flag on,
so routing, per-book extraction, synthesis and the coverage statement all run.
It records answer coverage, entity completeness, citation validity, faithfulness,
latency and token spend for the shipped configuration.

Run:
  uv run python scripts/measure_multibook_generation.py
  uv run python scripts/measure_multibook_generation.py --fixture <path>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import median

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.config import settings  # noqa: E402
from app.pipeline.generate import ask  # noqa: E402
from app.pipeline.generate.multibook import DEFAULT_FINAL_TOP_K, PER_BOOK_K  # noqa: E402
from app.pipeline.index.builder import load_chunks  # noqa: E402
from app.pipeline.retrieve import compose_retriever  # noqa: E402
from app.pipeline.retrieve.strategy import classify_retrieval_strategy  # noqa: E402
from app.providers.contracts import Llm  # noqa: E402
from app.providers.factory import make_embedder, make_llm, make_reranker  # noqa: E402
from app.schemas import Chunk  # noqa: E402
from eval.harness import (  # noqa: E402
    FAITHFUL_SYSTEM,
    AggregationItem,
    entity_matches,
    load_aggregation,
    missing_entities,
    parse_faithful,
)
from eval.harness.judging import JUDGE_MODEL  # noqa: E402
from eval.results import load_manifest  # noqa: E402


@dataclass(frozen=True)
class ItemScore:
    """One item's answer-level outcome.

    `books_covered` and `entities_found` use the cited evidence: a book counts
    when the answer cites a chunk from it that names an expected entity. This is
    the generation analogue of the retrieval aggregation metric.
    `answer_books_covered` and `answer_entities_found` are stricter: the entity
    must appear in that book's answer text. The gap between the two is extractor
    precision, not coverage.
    """

    item_id: str
    kind: str
    routed: str
    abstained: bool
    books_expected: int
    books_covered: int
    entities_expected: int
    entities_found: int
    answer_books_covered: int
    answer_entities_found: int
    citations: int
    valid_citations: int
    faithful: bool | None
    latency_ms: float
    model_calls: int
    input_chars: int
    output_chars: int


class _CountingLlm:
    """Proxy that records calls and character volume for the spend estimate."""

    def __init__(self, inner: Llm) -> None:
        self.inner = inner
        self.name = getattr(inner, "name", "?")
        self.calls = 0
        self.input_chars = 0
        self.output_chars = 0

    def reset(self) -> None:
        self.calls = 0
        self.input_chars = 0
        self.output_chars = 0

    async def generate(self, system: str, prompt: str, *, context=None) -> str:
        self.calls += 1
        self.input_chars += len(system) + len(prompt)
        reply = await self.inner.generate(system, prompt, context=context)
        self.output_chars += len(reply)
        return reply

    def stream(self, system: str, prompt: str, *, context=None):
        self.calls += 1
        self.input_chars += len(system) + len(prompt)

        async def gen():
            async for token in self.inner.stream(system, prompt, context=context):
                self.output_chars += len(token)
                yield token

        return gen()


def _chunk_index(chunks: list[Chunk]) -> dict[str, Chunk]:
    return {chunk.id: chunk for chunk in chunks}


def _is_relevant(item: AggregationItem, chunk: Chunk) -> bool:
    book = next((b for b in item.books if b.book_num == chunk.metadata.book_num), None)
    if book is None:
        return False
    return any(entity_matches(chunk.text, entity) for entity in book.expected_entities)


def _answer_sections(answer: str) -> dict[int, str]:
    """Split a multi-book answer into per-book text, keyed by book number."""
    sections: dict[int, list[str]] = {}
    current: int | None = None
    for raw in answer.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = re.match(r"^Book (\d+):", line)
        if match:
            current = int(match.group(1))
            sections.setdefault(current, []).append(line)
        elif current is not None:
            if line.startswith("Coverage:"):
                current = None
            else:
                sections[current].append(line)
    return {book: "\n".join(lines) for book, lines in sections.items()}


def _answer_coverage(item: AggregationItem, answer: str) -> tuple[int, int, int, int]:
    """Strict answer-text coverage: an entity must appear in that book's text.

    A labelled answer is scored per book: an entity only counts for the book
    whose section states it. A single-pass answer has no labels, so it is
    scored as one block.
    """
    sections = _answer_sections(answer)
    covered_books = 0
    expected_entities = 0
    found_entities = 0
    for book in item.books:
        text = sections.get(book.book_num, "") if sections else answer
        covered = False
        for entity in book.expected_entities:
            expected_entities += 1
            if entity_matches(text, entity):
                found_entities += 1
                covered = True
        covered_books += int(covered)
    return len(item.books), covered_books, expected_entities, found_entities


def _cited_coverage(
    item: AggregationItem, cited: list[Chunk]
) -> tuple[int, int, int, int]:
    """Cited-evidence coverage: a book counts when a cited chunk names an entity."""
    covered_books = 0
    expected_entities = 0
    found_entities = 0
    for book in item.books:
        book_chunks = [c for c in cited if c.metadata.book_num == book.book_num]
        covered = False
        for entity in book.expected_entities:
            expected_entities += 1
            if any(entity_matches(chunk.text, entity) for chunk in book_chunks):
                found_entities += 1
                covered = True
        covered_books += int(covered)
    return len(item.books), covered_books, expected_entities, found_entities


def _render_evidence(chunks: list[Chunk]) -> str:
    return "\n\n".join(
        f"[{chunk.id}] {chunk.metadata.book_name}: {chunk.text}" for chunk in chunks
    )


async def _faithful(judge: Llm, item: AggregationItem, answer: str, chunks: list[Chunk]):
    if not chunks:
        return None
    prompt = (
        f"Excerpts:\n{_render_evidence(chunks)}\n\n"
        f"Question: {item.question}\n\n"
        f"Answer: {answer}"
    )
    reply = parse_faithful(await judge.generate(FAITHFUL_SYSTEM, prompt))
    return reply


async def run(args) -> int:
    items = load_aggregation(args.fixture)
    corpus = load_chunks(args.chunks)
    missing = missing_entities(items, corpus)
    if missing:
        print("fixture entities missing from the corpus:", file=sys.stderr)
        for line in missing:
            print(f"  {line}", file=sys.stderr)
        return 1
    by_id = _chunk_index(corpus)

    reranker = (
        None
        if settings.rerank_provider == "none"
        else make_reranker(settings.rerank_provider)
    )
    setup = await compose_retriever(
        args.chunks,
        args.index,
        make_embedder(settings.embedder_provider),
        reranker=reranker,
        pool=settings.rerank_pool if reranker is not None else None,
        min_score=settings.rerank_min_score,
        subquery_quota=settings.subquery_quota,
    )
    # The eval needs real hosted models; the judge is pinned to OpenRouter and
    # is a different family from the generator (AGENTS.md).
    llm = _CountingLlm(make_llm("openrouter", temperature=0.0))
    judge = make_llm("openrouter", model=JUDGE_MODEL, temperature=0.0)
    judge_model = JUDGE_MODEL

    scores: list[ItemScore] = []
    try:
        for item in items:
            routed = classify_retrieval_strategy(item.question).name
            llm.reset()
            start = time.perf_counter()
            result = await ask(
                item.question,
                retriever=setup.retriever,
                llm=llm,
                top_k=DEFAULT_FINAL_TOP_K,
                multi_book=True,
            )
            latency_ms = (time.perf_counter() - start) * 1000
            cited_chunks = [
                by_id[cid] for cid in result.citations if cid in by_id
            ]
            books_expected, books_covered, entities_expected, entities_found = (
                _cited_coverage(item, cited_chunks)
            )
            (
                _,
                answer_books_covered,
                _,
                answer_entities_found,
            ) = _answer_coverage(item, result.answer)
            valid = sum(_is_relevant(item, chunk) for chunk in cited_chunks)
            # The coverage statement is deterministic retrieval bookkeeping, not
            # a model claim, so faithfulness judges the answer body.
            body = result.answer.split("\n\nCoverage:")[0]
            faithful = (
                None
                if result.abstained
                else await _faithful(judge, item, body, result.chunks)
            )
            scores.append(
                ItemScore(
                    item_id=item.id,
                    kind=item.kind,
                    routed=routed,
                    abstained=result.abstained,
                    books_expected=books_expected,
                    books_covered=books_covered,
                    entities_expected=entities_expected,
                    entities_found=entities_found,
                    answer_books_covered=answer_books_covered,
                    answer_entities_found=answer_entities_found,
                    citations=len(result.citations),
                    valid_citations=valid,
                    faithful=faithful,
                    latency_ms=latency_ms,
                    model_calls=result.model_calls,
                    input_chars=llm.input_chars,
                    output_chars=llm.output_chars,
                )
            )
            print(
                f"{item.id:8} {item.kind:11} route={routed:10} "
                f"books={books_covered}/{books_expected} "
                f"ents={entities_found}/{entities_expected} "
                f"text={answer_books_covered}/{books_expected} "
                f"cite={valid}/{len(result.citations)} "
                f"faithful={faithful} calls={result.model_calls} "
                f"{latency_ms:.0f}ms"
            )
    finally:
        await setup.retriever.aclose()

    multi = [score for score in scores if score.kind == "multi_book"]
    near = [score for score in scores if score.kind == "near_miss"]

    def mean(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    coverage = mean([s.books_covered / s.books_expected for s in multi])
    completeness = mean([s.entities_found / s.entities_expected for s in multi])
    text_coverage = mean([s.answer_books_covered / s.books_expected for s in multi])
    text_completeness = mean(
        [s.answer_entities_found / s.entities_expected for s in multi]
    )
    full = mean([1.0 if s.books_covered == s.books_expected else 0.0 for s in multi])
    citations = sum(s.citations for s in multi)
    valid = sum(s.valid_citations for s in multi)
    judged = [s.faithful for s in multi if s.faithful is not None]
    faithful_rate = mean([1.0 if value else 0.0 for value in judged])
    abstained = mean([1.0 if s.abstained else 0.0 for s in multi])
    latencies = sorted(s.latency_ms for s in multi)
    p50 = median(latencies) if latencies else 0.0
    p95 = latencies[max(0, int(len(latencies) * 0.95) - 1)] if latencies else 0.0
    calls = sum(s.model_calls for s in multi)
    input_tokens = sum(s.input_chars for s in multi) // 4
    output_tokens = sum(s.output_chars for s in multi) // 4
    spend = (
        input_tokens * settings.chat_input_price_per_mtok
        + output_tokens * settings.chat_output_price_per_mtok
    ) / 1_000_000
    near_hit = mean([1.0 if s.entities_found > 0 else 0.0 for s in near])
    near_share = (
        sum(s.valid_citations for s in near) / sum(s.citations for s in near)
        if sum(s.citations for s in near)
        else 0.0
    )

    manifest = load_manifest()
    embedder_key = "cloud" if settings.embedder_provider == "bedrock" else "local"
    print()
    print(f"run: {args.run_id}")
    print(
        f"path=multi_book per_book_k={PER_BOOK_K} final_top_k={DEFAULT_FINAL_TOP_K} "
        f"manifest: generator={manifest['generator']['model']} "
        f"judge={judge_model} "
        f"reranker={manifest['reranker']['model']} pool={settings.rerank_pool} "
        f"embedder={manifest['embedder'][embedder_key]['model']} "
        f"chunking={manifest['chunking']['size']}/{manifest['chunking']['overlap']}/"
        f"{manifest['chunking']['min_size']} "
        f"rrf_k={manifest['retrieval']['rrf_k']} quota={settings.subquery_quota}"
    )
    print("aggregate")
    print(
        f"  multi_book n={len(multi)} book_coverage={coverage:.2f} "
        f"full_coverage={full:.2f} entity_completeness={completeness:.2f}"
    )
    print(
        f"  answer_text book_coverage={text_coverage:.2f} "
        f"entity_completeness={text_completeness:.2f}"
    )
    print(
        f"  citation_validity={valid / citations if citations else 0.0:.2f} "
        f"faithfulness={faithful_rate:.2f} (n={len(judged)}) "
        f"abstention={abstained:.2f}"
    )
    print(
        f"  near_miss n={len(near)} entity_hit={near_hit:.2f} "
        f"book_share={near_share:.2f}"
    )
    print(
        f"  latency p50={p50:.0f}ms p95={p95:.0f}ms "
        f"model_calls={calls} input_tokens~{input_tokens} "
        f"output_tokens~{output_tokens} spend~${spend:.4f}"
    )

    args.results.mkdir(parents=True, exist_ok=True)
    path = args.results / f"{args.run_id}-multibook-generation.csv"
    path.write_text(
        "item_id,kind,routed,abstained,books_expected,books_covered,"
        "entities_expected,entities_found,answer_books_covered,"
        "answer_entities_found,citations,valid_citations,faithful,"
        "latency_ms,model_calls,input_chars,output_chars\n"
        + "\n".join(
            ",".join(
                [
                    s.item_id,
                    s.kind,
                    s.routed,
                    str(s.abstained),
                    str(s.books_expected),
                    str(s.books_covered),
                    str(s.entities_expected),
                    str(s.entities_found),
                    str(s.answer_books_covered),
                    str(s.answer_entities_found),
                    str(s.citations),
                    str(s.valid_citations),
                    "" if s.faithful is None else str(s.faithful),
                    f"{s.latency_ms:.0f}",
                    str(s.model_calls),
                    str(s.input_chars),
                    str(s.output_chars),
                ]
            )
            for s in scores
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"csv: {path}")
    print(
        "summary: "
        + json.dumps(
            {
                "coverage": round(coverage, 3),
                "completeness": round(completeness, 3),
                "answer_text_coverage": round(text_coverage, 3),
                "answer_text_completeness": round(text_completeness, 3),
                "citation_validity": round(valid / citations if citations else 0.0, 3),
                "faithfulness": round(faithful_rate, 3),
                "latency_p50_ms": round(p50, 0),
                "latency_p95_ms": round(p95, 0),
                "spend_usd": round(spend, 4),
            }
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure multi-book generation on the aggregation fixture"
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=REPO / "eval" / "fixtures" / "aggregation_holdout.jsonl",
    )
    parser.add_argument("--chunks", type=Path, default=REPO / "data" / "chunks.jsonl")
    parser.add_argument(
        "--index", type=Path, default=REPO / "data" / "index" / "chroma"
    )
    parser.add_argument(
        "--results", type=Path, default=REPO / "eval" / "results"
    )
    parser.add_argument(
        "--run-id",
        default=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
    )
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
