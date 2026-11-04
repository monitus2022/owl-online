# Run record: V2 D3 contextual retrieval experiment

- Date: 2026-11-05
- Run id: `20261104T185945Z`
- Ticket: #78 (V2 D3)
- Config: contextual chunks, 0.6B embedder, reranker on
- Artifacts: `eval/results/20261104T185945Z.csv` (local, gitignored)
- Status: rejected experiment, baseline unchanged

## Setup

| Field | Value |
|---|---|
| Embedder | `local` / `qwen3-embedding:0.6b`, 1024 dims |
| Chunks | `data/chunks_context.jsonl` |
| Context coverage | 14,259 of 15,658 chunks; 1,399 text-only book 7 tail |
| Context source | pinned Qwen generator, temperature 0, 2 sentences, 300 char cap |
| Reranker | `amazon.rerank-v1:0`, pool 50 |
| Retrieval | hybrid (dense + BM25, RRF), `k = 5`, `rrf_k = 60`, candidates 50 |

The generated context was prepended to the indexed text only. Generation and
citations still used the original chunk.

## Comparison

Baseline is run `20261104T154503Z`.

| Slice | Hit@5 base | Hit@5 context | Recall@5 base | Recall@5 context | MRR base | MRR context |
|---|---|---|---|---|---|---|
| overall | 0.76 | 0.72 | 0.66 | 0.61 | 0.50 | 0.50 |
| named_reference | 1.00 | 1.00 | 1.00 | 1.00 | 0.78 | 0.78 |
| simple | 0.74 | 0.68 | 0.62 | 0.56 | 0.46 | 0.44 |
| multi_part | 0.62 | 0.62 | 0.50 | 0.44 | 0.40 | 0.45 |

| Stage | Baseline | Contextual |
|---|---|---|
| dense recall@pool | 0.77 | 0.76 |
| sparse recall@pool | 0.68 | 0.73 |
| pool recall@pool | 0.81 | 0.80 |
| rerank lift | 0.86 | 0.80 |
| faithful | 12/15 | 12/15 |
| judge correct | 12/15 | 13/15 |

## Reading

- Contextual indexing is a net regression. Overall Hit@5 drops from 0.76 to
  0.72 and simple from 0.74 to 0.68. Named is unchanged at 1.00.
- Only two simple items flipped from hit to miss (`q02`, `s01`). The missing
  9% of chunks do not explain the loss: `q18`, `q20` and `n08` are unchanged.
- Sparse recall improves from 0.68 to 0.73, so the context does add lexical
  signal. Dense and pool recall fall, and rerank lift drops from 0.86 to 0.80.
  The 0.6B embedder is the likely limit: longer, denser text is harder for it.
- Multi-part MRR improves from 0.40 to 0.45, but Hit@5 and recall do not. That is
  not enough to keep the change.
- Generation improves slightly (F1 0.32 to 0.31 is flat; judge correct 12 to 13),
  but it is not a retrieval win.

## Cost

The full pass ran out of OpenRouter credits at 14,259 chunks. The remaining
balance was about $0.07. Based on the 200-chunk sample and token counts, the
generated contexts cost roughly $0.70-0.90. The index build is local and free.
This is a one-time cost, not a per-query cost.

## Decision

Rejected. Keep the text-only index and the 0.76 baseline. The next retrieval
lever is a stronger embedder, not more context on the 0.6B model. If the 4B
embedder does not move simple recall, move to the agent work and leave the
remaining `m06`/`m07` misses as documented limitations.

## Reproduce

```
uv run python scripts/build_contexts.py --cache-only
uv run python scripts/build_index.py --chunks data/chunks_context.jsonl --index data/index/chroma-context
uv run python scripts/run_eval.py --chunks data/chunks_context.jsonl --index data/index/chroma-context
```

## Raw summary

```text
gold: 60 items (50 answerable, 10 unanswerable)
config: pinned
generator: openrouter/qwen/qwen3-30b-a3b-instruct-2507
judge: openrouter/deepseek/deepseek-v4.1-flash-1017
reranker: bedrock

retrieval
  overall                n=50  Hit@5=0.72 Recall@5=0.61 MRR=0.50
  multi_part             n=8   Hit@5=0.62 Recall@5=0.44 MRR=0.45
  named_reference        n=8   Hit@5=1.00 Recall@5=1.00 MRR=0.78
  simple                 n=34  Hit@5=0.68 Recall@5=0.56 MRR=0.44

retrieval diagnostics
  overall                n=50  dense=0.76 sparse=0.73 pool=0.80 lift=0.80 loss=0.20 near=0.06
  multi_part             n=8   dense=0.67 sparse=0.77 pool=0.77 lift=0.62 loss=0.38 near=0.00
  named_reference        n=8   dense=1.00 sparse=1.00 pool=1.00 lift=1.00 loss=0.00 near=0.00
  simple                 n=34  dense=0.73 sparse=0.65 pool=0.76 lift=0.79 loss=0.21 near=0.09

abstention
  overall                10/10 (1.00)
  near_miss_unanswerable 5/5 (1.00)
  off_topic              5/5 (1.00)

generation (judged sample)
  overall                n=15  answered=15  abstained=0   EM=0.00 F1=0.31 faithful=12/15 (0.80) judge correct=13 partial=1 wrong=1 grounded=13 judge_parse=0 faithful_parse=0
  multi_part             n=5   answered=5   abstained=0   EM=0.00 F1=0.44 faithful=2/5 (0.40) judge correct=3 partial=1 wrong=1 grounded=3 judge_parse=0 faithful_parse=0
  named_reference        n=5   answered=5   abstained=0   EM=0.00 F1=0.28 faithful=5/5 (1.00) judge correct=5 partial=0 wrong=0 grounded=5 judge_parse=0 faithful_parse=0
  simple                 n=5   answered=5   abstained=0   EM=0.00 F1=0.21 faithful=5/5 (1.00) judge correct=5 partial=0 wrong=0 grounded=5 judge_parse=0 faithful_parse=0
```
