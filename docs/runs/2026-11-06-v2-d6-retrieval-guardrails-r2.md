# Run record: V2 D6 retrieval guardrails r2

- Date: 2026-11-06
- Run ids: `20261105T160001Z` (baseline repin), `20261105T160032Z` (gate run)
- Ticket: #79 (V2 D6)
- Config: `pinned` (reranker on)
- Artifacts: `eval/results/baseline.csv` (repinned from `20261105T160001Z`), `eval/results/20261105T160032Z.csv` (local, gitignored)
- Status: supersedes the `2026-11-05-v2-d6-retrieval-guardrails.md` record. The known-hard fabrication case was moved into the judged sample, so the sample and baseline changed.
- Scope note: tokenizer and floor were measured and rejected; the deadline and novel-entity signal ship.

## Configuration

| Field | Value |
|---|---|
| Generator | `qwen/qwen3-30b-a3b-instruct-2507` |
| Judge | `deepseek/deepseek-v4.1-flash-1017` |
| Reranker | `amazon.rerank-v1:0`, pool 50, floor 0.0 |
| Embedder | `local` / `qwen3-embedding:0.6b`, 1024 dims |
| Chunking | size 500, overlap 75, min size 200 |
| Retrieval | hybrid (dense + BM25, RRF), `k = 5`, `rrf_k = 60`, candidates 50 |
| Tokenizer | `regex-words` (pinned; Snowball rejected) |
| Gold set | 61 items: 51 answerable, 10 unanswerable |
| Gold hash | `fe1d82f5c1c8` |
| Index text hash | `230bf8b2ab9af9d5` |
| Judged sample | 15, round-robin across the answerable slices |
| Deadline | `OWL_ASK_TIMEOUT_S = 30` for `/ask` |
| Retry budget | `[generation].retry_budget = 1` |

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
| overall | 15 | 14 | 1 | 0.00 | 0.30 | 12/14 | 12 | 12 |
| simple | 5 | 5 | 0 | 0.00 | 0.30 | 5/5 | 5 | 5 |
| multi_part | 5 | 4 | 1 | 0.00 | 0.34 | 2/4 | 2 | 2 |
| named_reference | 5 | 5 | 0 | 0.00 | 0.28 | 5/5 | 5 | 5 |

Judge buckets: 12 correct, 1 partial, 1 wrong. The abstention is `m09`, the
seven-Horcruxes case.

Novel entities: 0/14 answers. The Horcrux answer abstained, so the Herbrand
fabrication did not occur in this sample and the signal had no true positive to
report. The unit test covers the invented name.

## Experiments

Sparse tokenizer, same index and reranker, 61-item gold set:

| Tokenizer | Hit@5 | Recall@5 | MRR |
|---|---:|---:|---:|
| `regex-words` | 39/51 = 0.765 | 0.660 | 0.498 |
| Snowball stemming | 38/51 = 0.745 | 0.640 | 0.504 |
| Stopwords only | 36/51 = 0.706 | 0.591 | 0.467 |

The difference between the top two rows is one item, inside the 0.05 gate band,
and MRR rose slightly. Stemming is rejected because it adds a dependency for no
measured gain, not because of a large regression.

Rerank floor, top score per item (51 answerable, 10 unanswerable):

| Slice | n | empty retrieval | min | p10 | median | p90 | max |
|---|---:|---:|---:|---:|---:|---:|---:|
| answerable | 51 | 0 | 0.003 | 0.059 | 0.477 | 0.887 | 0.991 |
| unanswerable | 10 | 2 | 0.000 | 0.000 | 0.000 | 0.352 | 0.352 |

| Floor | Floor-driven false abstention | Floor-driven abstention |
|---:|---:|---:|
| 0.0 | 0/51 | 0/10 |
| 0.1 | 10/51 | 7/10 |
| 0.4 | 22/51 | 8/10 |

Two unanswerable items return no chunks and abstain before any score comparison;
they are not in the floor columns. Catching the other eight would cost 22 of 51
answerable items, so the floor is pinned at `0.0`.

## Gate

```text
uv run python scripts/run_eval.py --check --latest eval/results/20261105T160032Z.csv
baseline: eval/results/baseline.csv
latest:   eval/results/20261105T160032Z.csv
gate: PASS
```

## Reading

- Retrieval is unchanged: 0.76 overall, multi-part 0.67 on nine items.
- The judged sample changed because `m09` now sorts into the first five
  multi-part items. The model abstained on it instead of inventing a name, so
  faithfulness reads 12/14 rather than 12/15 and F1 reads 0.30.
- The fabrication signal is unexercised in this sample; its value is proven at
  the unit level and by the Horcrux case being structurally sampleable now.
- Stemming and a positive rerank floor are both rejected on measurement. The
  shipped D6 value is the deadline, the signal and the pins.
- The gold-set order change means earlier D6 runs are history, not comparison
  points; the baseline was repinned deliberately.

## Reproduce

```text
uv run python scripts/run_eval.py
uv run python scripts/run_eval.py --check --latest eval/results/20261105T160032Z.csv
uv run python scripts/measure_rerank_floor.py
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
  overall                n=15  answered=14  abstained=1   EM=0.00 F1=0.30 faithful=12/14 (0.86) judge correct=12 partial=1 wrong=1 grounded=12 judge_parse=0 faithful_parse=0
  multi_part             n=5   answered=4   abstained=1   EM=0.00 F1=0.34 faithful=2/4 (0.50) judge correct=2 partial=1 wrong=1 grounded=2 judge_parse=0 faithful_parse=0
  named_reference        n=5   answered=5   abstained=0   EM=0.00 F1=0.28 faithful=5/5 (1.00) judge correct=5 partial=0 wrong=0 grounded=5 judge_parse=0 faithful_parse=0
  simple                 n=5   answered=5   abstained=0   EM=0.00 F1=0.30 faithful=5/5 (1.00) judge correct=5 partial=0 wrong=0 grounded=5 judge_parse=0 faithful_parse=0

novel entities: 0/14 answers (0.00), tokens: none

wrote /Users/tc/Documents/Github/owl-online/eval/results/20261105T160032Z.csv
```
