# Run record: held-out single-hop k=7

- Date: 2026-11-06
- Run id: `20261106T121322Z`
- Ticket: #106
- Config: `aggregation_holdout`, single-hop, top-k 7, quota 0
- Artifacts: no result CSV (retrieval-only script); `eval/fixtures/aggregation_holdout.jsonl`

## Configuration

| Field | Value |
|---|---|
| Fixture | 20 items: 15 multi-book, 5 near-miss |
| Expected entities | 90 |
| Path | single-hop, one pass |
| Final top-k | 7 |
| Generator | `qwen/qwen3-30b-a3b-instruct-2507` (manifest; not called) |
| Judge | `deepseek/deepseek-v4.1-flash-1017` (manifest; not called) |
| Reranker | `amazon.rerank-v1:0`, pool 50, floor 0.0 |
| Embedder | `local` / `qwen3-embedding:0.6b`, 1024 dims |
| Chunking | size 500, overlap 75, min size 200 |
| Retrieval | hybrid, `k = 7`, `rrf_k = 60`, candidates 50 |
| Sub-query quota | 0, global fusion |

## Retrieval

| Metric | Value |
|---|---:|
| Book coverage | 0.69 |
| Full coverage | 0.13 |
| Entity completeness | 0.69 |
| Citation validity | 0.74 |
| Near-miss entity hit | 0.80 |
| Near-miss entity completeness | 0.75 |
| Near-miss book share | 0.43 |

## Router

| Metric | Value |
|---|---:|
| Precision | 1.00 |
| Recall | 0.93 |
| True positives | 14 |
| False positives | 0 |
| False negatives | 1 |

The one false negative is `hold15`, phrased as `How many books mention an
Animagus?` with no coverage cue. It is a designed negative: the held-out set
contains one multi-book question without a cue, and the router misses it by
construction. The 0.93 recall includes that item.

## Reading

- This is the equal-budget comparison for the routed held-out run.
- The held-out set was written before tuning and is not used to change the cues
  or the retrieval path. Failures are recorded, not fixed.
- `hnear03` (`What are the three Dursleys?`) returns no expected entity in the
  single-hop set, so near-miss entity hit is 0.80 rather than 1.00.
- Citation validity is 0.74. The routed run is lower because it returns a chunk
  from every book, including books outside the item's expected set.
- Near-miss book share is the fraction of near-miss chunks from the declared
  answer book. The entities may also appear in other books, so this is not a
  precision metric.

## Gate

No pipeline, generation or gate metric changed. The existing gate still passes:

```text
uv run python scripts/run_eval.py --check --latest eval/results/20261106T060813Z.csv
gate: PASS
```

## Reproduce

```text
uv run python scripts/measure_aggregation.py --fixture eval/fixtures/aggregation_holdout.jsonl --strategy single_hop --k 7 --run-id 20261106T121322Z
```

## Raw output

```text
run: 20261106T121322Z
strategy=single_hop per_book_k=1 manifest: generator=qwen/qwen3-30b-a3b-instruct-2507 judge=deepseek/deepseek-v4.1-flash-1017 reranker=amazon.rerank-v1:0 pool=50 embedder=qwen3-embedding:0.6b chunking=500/75/200 top_k=7 rrf_k=60 quota=0
router: precision=1.00 recall=0.93 tp=14 fp=0 fn=1
expected entities: 90
aggregation fixture
item     kind        books covered entities found citations valid
hold01   multi_book      4       4        4     4         7     6
hold02   multi_book      3       2        3     2         7     7
hold03   multi_book      3       3        3     3         7     7
hold04   multi_book      6       5        6     5         7     7
hold05   multi_book      6       4        6     4         7     5
hold06   multi_book      7       3        7     3         7     6
hold07   multi_book      5       4        5     4         7     7
hold08   multi_book      5       3        5     3         7     5
hold09   multi_book      7       4        7     4         7     5
hold10   multi_book      4       3        4     3         7     6
hold11   multi_book      4       3        4     3         7     5
hold12   multi_book      7       3        7     3         7     7
hold13   multi_book      5       4        5     4         7     7
hold14   multi_book      3       2        3     2         7     7
hold15   multi_book      3       1        3     1         7     1
hnear01  near_miss       1       1        3     3         7     5
hnear02  near_miss       1       1        4     4         7     2
hnear03  near_miss       1       0        3     0         7     0
hnear04  near_miss       1       1        4     4         7     2
hnear05  near_miss       1       1        4     3         7     6

aggregate
  multi_book n=15 book_coverage=0.69 full_coverage=0.13 entity_completeness=0.69
  near_miss  n=5 entity_hit=0.80 entity_completeness=0.75 book_share=0.43
  citation_validity=0.74
```
