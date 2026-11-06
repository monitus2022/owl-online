# Run record: sub-query quota r2

- Date: 2026-11-06
- Run id: `20261106T060914Z`
- Ticket: #96
- Config: `pinned`, reranker on, `OWL_SUBQUERY_QUOTA=2`
- Artifacts: `eval/results/baseline.csv` (run `20261106T060737Z`), `eval/results/20261106T060914Z.csv` (local, gitignored)

## Configuration

| Field | Value |
|---|---|
| Generator | `qwen/qwen3-30b-a3b-instruct-2507` |
| Judge | `deepseek/deepseek-v4.1-flash-1017` |
| Reranker | `amazon.rerank-v1:0`, pool 50, floor 0.0 |
| Embedder | `local` / `qwen3-embedding:0.6b`, 1024 dims |
| Chunking | size 500, overlap 75, min size 200 |
| Retrieval | hybrid, `k = 5`, `rrf_k = 60`, candidates 50 |
| Sub-query quota | 2 per retrieval leg, recorded in the CSV |
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

| Slice | n | dense | sparse | pool | lift | loss | near |
|---|---|---|---|---|---|---|---|
| overall | 51 | 0.78 | 0.68 | 0.75 | 0.93 | 0.07 | 0.06 |
| simple | 34 | 0.72 | 0.58 | 0.75 | 0.89 | 0.11 | 0.09 |
| multi_part | 9 | 0.80 | 0.76 | 0.56 | 1.00 | 0.00 | 0.00 |
| named_reference | 8 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 |

## Abstention

| Slice | Refused | Rate |
|---|---|---|
| overall | 10/10 | 1.00 |
| near_miss_unanswerable | 5/5 | 1.00 |
| off_topic | 5/5 | 1.00 |

## Generation

| Slice | n | Answered | Abstained | EM | F1 | Faithful | Judge correct | Grounded |
|---|---|---|---|---|---|---|---|---|
| overall | 15 | 14 | 1 | 0.00 | 0.29 | 14/14 | 14 | 14 |
| simple | 5 | 5 | 0 | 0.00 | 0.30 | 5/5 | 5 | 5 |
| multi_part | 5 | 4 | 1 | 0.00 | 0.30 | 4/4 | 4 | 4 |
| named_reference | 5 | 5 | 0 | 0.00 | 0.28 | 5/5 | 5 | 5 |

Judge buckets: 14 correct, 0 partial, 0 wrong. The abstention is `m09`.
Novel entities: 0/14 answers.

## Gate

This is a different configuration from the baseline, so the gate refuses it by
design:

```text
baseline: eval/results/baseline.csv (run 20261106T060737Z, quota 0)
latest:   eval/results/20261106T060914Z.csv (quota 2)
uv run python scripts/run_eval.py --check --latest eval/results/20261106T060914Z.csv
baseline and latest run used different configurations (subquery_quota '0' -> '2');
rerun with --write-baseline after a deliberate change
exit=1
```

The quota remains opt-in; enabling it needs a deliberate baseline repin or a
separate quota-2 baseline.

## Reading

- Multi-part Hit@5 moves from 0.667 to 0.778, overall from 0.765 to 0.784. That
  is one item on n=9 and within the gate's one-item band.
- The judged sample moves from 13/14 to 14/14 on both judge correctness and
  faithfulness; F1 moves from 0.30 to 0.29, within noise.
- The diagnostics are now valid. Multi-part dense 0.80 and sparse 0.76 are the
  unions of all legs, matching the quota-0 baseline. The old record's 0.74 / 0.59
  was the shadowing bug.
- Multi-part pool recall falls from 0.91 to 0.56 because the quota narrows the
  pool to two candidates per leg. Rerank lift becomes 1.00: every candidate that
  reaches the reranker is kept. Selection, not rerank loss, is the trade.
- The manifest field now records the quota, so this run is distinguishable from
  the quota-0 baseline in the CSV.
- Quota 2 stays opt-in. The next comparison is quota 3 and per-sub-query rerank on
  a larger multi-part sample.

## Reproduce

```text
OWL_SUBQUERY_QUOTA=2 uv run python scripts/run_eval.py
uv run python scripts/run_eval.py --check --latest eval/results/20261106T060914Z.csv
```

## Raw summary

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
  overall                n=51  dense=0.78 sparse=0.68 pool=0.75 lift=0.93 loss=0.07 near=0.06
  multi_part             n=9   dense=0.80 sparse=0.76 pool=0.56 lift=1.00 loss=0.00 near=0.00
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

wrote /Users/tc/Documents/Github/owl-online/eval/results/20261106T060914Z.csv
```
