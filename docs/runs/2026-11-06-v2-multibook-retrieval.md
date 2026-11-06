# Run record: per-book retrieval prototype

- Date: 2026-11-06
- Run id: `20261106T105819Z`
- Ticket: #96
- Config: `aggregation`, routed prototype, per-book k 1, top-k 7, quota 0
- Artifacts: no result CSV (retrieval-only script); `app/pipeline/retrieve/multibook.py`, `eval/fixtures/aggregation.jsonl`

## Configuration

| Field | Value |
|---|---|
| Router | deterministic coverage cues, no model call |
| Path | multi-book questions use per-book retrieval; near-misses use single-hop |
| Map calls | at most 7, one per book |
| Fan-out | 4 in flight |
| Per-book k | 1 |
| Final top-k | 7, equal to the single-hop comparison |
| Generator | `qwen/qwen3-30b-a3b-instruct-2507` (manifest; not called) |
| Judge | `deepseek/deepseek-v4.1-flash-1017` (manifest; not called) |
| Reranker | `amazon.rerank-v1:0`, pool 50, floor 0.0 |
| Embedder | `local` / `qwen3-embedding:0.6b`, 1024 dims |
| Chunking | size 500, overlap 75, min size 200 |
| Retrieval | hybrid, `k = 7`, `rrf_k = 60`, candidates 50 |
| Sub-query quota | 0, global fusion |
| Fixture | 15 items: 10 multi-book, 5 near-miss |

## Retrieval

| Metric | Single pass, k=7 | Routed per-book, k=7 |
|---|---:|---:|
| Book coverage | 0.58 | 0.79 |
| Full coverage | 0.00 | 0.40 |
| Entity completeness | 0.56 | 0.76 |
| Citation validity | 0.71 | 0.56 |
| Near-miss entity hit | 1.00 | 1.00 |
| Near-miss entity completeness | 0.87 | 0.87 |
| Near-miss book precision | 0.40 | 0.40 |

## Router

| Metric | Value |
|---|---:|
| Precision | 1.00 |
| Recall | 1.00 |
| True positives | 10 |
| False positives | 0 |
| False negatives | 0 |

The router sends the 10 multi-book items to the per-book path and the 5
near-misses to the single-hop path, which is why near-miss metrics are unchanged.
The 1.00 / 1.00 is in-sample: the cues were chosen after seeing the fixture.

## Reading

- Per-book retrieval raises book coverage from 0.58 to 0.79 and entity
  completeness from 0.56 to 0.76 at the same top-k 7 budget. Full coverage rises
  from 0.00 to 0.40: four multi-book items now cover every expected book.
- The filter is authoritative: a question that names a book title, such as
  `Order of the Phoenix`, cannot redirect a per-book pass to that title's book.
  Before the fix, agg06 collapsed to one book and reported 1/3 coverage; it now
  covers 3/3.
- Citation validity falls from 0.71 to 0.56 because the path returns seven
  chunks and each must still contain an expected entity to count. The raw
  coverage gain is real, but the evidence set is wider and needs extraction and
  deduplication before synthesis.
- The remaining gap is per-book selection. agg08 still covers only one of its
  three books, and agg05 covers four of seven. A single top chunk per book is not
  always the chunk with the expected entity.
- This is a retrieval-only prototype. `ask()` is not wired to it yet, so chat
  behavior is unchanged.
- The next step is per-book extraction with citations, merge and dedupe, one
  synthesis and a coverage statement. The seven-map cap and fan-out 4 are in
  place.

## Gate

No pipeline, generation or gate metric changed. The existing gate still passes:

```text
uv run python scripts/run_eval.py --check --latest eval/results/20261106T060813Z.csv
gate: PASS
```

## Reproduce

```text
uv run python scripts/measure_aggregation.py --strategy routed --k 7 --run-id 20261106T105819Z
```

## Raw output

```text
run: 20261106T105819Z
strategy=routed per_book_k=1 manifest: generator=qwen/qwen3-30b-a3b-instruct-2507 judge=deepseek/deepseek-v4.1-flash-1017 reranker=amazon.rerank-v1:0 pool=50 embedder=qwen3-embedding:0.6b chunking=500/75/200 top_k=7 rrf_k=60 quota=0
router: precision=1.00 recall=1.00 tp=10 fp=0 fn=0
expected entities: 79
aggregation fixture
item     kind        books covered entities found citations valid
agg01    multi_book      7       4        7     4         7     4
agg02    multi_book      5       5        5     5         7     5
agg03    multi_book      7       6        7     6         7     6
agg04    multi_book      7       6        7     6         7     6
agg05    multi_book      7       4       17     5         7     4
agg06    multi_book      3       3        3     3         7     3
agg07    multi_book      3       2        3     2         7     2
agg08    multi_book      3       1        3     1         7     1
agg09    multi_book      7       7        7     7         7     7
agg10    multi_book      7       7        7     7         7     7
near01   near_miss       1       1        1     1         7     2
near02   near_miss       1       1        4     4         7     1
near03   near_miss       1       1        3     3         7     4
near04   near_miss       1       1        2     2         7     6
near05   near_miss       1       1        3     1         7     1

aggregate
  multi_book n=10 book_coverage=0.79 full_coverage=0.40 entity_completeness=0.76
  near_miss  n=5 entity_hit=1.00 entity_completeness=0.87 book_precision=0.40
  citation_validity=0.56
```
