# Run record: single-hop k=7 comparison

- Date: 2026-11-06
- Run id: `20261106T105801Z`
- Ticket: #96
- Config: `aggregation`, single-hop, top-k 7, quota 0
- Artifacts: no result CSV (retrieval-only script); `eval/fixtures/aggregation.jsonl`

## Configuration

| Field | Value |
|---|---|
| Path | single-hop, one pass |
| Final top-k | 7, equal to the routed per-book run |
| Generator | `qwen/qwen3-30b-a3b-instruct-2507` (manifest; not called) |
| Judge | `deepseek/deepseek-v4.1-flash-1017` (manifest; not called) |
| Reranker | `amazon.rerank-v1:0`, pool 50, floor 0.0 |
| Embedder | `local` / `qwen3-embedding:0.6b`, 1024 dims |
| Chunking | size 500, overlap 75, min size 200 |
| Retrieval | hybrid, `k = 7`, `rrf_k = 60`, candidates 50 |
| Sub-query quota | 0, global fusion |
| Fixture | 15 items: 10 multi-book, 5 near-miss |

## Retrieval

| Metric | Value |
|---|---:|
| Book coverage | 0.58 |
| Full coverage | 0.00 |
| Entity completeness | 0.56 |
| Citation validity | 0.71 |
| Near-miss entity hit | 1.00 |
| Near-miss entity completeness | 0.87 |
| Near-miss book precision | 0.40 |

## Reading

- This is the equal-budget comparison for `2026-11-06-v2-multibook-retrieval.md`.
  Both runs use top-k 7; the routed run uses per-book retrieval for multi-book
  items.
- Raising k from 5 to 7 already improves single-pass coverage from 0.46 to 0.58
  and completeness from 0.45 to 0.56. The routed per-book run adds a further
  gain to 0.79 and 0.76.
- Full coverage stays at 0.00 for single-hop: no multi-book item covers every
  expected book with one pass.
- Near-miss book precision falls from 0.48 at k=5 to 0.40 at k=7 because the
  wider set pulls more chunks from other books. The router still keeps those
  questions on the single-hop path.

## Gate

No pipeline, generation or gate metric changed. The existing gate still passes:

```text
uv run python scripts/run_eval.py --check --latest eval/results/20261106T060813Z.csv
gate: PASS
```

## Reproduce

```text
uv run python scripts/measure_aggregation.py --strategy single_hop --k 7 --run-id 20261106T105801Z
```

## Raw output

```text
run: 20261106T105801Z
strategy=single_hop per_book_k=1 manifest: generator=qwen/qwen3-30b-a3b-instruct-2507 judge=deepseek/deepseek-v4.1-flash-1017 reranker=amazon.rerank-v1:0 pool=50 embedder=qwen3-embedding:0.6b chunking=500/75/200 top_k=7 rrf_k=60 quota=0
router: precision=1.00 recall=1.00 tp=10 fp=0 fn=0
expected entities: 79
aggregation fixture
item     kind        books covered entities found citations valid
agg01    multi_book      7       3        7     3         7     6
agg02    multi_book      5       3        5     3         7     7
agg03    multi_book      7       5        7     5         7     7
agg04    multi_book      7       4        7     4         7     7
agg05    multi_book      7       4       17     6         7     6
agg06    multi_book      3       1        3     1         7     4
agg07    multi_book      3       2        3     2         7     7
agg08    multi_book      3       2        3     2         7     4
agg09    multi_book      7       4        7     4         7     6
agg10    multi_book      7       5        7     5         7     7
near01   near_miss       1       1        1     1         7     2
near02   near_miss       1       1        4     4         7     1
near03   near_miss       1       1        3     3         7     4
near04   near_miss       1       1        2     2         7     6
near05   near_miss       1       1        3     1         7     1

aggregate
  multi_book n=10 book_coverage=0.58 full_coverage=0.00 entity_completeness=0.56
  near_miss  n=5 entity_hit=1.00 entity_completeness=0.87 book_precision=0.40
  citation_validity=0.71
```
