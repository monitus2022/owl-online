# Run record: aggregation fixture baseline

- Date: 2026-11-06
- Run id: `20261106T095329Z`
- Ticket: #96
- Config: `pinned`, reranker on, quota 0, retrieval only
- Artifacts: `eval/fixtures/aggregation.jsonl`, `scripts/measure_aggregation.py`

## Configuration

| Field | Value |
|---|---|
| Generator | not called |
| Judge | not called |
| Reranker | `amazon.rerank-v1:0`, pool 50, floor 0.0 |
| Embedder | `local` / `qwen3-embedding:0.6b`, 1024 dims |
| Chunking | size 500, overlap 75, min size 200 |
| Retrieval | hybrid, `k = 5`, `rrf_k = 60`, candidates 50 |
| Sub-query quota | 0, global fusion |
| Fixture | 15 items: 10 multi-book, 5 near-miss |
| Expected entities | 48 across the 10 multi-book items |

## Retrieval

| Item | Kind | Books | Covered | Entities | Found | Citations | Valid |
|---|---|---:|---:|---:|---:|---:|---:|
| agg01 | multi_book | 7 | 2 | 7 | 2 | 5 | 5 |
| agg02 | multi_book | 3 | 2 | 3 | 2 | 5 | 4 |
| agg03 | multi_book | 7 | 4 | 7 | 4 | 5 | 5 |
| agg04 | multi_book | 7 | 2 | 7 | 2 | 5 | 5 |
| agg05 | multi_book | 7 | 3 | 17 | 5 | 5 | 5 |
| agg06 | multi_book | 3 | 1 | 3 | 1 | 5 | 5 |
| agg07 | multi_book | 3 | 1 | 3 | 1 | 5 | 5 |
| agg08 | multi_book | 3 | 2 | 3 | 2 | 5 | 5 |
| agg09 | multi_book | 7 | 5 | 7 | 5 | 5 | 5 |
| agg10 | multi_book | 7 | 4 | 7 | 4 | 5 | 5 |
| near01 | near_miss | 1 | 1 | 1 | 1 | 5 | 3 |
| near02 | near_miss | 1 | 1 | 4 | 4 | 5 | 1 |
| near03 | near_miss | 1 | 1 | 3 | 2 | 5 | 5 |
| near04 | near_miss | 1 | 1 | 2 | 2 | 5 | 4 |
| near05 | near_miss | 1 | 1 | 3 | 1 | 5 | 5 |

## Aggregate

| Metric | Value |
|---|---|
| Multi-book items | 10 |
| Near-miss items | 5 |
| Book coverage | 0.49 |
| Full coverage | 0.00 |
| Entity completeness | 0.47 |
| Citation validity | 0.89 |
| Near-miss entity hit | 1.00 |
| Near-miss book precision | 0.72 |

## Reading

- One top-5 pass reaches only about half the expected books and half the
  expected entities. No multi-book item covers all of its books, which is the
  structural loss #96 describes.
- The per-item pattern is the expected one: a question whose evidence clusters
  in a few books (agg02, agg08) does better than one spread across seven
  (agg01, agg03, agg04).
- Citation validity is 0.89 overall, but near-miss precision is 0.72: the
  single-hop questions pull some chunks from other books. That is not a failure
  by itself, but it is the signal a router should not use a plural count alone.
- Every expected entity was checked against the corpus before the run. The
  fixture does not use free model memory.
- This is retrieval only. Faithfulness and citation validity after synthesis
  need the multi-book path; they are not claimed here.
- The baseline is now the comparison point for the per-book path. The path must
  raise coverage and completeness, keep citation validity high, and not turn the
  near-misses into multi-book calls.

## Reproduce

```text
uv run python scripts/measure_aggregation.py
```

## Raw output

```text
run: 20261106T095329Z
aggregation fixture
item     kind        books covered entities found citations valid
agg01    multi_book      7       2        7     2         5     5
agg02    multi_book      3       2        3     2         5     4
agg03    multi_book      7       4        7     4         5     5
agg04    multi_book      7       2        7     2         5     5
agg05    multi_book      7       3       17     5         5     5
agg06    multi_book      3       1        3     1         5     5
agg07    multi_book      3       1        3     1         5     5
agg08    multi_book      3       2        3     2         5     5
agg09    multi_book      7       5        7     5         5     5
agg10    multi_book      7       4        7     4         5     5
near01   near_miss       1       1        1     1         5     3
near02   near_miss       1       1        4     4         5     1
near03   near_miss       1       1        3     2         5     5
near04   near_miss       1       1        2     2         5     4
near05   near_miss       1       1        3     1         5     5

aggregate
  multi_book n=10 book_coverage=0.49 full_coverage=0.00 entity_completeness=0.47
  near_miss  n=5 entity_hit=1.00 book_precision=0.72
  citation_validity=0.89
```
