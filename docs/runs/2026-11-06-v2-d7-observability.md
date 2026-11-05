# Run record: V2 D7 tracing and injection guard

- Date: 2026-11-06
- Run id: `20261105T171800Z`
- Ticket: #82 (V2 D7)
- Config: `pinned` (reranker on)
- Artifacts: `eval/results/baseline.csv` (committed, unchanged), `eval/results/20261105T171800Z.csv` (local, gitignored)
- Status: regression check after the answer system prompt gained the untrusted-evidence sentence and the trace/injection code landed

## Configuration

| Field | Value |
|---|---|
| Generator | `qwen/qwen3-30b-a3b-instruct-2507` |
| Judge | `deepseek/deepseek-v4.1-flash-1017` |
| Reranker | `amazon.rerank-v1:0`, pool 50, floor 0.0 |
| Embedder | `local` / `qwen3-embedding:0.6b`, 1024 dims |
| Chunking | size 500, overlap 75, min size 200 |
| Retrieval | hybrid (dense + BM25, RRF), `k = 5`, `rrf_k = 60`, candidates 50 |
| Tokenizer | `regex-words` |
| Gold set | 61 items: 51 answerable, 10 unanswerable |
| Gold hash | `fe1d82f5c1c8` |
| Index text hash | `230bf8b2ab9af9d5` |
| Judged sample | 15, round-robin across the answerable slices |
| Trace | request spans, prompt hashes only; file optional |

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

```text
uv run python scripts/run_eval.py --check --latest eval/results/20261105T171800Z.csv
gate: PASS
```

## Reading

- Retrieval is unchanged; tracing and the injection filter are inert on the
  current corpus.
- One judge and one faithfulness verdict moved from partial/unfaithful to
  correct, almost certainly the system-prompt sentence rather than the tracer.
  It is a single item on a 15-item sample, so it is not claimed as an improvement.
- The injection guard is deterministic and bounded: it removes instruction-shaped
  spans from evidence and logs the affected chunk ids. It does not prove immunity
  to novel phrasings.
- The trace records decisions and inputs. Prompt text is hashed, not stored, so
  traces can be shipped without carrying excerpts.
- Model routing is not part of this run; it stays deferred with a recorded reason.

## Reproduce

```text
uv run python scripts/run_eval.py
uv run python scripts/run_eval.py --check --latest eval/results/20261105T171800Z.csv
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

wrote /Users/tc/Documents/Github/owl-online/eval/results/20261105T171800Z.csv
```
