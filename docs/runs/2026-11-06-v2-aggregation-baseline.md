# Run record: aggregation fixture baseline

- Date: 2026-11-06
- Run id: `20261106T100459Z`
- Ticket: #96
- Config: `aggregation`, reranker on, quota 0, retrieval only
- Artifacts: `eval/fixtures/aggregation.jsonl`, `scripts/measure_aggregation.py`

## Configuration

| Field | Value |
|---|---|
| Generator | `qwen/qwen3-30b-a3b-instruct-2507` (manifest; not called) |
| Judge | `deepseek/deepseek-v4.1-flash-1017` (manifest; not called) |
| Reranker | `amazon.rerank-v1:0`, pool 50, floor 0.0 |
| Embedder | `local` / `qwen3-embedding:0.6b`, 1024 dims |
| Chunking | size 500, overlap 75, min size 200 |
| Retrieval | hybrid, `k = 5`, `rrf_k = 60`, candidates 50 |
| Sub-query quota | 0, global fusion |
| Fixture | 15 items: 10 multi-book, 5 near-miss |
| Expected entities | 79 across all 15 items (66 multi-book, 13 near-miss) |

## Retrieval

| Item | Kind | Books | Covered | Entities | Found | Citations | Valid |
|---|---|---:|---:|---:|---:|---:|---:|
| agg01 | multi_book | 7 | 2 | 7 | 2 | 5 | 5 |
| agg02 | multi_book | 5 | 3 | 5 | 3 | 5 | 5 |
| agg03 | multi_book | 7 | 4 | 7 | 4 | 5 | 5 |
| agg04 | multi_book | 7 | 2 | 7 | 2 | 5 | 5 |
| agg05 | multi_book | 7 | 3 | 17 | 5 | 5 | 4 |
| agg06 | multi_book | 3 | 1 | 3 | 1 | 5 | 3 |
| agg07 | multi_book | 3 | 1 | 3 | 1 | 5 | 5 |
| agg08 | multi_book | 3 | 2 | 3 | 2 | 5 | 4 |
| agg09 | multi_book | 7 | 4 | 7 | 4 | 5 | 5 |
| agg10 | multi_book | 7 | 4 | 7 | 4 | 5 | 5 |
| near01 | near_miss | 1 | 1 | 1 | 1 | 5 | 2 |
| near02 | near_miss | 1 | 1 | 4 | 4 | 5 | 1 |
| near03 | near_miss | 1 | 1 | 3 | 3 | 5 | 4 |
| near04 | near_miss | 1 | 1 | 2 | 2 | 5 | 4 |
| near05 | near_miss | 1 | 1 | 3 | 1 | 5 | 1 |

## Aggregate

| Metric | Value |
|---|---|
| Multi-book items | 10 |
| Near-miss items | 5 |
| Book coverage | 0.46 |
| Full coverage | 0.00 |
| Entity completeness | 0.45 |
| Citation validity | 0.77 |
| Near-miss entity hit | 1.00 |
| Near-miss entity completeness | 0.87 |
| Near-miss book precision | 0.48 |

## Reading

- One top-5 pass reaches less than half the expected books and less than half
  the expected entities. No multi-book item covers all of its books, which is
  the structural loss #96 describes.
- The per-item pattern is the expected one: a question whose evidence clusters
  in a few books (agg02, agg08) does better than one spread across seven
  (agg01, agg03, agg04).
- Citation validity is now relevance-aware: a chunk counts only if it is from an
  expected book and contains an expected entity for that book. The stricter
  metric is 0.77, not the vacuous 0.89 from counting every chunk in a seven-book
  question as valid.
- Near-miss entity hit is 1.00 but completeness is 0.87 and book precision is
  0.48. The near-misses are retrievable, but the retrieved set spreads beyond
  the single expected book. A plural count alone must not route them to the
  multi-book path.
- near05 uses `Hungarian Horntail`, `merpeople` and `maze`, not the generic
  `dragon`, so a dragon-blood chunk cannot satisfy the task.
- Every expected entity was checked against the corpus with word-boundary,
  plural-friendly matching before the run. The fixture does not use free model
  memory.
- This is retrieval only. Faithfulness and citation validity after synthesis
  need the multi-book path; they are not claimed here.
- The baseline is now the comparison point for the per-book path. The path must
  raise coverage and completeness, keep citation validity high, and not turn the
  near-misses into multi-book calls.

## Gate

No pipeline, retrieval or generation code changed in this measurement. The
existing gate still passes against the quota-aware baseline:

```text
uv run python scripts/run_eval.py --check --latest eval/results/20261106T060813Z.csv
gate: PASS
```

## Reproduce

```text
uv run python scripts/measure_aggregation.py --run-id 20261106T100459Z
```

## Raw output

```text
run: 20261106T100459Z
manifest: generator=qwen/qwen3-30b-a3b-instruct-2507 judge=deepseek/deepseek-v4.1-flash-1017 reranker=amazon.rerank-v1:0 pool=50 embedder=qwen3-embedding:0.6b chunking=500/75/200 top_k=5 rrf_k=60 quota=0
expected entities: 79
aggregation fixture
item     kind        books covered entities found citations valid
agg01    multi_book      7       2        7     2         5     5
agg02    multi_book      5       3        5     3         5     5
agg03    multi_book      7       4        7     4         5     5
agg04    multi_book      7       2        7     2         5     5
agg05    multi_book      7       3       17     5         5     4
agg06    multi_book      3       1        3     1         5     3
agg07    multi_book      3       1        3     1         5     5
agg08    multi_book      3       2        3     2         5     4
agg09    multi_book      7       4        7     4         5     5
agg10    multi_book      7       4        7     4         5     5
near01   near_miss       1       1        1     1         5     2
near02   near_miss       1       1        4     4         5     1
near03   near_miss       1       1        3     3         5     4
near04   near_miss       1       1        2     2         5     4
near05   near_miss       1       1        3     1         5     1

aggregate
  multi_book n=10 book_coverage=0.46 full_coverage=0.00 entity_completeness=0.45
  near_miss  n=5 entity_hit=1.00 entity_completeness=0.87 book_precision=0.48
  citation_validity=0.77
```
