# Run record: V2 D3 retrieval ablations

- Date: 2026-11-05
- Ticket: #78 (V2 D3)
- Run ids: `20261104T214110Z` (4B), `20261104T214334Z` (pool 100), `20261104T214458Z` (pool 30)
- Baseline: run `20261104T220147Z` (0.6B embedder, pool 50, text-only)
- Status: no variant beats the baseline; retrieval tuning stops

## Variants

| Variant | Run id | Hit@5 | Recall@5 | MRR | Named Hit@5 | Simple Hit@5 | Multi Hit@5 | Dense | Pool | Lift |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | `20261104T220147Z` | 0.76 | 0.66 | 0.50 | 1.00 | 0.74 | 0.62 | 0.77 | 0.81 | 0.86 |
| 4B embedder | `20261104T214110Z` | 0.76 | 0.65 | 0.49 | 1.00 | 0.74 | 0.62 | 0.83 | 0.82 | 0.84 |
| pool 100 | `20261104T214334Z` | 0.68 | 0.57 | 0.48 | 1.00 | 0.62 | 0.62 | 0.78 | 0.82 | 0.77 |
| pool 30 | `20261104T214458Z` | 0.74 | 0.63 | 0.52 | 0.88 | 0.74 | 0.62 | 0.75 | 0.74 | 0.88 |

## Reading

- The 4B embedder is the interesting result: dense recall rises from 0.77 to 0.83 and pool recall from 0.81 to 0.82, but Hit@5 is flat and rerank lift falls from 0.86 to 0.84. The better candidates are not converted into top-5 hits.
- Pool 100 makes it worse: overall Hit@5 drops to 0.68, simple to 0.62, and rerank lift to 0.77. More candidates dilute the reranker.
- Pool 30 raises MRR to 0.52 but loses one named item (0.88) and overall Hit@5
  falls to 0.74. That is within the slice noise band, but the named loss is not
  worth the MRR gain.
- Pool 50 remains the best tested setting. The remaining loss is in reranking
  and in the hard semantic items `m06`/`m07`, not in dense recall.
- The 4B index is local (`data/index/chroma-4b`) and costs no API tokens. It is not pinned because it does not improve the headline metric.

## Decision

Keep the 0.6B / pool-50 / text-only baseline. Do not switch embedder, pool size or contextual index. The next work is the agent foundation (D4). Revisit retrieval only with a different reranker or a query-rewriting agent, and treat `m06`/`m07` as known limitations until then.

## Reproduce

```
OWL_RERANK_POOL=100 uv run python scripts/run_eval.py
OWL_RERANK_POOL=30 uv run python scripts/run_eval.py
uv run python scripts/run_eval.py --index data/index/chroma-4b --embedder-model qwen3-embedding:4b
```

## Raw summary

```text
baseline 0.6B pool 50: overall Hit@5=0.76 Recall@5=0.66 MRR=0.50
4B pool 50:           overall Hit@5=0.76 Recall@5=0.65 MRR=0.49 dense=0.83 pool=0.82 lift=0.84
0.6B pool 100:        overall Hit@5=0.68 Recall@5=0.57 MRR=0.48 lift=0.77
0.6B pool 30:         overall Hit@5=0.74 Recall@5=0.63 MRR=0.52 named=0.88
```
