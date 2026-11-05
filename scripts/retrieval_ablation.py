"""Retrieval-only ablation for multi-part selection.

Compares the baseline against a per-sub-query quota and a larger top-k for
decomposed questions. No generation, no judge, no eval record.

  uv run python scripts/retrieval_ablation.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.config import settings  # noqa: E402
from app.pipeline.retrieve import compose_retriever  # noqa: E402
from app.pipeline.retrieve.decompose import split_question  # noqa: E402
from app.pipeline.retrieve.retriever import (  # noqa: E402
    _combine_filter,
    parse_metadata_filter,
)
from app.providers.factory import make_embedder, make_reranker  # noqa: E402
from eval.harness import load_gold, retrieval_metrics_all  # noqa: E402


class _QuotaRetriever:
    """Fuse each sub-query separately and keep the top `quota` from each."""

    def __init__(self, base, quota: int = 2) -> None:
        self._base = base
        self._quota = quota

    async def retrieve(self, query: str, top_k: int):
        sub = split_question(query)
        if len(sub) <= 1:
            return await self._base.retrieve(query, top_k)
        parts = sub + [query]
        base_filter = parse_metadata_filter(query)
        filters = [
            _combine_filter(parse_metadata_filter(part), base_filter)
            for part in parts
        ]
        dense = [
            await self._base._dense_run(part, spec)
            for part, spec in zip(parts, filters, strict=True)
        ]
        sparse = [
            await self._base._sparse_run(part, spec)
            for part, spec in zip(parts, filters, strict=True)
        ]
        ids: list[str] = []
        for dense_ids, sparse_ids in zip(dense, sparse, strict=True):
            for cid, _ in self._base._fuse_many([dense_ids, sparse_ids])[: self._quota]:
                if cid not in ids:
                    ids.append(cid)
        chunks = [
            self._base._chunks_by_id[cid].model_copy(update={"score": 1.0})
            for cid in ids
        ]
        if self._base._reranker is None:
            return chunks[:top_k]
        if not chunks:
            return []
        return await self._base._reranker.rerank(
            query, chunks, min(top_k, len(chunks))
        )


class _TopK8:
    def __init__(self, base) -> None:
        self._base = base

    async def retrieve(self, query: str, top_k: int):
        return (await self._base.retrieve(query, 8))[:top_k]


async def main() -> int:
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
    gold = load_gold(REPO / "eval/gold/questions.jsonl")
    variants = {
        "baseline": setup.retriever,
        "quota-2": _QuotaRetriever(setup.retriever, 2),
        "topk-8": _TopK8(setup.retriever),
    }
    print(f"{'variant':<12} {'slice':<16} {'n':>3} {'Hit@5':>6} {'Recall':>7} {'MRR':>6}")
    for name, retriever in variants.items():
        overall, by_slice = await retrieval_metrics_all(retriever, gold, 5)
        rows = [("overall", overall), *sorted(by_slice.items())]
        for slice_name, m in rows:
            print(
                f"{name:<12} {slice_name:<16} {m.n:>3} "
                f"{m.hit_at_k:>6.3f} {m.recall_at_k:>7.3f} {m.mrr:>6.3f}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
