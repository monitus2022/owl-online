"""Compare practice/feedback quality, latency and cost across two models.

Runs each fixture item through the real practice/feedback graph, checks citations
deterministically, then asks the pinned judge. This is a decision tool, not part
of the production gate.

  uv run python scripts/compare_routing.py \
    --models qwen/qwen3-30b-a3b-instruct-2507,mistralai/mistral-small-3.2-24b-instruct
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.agent import build_graph  # noqa: E402
from app.config import settings  # noqa: E402
from app.pipeline.generate import render_evidence  # noqa: E402
from app.pipeline.retrieve import compose_retriever  # noqa: E402
from app.providers.factory import make_embedder, make_llm, make_reranker  # noqa: E402
from eval.harness import JUDGE_MODEL, CachedLlm  # noqa: E402
from eval.harness.routing import (  # noqa: E402
    FEEDBACK_JUDGE_SYSTEM,
    PRACTICE_JUDGE_SYSTEM,
    parse_routing_verdict,
)


def _price(model: str) -> tuple[float, float]:
    if model == settings.small_model:
        return (
            settings.chat_small_input_price_per_mtok,
            settings.chat_small_output_price_per_mtok,
        )
    return settings.chat_input_price_per_mtok, settings.chat_output_price_per_mtok


async def _score(item: dict, state: dict, judge) -> dict:
    citations = list(state.get("citations", []))
    expected = set(item["expected_chunk_ids"])
    behavior = item.get("expected_behavior", "answer")
    if behavior == "answer":
        citation_ok = bool(citations) and bool(set(citations) & expected)
    else:
        citation_ok = True
    abstain_ok = state.get("abstained", False) if behavior == "abstain" else None
    evidence = render_evidence(list(state.get("chunks", [])))
    task = item["question"]
    extra = ""
    if item["intent"] == "feedback":
        task = f"{task}\nStudent answer: {item['student_answer']}"
        extra = f"\nReference: {item['reference_answer']}\nRubric: {item['rubric']}"
    prompt = (
        f"Excerpts:\n{evidence}\n\nTask: {task}{extra}\n\n"
        f"Generated response: {state.get('answer', '')}"
    )
    system = (
        PRACTICE_JUDGE_SYSTEM
        if item["intent"] == "practice"
        else FEEDBACK_JUDGE_SYSTEM
    )
    raw = await judge.generate(system, prompt)
    verdict = parse_routing_verdict(raw, item["intent"])
    return {
        "citation_ok": citation_ok,
        "abstain_ok": abstain_ok,
        "verdict": verdict,
        "chars_in": len(item["question"]) + len(item.get("student_answer") or "")
        + sum(len(chunk.text) for chunk in state.get("chunks", [])),
        "chars_out": len(state.get("answer", "")),
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixture", type=Path, default=REPO / "eval/fixtures/practice_feedback.jsonl"
    )
    parser.add_argument(
        "--models",
        default="qwen/qwen3-30b-a3b-instruct-2507,"
        "mistralai/mistral-small-3.2-24b-instruct",
    )
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()
    items = [json.loads(line) for line in args.fixture.read_text().splitlines() if line]
    models = [m.strip() for m in args.models.split(",") if m.strip()]

    reranker = (
        None
        if settings.rerank_provider == "none"
        else make_reranker(settings.rerank_provider)
    )
    setup = await compose_retriever(
        settings.chunks_path,
        settings.index_dir,
        make_embedder(settings.embedder_provider),
        reranker=reranker,
        pool=settings.rerank_pool if reranker is not None else None,
        min_score=settings.rerank_min_score,
    )
    judge = CachedLlm(
        make_llm("openrouter", model=JUDGE_MODEL, temperature=0.0, max_tokens=2048),
        JUDGE_MODEL,
        REPO / "eval" / ".cache",
        variant="routing",
    )
    print(
        f"fixture: {len(items)} items; judge: {JUDGE_MODEL}; "
        "caps: generator=512, judge=2048"
    )
    print(
        f"{'model':<48} {'cites':>5} {'topic':>5} {'ground':>6} "
        f"{'answer':>6} {'bound':>5} {'band':>5} {'err':>4} "
        f"{'p50ms':>6} {'fail':>4} {'parse':>5} {'cost/1k':>8}"
    )
    for slug in models:
        llm = make_llm("openrouter", model=slug, temperature=0.0, max_tokens=512)
        graph = build_graph(setup.retriever, llm)
        latencies: list[float] = []
        rows = []
        for item in items:
            state_in = {
                "question": item["question"],
                "requested_mode": item["intent"],
                "student_answer": item.get("student_answer"),
                "top_k": args.k,
            }
            start = time.perf_counter()
            try:
                state = await graph.ainvoke(state_in)
                row = await _score(item, state, judge)
            except Exception as exc:  # noqa: BLE001 - report, do not abort the sweep
                rows.append({"citation_ok": False, "verdict": None, "error": str(exc)})
                continue
            latencies.append((time.perf_counter() - start) * 1000)
            rows.append(row)
        practice = [r for r, i in zip(rows, items, strict=True) if i["intent"] == "practice"]
        feedback = [r for r, i in zip(rows, items, strict=True) if i["intent"] == "feedback"]
        pv = [r["verdict"] for r in practice if r.get("verdict")]
        fv = [r["verdict"] for r in feedback if r.get("verdict")]
        failed = sum(1 for r in rows if r.get("error"))
        parse_fail = len(rows) - failed - len(pv) - len(fv)
        band_ok = sum(
            1
            for r, i in zip(feedback, [x for x in items if x["intent"] == "feedback"], strict=True)
            if r.get("verdict") and r["verdict"]["band"] == i["band"]
        )
        err_items = [
            r["verdict"]
            for r, i in zip(feedback, [x for x in items if x["intent"] == "feedback"], strict=True)
            if r.get("verdict") and i["band"] != "strong"
        ]
        input_price, output_price = _price(slug)
        cost = statistics.mean(
            (r.get("chars_in", 0) / 4 * input_price + r.get("chars_out", 0) / 4 * output_price)
            / 1_000_000
            for r in rows
            if r.get("chars_in")
        ) if any(r.get("chars_in") for r in rows) else 0.0
        print(
            f"{slug:<48} {sum(r['citation_ok'] for r in rows):>3}/{len(rows):<2} "
            f"{sum(v['on_topic'] for v in pv):>3}/{len(pv):<2} "
            f"{sum(v['grounded'] for v in pv+fv):>4}/{len(pv+fv):<2} "
            f"{sum(v['answerable'] for v in pv):>4}/{len(pv):<2} "
            f"{sum(v['boundary'] for v in pv+fv):>3}/{len(pv+fv):<2} "
            f"{band_ok:>3}/{len(feedback):<2} "
            f"{sum(v['error_named'] for v in err_items):>3}/{len(err_items):<2} "
            f"{statistics.median(latencies) if latencies else 0:>6.0f} "
            f"{failed:>4} {parse_fail:>5} "
            f"${cost*1000:>7.2f}"
        )
    return 0 if any(r.get('verdict') for r in rows) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
