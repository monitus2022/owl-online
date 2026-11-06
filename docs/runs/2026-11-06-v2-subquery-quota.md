# Run record: sub-query quota

- Date: 2026-11-06
- Run id: `20261105T204517Z`
- Ticket: #96
- Config: `pinned`, reranker on, `OWL_SUBQUERY_QUOTA=2` (experiment; default remains 0)
- Artifacts: `eval/results/baseline.csv` (unchanged), `eval/results/20261105T204517Z.csv` (local, gitignored)

## Configuration

| Field | Value |
|---|---|
| Generator | `qwen/qwen3-30b-a3b-instruct-2507` |
| Judge | `deepseek/deepseek-v4.1-flash-1017` |
| Reranker | `amazon.rerank-v1:0`, pool 50, floor 0.0 |
| Embedder | `local` / `qwen3-embedding:0.6b`, 1024 dims |
| Chunking | size 500, overlap 75, min size 200 |
| Retrieval | hybrid, `k = 5`, `rrf_k = 60`, candidates 50 |
| Sub-query quota | 2 per retrieval leg in this experiment; default 0 |
| Gold set | 61 items: 51 answerable, 10 unanswerable |
| Judged sample | 15, round-robin across the answerable slices |

## Retrieval

| Slice | n | Hit@5 | Recall@5 | MRR |
|---|---|---|---|---|
| overall | 51 | 0.78 | 0.66 | 0.50 |
| simple | 34 | 0.74 | 0.62 | 0.46 |
| multi_part | 9 | 0.78 | 0.52 | 0.41 |
| named_reference | 8 | 1.00 | 1.00 | 0.78 |

## Diagnostics

Invalid in this run: the quota loop shadowed the trace's `dense_ids` and
`sparse_ids`, so the table reported only the original-question leg. The bug is
fixed; re-run before using diagnostics.

## Abstention

| Slice | Refused | Rate |
|---|---|---|
| overall | 10/10 | 1.00 |
| near_miss_unanswerable | 5/5 | 1.00 |
| off_topic | 5/5 | 1.00 |

## Generation

| Slice | n | Answered | Abstained | EM | F1 | Faithful | Judge correct |
|---|---|---|---|---|---|---|---|
| overall | 15 | 14 | 1 | 0.00 | 0.29 | 14/14 | 14 |
| simple | 5 | 5 | 0 | 0.00 | 0.30 | 5/5 | 5 |
| multi_part | 5 | 4 | 1 | 0.00 | 0.30 | 4/4 | 4 |
| named_reference | 5 | 5 | 0 | 0.00 | 0.28 | 5/5 | 5 |

Judge buckets: 14 correct, 0 partial, 0 wrong. Grounded 14/14. 1 answer in the
sample abstained.

Novel entities: 0/14.

## Gate

```text
baseline: eval/results/baseline.csv (run 20261105T160001Z)
latest:   eval/results/20261105T204517Z.csv
uv run python scripts/run_eval.py --check --latest eval/results/20261105T204517Z.csv
gate: PASS
```

This gate passed while `subquery_quota` was still absent from the CSV manifest
fields. The run is an experiment, not the default configuration.

## Reading

- Multi-part Hit@5 moves from 0.667 to 0.778, overall from 0.765 to 0.784.
- The judged sample improves from the committed baseline's 12/14 to 14/14 on
  both judge correctness and faithfulness; F1 moves from 0.30 to 0.29, within
  noise. The D7 run at 13/14 was not the pinned baseline.
- The diagnostics table in this record is invalid: the quota loop shadowed the
  trace's `dense_ids`/`sparse_ids`, so it reported only the original-question leg.
  The bug is fixed; the diagnostics need a re-run before they are used.
- The change also fixes a real reranker edge: with a quota the pool can be
  smaller than `top_k`, and Bedrock rejects `numberOfResults` above the source
  count. `HybridRetriever` now caps the request at the pool size.
- Quota 2 remains a candidate behind `OWL_SUBQUERY_QUOTA`, default 0. The setting
  is not yet a CSV manifest field, so the gate cannot distinguish the two
  configurations; enabling it by default needs that field and a deliberate
  baseline repin.

## Reproduce

```text
OWL_SUBQUERY_QUOTA=2 uv run python scripts/run_eval.py
uv run python scripts/run_eval.py --check --latest eval/results/20261105T204517Z.csv
```

## Raw summary

The raw output is verbatim and still contains the invalid diagnostics block; see
Diagnostics above.

```text
gold: 61 items (51 answerable, 10 unanswerable)
config: pinned
generator: openrouter/qwen/qwen3-30b-a3b-instruct-2507
judge: openrouter/deepseek/deepseek-v4.1-flash-1017
reranker: bedrock

retrieval
  overall                n=51  Hit@5=0.78 Recall@5=0.66 MRR=0.50
  multi_part             n=9   Hit@5=0.78 Recall@5=0.52 MRR=0.41
  named_reference        n=8   Hit@5=1.00 Recall@5=1.00 MRR=0.78
  simple                 n=34  Hit@5=0.74 Recall@5=0.62 MRR=0.46

retrieval diagnostics
  overall                n=51  dense=0.77 sparse=0.65 pool=0.75 lift=0.93 loss=0.07 near=0.06
  multi_part             n=9   dense=0.74 sparse=0.59 pool=0.56 lift=1.00 loss=0.00 near=0.00
  named_reference        n=8   dense=1.00 sparse=1.00 pool=1.00 lift=1.00 loss=0.00 near=0.00
  simple                 n=34  dense=0.72 sparse=0.58 pool=0.75 lift=0.89 loss=0.11 near=0.09

abstention
  overall                10/10 (1.00)
  near_miss_unanswerable 5/5 (1.00)
  off_topic              5/5 (1.00)

generation (judged sample)
  overall                n=15  answered=14  abstained=1   EM=0.00 F1=0.29 faithful=14/14 (1.00) judge correct=14 partial=0 wrong=0 grounded=14 judge_parse=0 faithful_parse=0
  multi_part             n=5   answered=4   abstained=1   EM=0.00 F1=0.30 faithful=4/4 (1.00) judge correct=4 partial=0 wrong=0 grounded=4 judge_parse=0 faithful_parse=0
  named_reference        n=5   answered=5   abstained=0   EM=0.00 F1=0.28 faithful=5/5 (1.00) judge correct=5 partial=0 wrong=0 grounded=5 judge_parse=0 faithful_parse=0
  simple                 n=5   answered=5   abstained=0   EM=0.00 F1=0.30 faithful=5/5 (1.00) judge correct=5 partial=0 wrong=0 grounded=5 judge_parse=0 faithful_parse=0

novel entities: 0/14 answers (0.00), tokens: none

wrote /Users/tc/Documents/Github/owl-online/eval/results/20261105T204517Z.csv
```
