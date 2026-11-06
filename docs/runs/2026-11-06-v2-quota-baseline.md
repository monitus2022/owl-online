# Run record: quota-aware baseline

- Date: 2026-11-06
- Run id: `20261106T060737Z`
- Ticket: #96
- Config: `pinned`, reranker on, quota 0
- Artifacts: `eval/results/baseline.csv` (re-pinned to this run), `eval/results/20261106T060737Z.csv` (local, gitignored)

## Configuration

| Field | Value |
|---|---|
| Generator | `qwen/qwen3-30b-a3b-instruct-2507` |
| Judge | `deepseek/deepseek-v4.1-flash-1017` |
| Reranker | `amazon.rerank-v1:0`, pool 50, floor 0.0 |
| Embedder | `local` / `qwen3-embedding:0.6b`, 1024 dims |
| Chunking | size 500, overlap 75, min size 200 |
| Retrieval | hybrid, `k = 5`, `rrf_k = 60`, candidates 50 |
| Sub-query quota | 0, global fusion, recorded in the CSV |
| Gold set | 61 items: 51 answerable, 10 unanswerable |
| Judged sample | 15, round-robin across the answerable slices |

## Retrieval

| Slice | n | Hit@5 | Recall@5 | MRR |
|---|---|---|---|---|
| overall | 51 | 0.76 | 0.66 | 0.50 |
| simple | 34 | 0.74 | 0.62 | 0.46 |
| multi_part | 9 | 0.67 | 0.52 | 0.41 |
| named_reference | 8 | 1.00 | 1.00 | 0.78 |

## Diagnostics

| Slice | n | dense | sparse | pool | lift | loss | near |
|---|---|---|---|---|---|---|---|
| overall | 51 | 0.78 | 0.68 | 0.81 | 0.87 | 0.13 | 0.06 |
| simple | 34 | 0.72 | 0.58 | 0.75 | 0.89 | 0.11 | 0.09 |
| multi_part | 9 | 0.80 | 0.76 | 0.91 | 0.67 | 0.33 | 0.00 |
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
| overall | 15 | 14 | 1 | 0.00 | 0.30 | 13/14 | 13 | 13 |
| simple | 5 | 5 | 0 | 0.00 | 0.30 | 5/5 | 5 | 5 |
| multi_part | 5 | 4 | 1 | 0.00 | 0.34 | 3/4 | 3 | 3 |
| named_reference | 5 | 5 | 0 | 0.00 | 0.28 | 5/5 | 5 | 5 |

Judge buckets: 13 correct, 1 partial, 0 wrong. The abstention is `m09`.
Novel entities: 0/14 answers.

## Gate

This run pins the baseline. The gate runs against a fresh default run in the next
record.

```text
uv run python scripts/run_eval.py --write-baseline
wrote baseline eval/results/baseline.csv
```

## Reading

- The baseline now records `subquery_quota` in every row. A quota-2 run is a
  different configuration and cannot pass `--check` against this baseline.
- Metrics match the follow-up gate run `20261106T060233Z`; the only change is the
  new CSV column and the baseline pin.
- The previous baseline was 12/14 on both faithfulness and judge correctness.
  This default path is 13/14, so the old baseline was pessimistic by one item.
- Multi-part pool recall is 0.91. The quota-2 run's 0.56 was measured through the
  shadowed trace and is not comparable.

## Reproduce

```text
uv run python scripts/run_eval.py --write-baseline
```

## Raw summary

```text
gold: 61 items (51 answerable, 10 unanswerable)
config: pinned
generator: openrouter/qwen/qwen3-30b-a3b-instruct-2507
judge: openrouter/deepseek/deepseek-v4.1-flash-1017
reranker: bedrock

retrieval
  overall                n=51  Hit@5=0.76 Recall@5=0.66 MRR=0.50
  multi_part             n=9   Hit@5=0.67 Recall@5=0.52 MRR=0.41
  named_reference        n=8   Hit@5=1.00 Recall@5=1.00 MRR=0.78
  simple                 n=34  Hit@5=0.74 Recall@5=0.62 MRR=0.46

retrieval diagnostics
  overall                n=51  dense=0.78 sparse=0.68 pool=0.81 lift=0.87 loss=0.13 near=0.06
  multi_part             n=9   dense=0.80 sparse=0.76 pool=0.91 lift=0.67 loss=0.33 near=0.00
  named_reference        n=8   dense=1.00 sparse=1.00 pool=1.00 lift=1.00 loss=0.00 near=0.00
  simple                 n=34  dense=0.72 sparse=0.58 pool=0.75 lift=0.89 loss=0.11 near=0.09

abstention
  overall                10/10 (1.00)
  near_miss_unanswerable 5/5 (1.00)
  off_topic              5/5 (1.00)

generation (judged sample)
  overall                n=15  answered=14  abstained=1   EM=0.00 F1=0.30 faithful=13/14 (0.93) judge correct=13 partial=1 wrong=0 grounded=13 judge_parse=0 faithful_parse=0
  multi_part             n=5   answered=4   abstained=1   EM=0.00 F1=0.34 faithful=3/4 (0.75) judge correct=3 partial=1 wrong=0 grounded=3 judge_parse=0 faithful_parse=0
  named_reference        n=5   answered=5   abstained=0   EM=0.00 F1=0.28 faithful=5/5 (1.00) judge correct=5 partial=0 wrong=0 grounded=5 judge_parse=0 faithful_parse=0
  simple                 n=5   answered=5   abstained=0   EM=0.00 F1=0.30 faithful=5/5 (1.00) judge correct=5 partial=0 wrong=0 grounded=5 judge_parse=0 faithful_parse=0

novel entities: 0/14 answers (0.00), tokens: none

wrote /Users/tc/Documents/Github/owl-online/eval/results/20261106T060737Z.csv
wrote baseline /Users/tc/Documents/Github/owl-online/eval/results/baseline.csv
```
