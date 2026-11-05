# Run record: V2 D6 retrieval guardrails

- Date: 2026-11-05
- Run ids: `20261105T154916Z` (baseline repin), `20261105T154940Z` (gate run)
- Ticket: #79 (V2 D6)
- Config: `pinned` (reranker on)
- Artifacts: `eval/results/baseline.csv` (repinned from `20261105T154916Z`), `eval/results/20261105T154940Z.csv` (local, gitignored)
- Status: superseded by `2026-11-06-v2-d6-retrieval-guardrails-r2.md`, which corrects the floor table and moves the known-hard item into the judged sample. Original status: gold set grew by one known-hard item, so the baseline was deliberately repinned; the gate run passes
- Scope note: the tokenizer experiment was rejected on evidence and the rerank floor stayed at zero. The shipped changes are the `/ask` deadline, the novel-entity signal, and the pinned tokenizer and floor.

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

| Slice | n | Answered | EM | F1 | Faithful | Judge correct | Grounded |
|---|---|---|---|---|---|---|---|
| overall | 15 | 15 | 0.00 | 0.32 | 12/15 | 12 | 12 |
| simple | 5 | 5 | 0.00 | 0.30 | 5/5 | 5 | 5 |
| multi_part | 5 | 5 | 0.00 | 0.40 | 2/5 | 2 | 2 |
| named_reference | 5 | 5 | 0.00 | 0.28 | 5/5 | 5 | 5 |

Novel entities: 0/15 answers. The Horcrux fabrication case (`m09`) is in the
gold set but was not selected for this judged sample.

## Experiments

Sparse tokenizer, same index and reranker, 61-item gold set:

| Tokenizer | Hit@5 | Recall@5 | MRR |
|---|---:|---:|---:|
| `regex-words` | 0.765 | 0.660 | 0.498 |
| Snowball stemming | 0.745 | 0.640 | 0.504 |
| Stopwords only | 0.706 | 0.591 | 0.467 |

Stemming raised sparse recall from 0.68 to 0.72 but lowered Hit@5 and recall, so
it was rejected. The full stopword-plus-stemmer variant measured 0.74 Hit@5 on
the 60-item set in an earlier run.

Rerank floor, top score per item (51 answerable, 10 unanswerable):

| Slice | min | p10 | median | p90 | max |
|---|---:|---:|---:|---:|---:|
| answerable | 0.003 | 0.059 | 0.477 | 0.887 | 0.991 |
| unanswerable | 0.000 | 0.000 | 0.000 | 0.352 | 0.352 |

| Floor | False abstention | Unanswerable abstention |
|---:|---:|---:|
| 0.0 | 0/51 | 0/10 |
| 0.1 | 10/51 | 9/10 |
| 0.4 | 22/51 | 10/10 |

The distributions overlap. Unanswerable items mostly abstain through empty
retrieval already, and the remaining item costs 22 answerable items. The floor
is pinned at `0.0`.

## Gate

```text
uv run python scripts/run_eval.py --check --latest eval/results/20261105T154940Z.csv
gate: PASS
```

## Reading

- Retrieval is unchanged against the previous baseline: 0.76 overall. The new
  multi-part item did not depress the slice; multi-part moved from 0.62 to 0.67
  on one extra item.
- The tokenizer change is a real negative result. Sparse recall improved but
  final ranking lost ground, which is the only metric that matters.
- The floor cannot separate the slices. Pinning zero is the evidence-based
  choice, not a default left untouched.
- D6 ships the deadline, the novel-entity signal, and the pins. It does not
  improve answer quality, and it says so.
- The gold-set change means runs before this record are not directly comparable:
  `gold_hash` changed and the baseline was repinned on purpose.

## Reproduce

```text
uv run python scripts/run_eval.py
uv run python scripts/run_eval.py --check --latest eval/results/20261105T154940Z.csv
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
  overall                n=15  answered=15  abstained=0   EM=0.00 F1=0.32 faithful=12/15 (0.80) judge correct=12 partial=2 wrong=1 grounded=12 judge_parse=0 faithful_parse=0
  multi_part             n=5   answered=5   abstained=0   EM=0.00 F1=0.40 faithful=2/5 (0.40) judge correct=2 partial=2 wrong=1 grounded=2 judge_parse=0 faithful_parse=0
  named_reference        n=5   answered=5   abstained=0   EM=0.00 F1=0.28 faithful=5/5 (1.00) judge correct=5 partial=0 wrong=0 grounded=5 judge_parse=0 faithful_parse=0
  simple                 n=5   answered=5   abstained=0   EM=0.00 F1=0.30 faithful=5/5 (1.00) judge correct=5 partial=0 wrong=0 grounded=5 judge_parse=0 faithful_parse=0

novel entities: 0/15 answers (0.00), tokens: none

wrote /Users/tc/Documents/Github/owl-online/eval/results/20261105T154940Z.csv
```
