# Run record: deterministic router on the aggregation fixture

- Date: 2026-11-06
- Run id: `20261106T102144Z`
- Ticket: #96
- Config: `aggregation`, pre-retrieval router, quota 0
- Artifacts: no result CSV (retrieval-only script); `eval/fixtures/aggregation.jsonl`, `scripts/measure_aggregation.py`

## Configuration

| Field | Value |
|---|---|
| Router | deterministic coverage cues, no model call |
| Generator | `qwen/qwen3-30b-a3b-instruct-2507` (manifest; not called) |
| Judge | `deepseek/deepseek-v4.1-flash-1017` (manifest; not called) |
| Reranker | `amazon.rerank-v1:0`, pool 50, floor 0.0 |
| Embedder | `local` / `qwen3-embedding:0.6b`, 1024 dims |
| Chunking | size 500, overlap 75, min size 200 |
| Retrieval | hybrid, `k = 5`, `rrf_k = 60`, candidates 50 |
| Sub-query quota | 0, global fusion |
| Fixture | 15 items: 10 multi-book, 5 near-miss |

## Router

| Metric | Value |
|---|---|
| Precision | 1.00 |
| Recall | 1.00 |
| True positives | 10 |
| False positives | 0 |
| False negatives | 0 |

The router labels a question `multi_book` when it sees a book-scoped coverage
phrase (`each book`, `each of the seven books`, `every book`,
`every one of the books`, `all seven books`, `across the books`,
`which books`, `in which books`, `list all seven books`, `for each book`,
`per book`) or at least two explicit book numbers. A plural count without a
coverage phrase stays `single_hop`, which is the near-miss case.

Known limits: singular `which book`, `for each other`, `each of the three tasks`,
`all seven Weasley children`, and `list all the spells in book 3` stay
single-hop. These are regression tests, not general-language guarantees.

The strategy and reason are emitted in the request trace as
`retrieval_strategy`, and `RetrievalTrace` carries `strategy`, `strategy_reason`
and `strategy_cues`.

## Retrieval

| Metric | Value |
|---|---:|
| Book coverage | 0.46 |
| Full coverage | 0.00 |
| Entity completeness | 0.45 |
| Citation validity | 0.77 |
| Near-miss entity hit | 1.00 |
| Near-miss entity completeness | 0.87 |
| Near-miss book precision | 0.48 |

The aggregation metrics are unchanged from the baseline. The router does not
change retrieval by itself; the per-book path is the next step.

## Reading

- The cue set separates all 10 multi-book questions from all 5 near-misses on
  this fixture.
- This is an in-sample result. The cues were chosen after seeing the fixture, so
  1.00 / 1.00 is not evidence of general precision. The next measurement should
  use questions written after the cues are frozen, or a held-out set.
- The router is pre-retrieval only. The post-retrieval coverage check from #96
  is not implemented yet.
- The router does not yet change the retrieval path. It labels the question and
  records the reason, but `ask()` still runs one top-5 pass.
- No pipeline, generation or gate metric changed. The existing eval gate still
  passes.

## Gate

```text
uv run python scripts/run_eval.py --check --latest eval/results/20261106T060813Z.csv
gate: PASS
```

## Reproduce

```text
uv run python scripts/measure_aggregation.py --run-id 20261106T102144Z
```

## Raw output

```text
run: 20261106T102144Z
manifest: generator=qwen/qwen3-30b-a3b-instruct-2507 judge=deepseek/deepseek-v4.1-flash-1017 reranker=amazon.rerank-v1:0 pool=50 embedder=qwen3-embedding:0.6b chunking=500/75/200 top_k=5 rrf_k=60 quota=0
router: precision=1.00 recall=1.00 tp=10 fp=0 fn=0
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
