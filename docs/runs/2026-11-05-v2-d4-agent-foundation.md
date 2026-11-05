# Run record: V2 D4 agent foundation regression check

- Date: 2026-11-05
- Run id: `20261105T093948Z`
- Ticket: #80 (V2 D4)
- Config: `pinned` (reranker on)
- Artifacts: `eval/results/baseline.csv` (committed, unchanged), `eval/results/20261105T093948Z.csv` (local, gitignored)
- Status: regression check after the D4 `ask()` refactor; no behavioural change
- Scope note: chat intents are answer, practice and feedback. The formal exam bank is a separate offline pipeline. Objective answers are scored deterministically; free-text answers are judged by a pinned LLM against stored rubrics and evidence; totals and bands are deterministic.

## Configuration

| Field | Value |
|---|---|
| Generator | `qwen/qwen3-30b-a3b-instruct-2507` |
| Judge | `deepseek/deepseek-v4.1-flash-1017` |
| Reranker | `amazon.rerank-v1:0`, pool 50 |
| Embedder | `local` / `qwen3-embedding:0.6b`, 1024 dims |
| Chunking | size 500, overlap 75, min size 200 |
| Retrieval | hybrid (dense + BM25, RRF), `k = 5`, `rrf_k = 60`, candidates 50 |
| Gold set | 60 items: 50 answerable, 10 unanswerable |
| Index text hash | `230bf8b2ab9af9d5` |
| Judged sample | 15, round-robin across the answerable slices |

## Retrieval

| Slice | n | Hit@5 | Recall@5 | MRR |
|---|---|---|---|---|
| overall | 50 | 0.76 | 0.66 | 0.50 |
| simple | 34 | 0.74 | 0.62 | 0.46 |
| multi_part | 8 | 0.62 | 0.50 | 0.40 |
| named_reference | 8 | 1.00 | 1.00 | 0.78 |

## Diagnostics

| Slice | n | dense | sparse | pool | lift | loss | near |
|---|---|---|---|---|---|---|---|
| overall | 50 | 0.77 | 0.68 | 0.81 | 0.86 | 0.14 | 0.06 |
| simple | 34 | 0.72 | 0.58 | 0.75 | 0.89 | 0.11 | 0.09 |
| multi_part | 8 | 0.77 | 0.77 | 0.90 | 0.62 | 0.38 | 0.00 |
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

## Gate

```
uv run python scripts/run_eval.py --check --latest eval/results/20261105T093948Z.csv
gate: PASS
```

The D4 change refactors `ask()` into `retrieval_floor`, `build_prompt` and
`ground_answer`; the non-streaming path still calls `llm.generate` with the same
system prompt and prompt text. Metrics are identical to the pinned D3 baseline
`20261104T220147Z`, which is the expected result for a plumbing change.

## Reading

- No regression in retrieval, abstention or generation.
- The refactor is covered by the existing `ask()` tests plus the new streaming
  test; the eval run confirms the pinned path is unchanged.
- D4 adds the agent surface (`/ask/stream`) but does not change the eval stack.
  The OpenRouter generator remains the pinned eval model; the Bedrock Llm is
  probed separately with `scripts/probe_bedrock.py`.
- The judge remains a different family from the generator.

## Reproduce

```
uv run python scripts/run_eval.py
uv run python scripts/run_eval.py --check --latest eval/results/20261105T093948Z.csv
```

## Raw summary

```text
gold: 60 items (50 answerable, 10 unanswerable)
config: pinned
generator: openrouter/qwen/qwen3-30b-a3b-instruct-2507
judge: openrouter/deepseek/deepseek-v4.1-flash-1017
reranker: bedrock

retrieval
  overall                n=50  Hit@5=0.76 Recall@5=0.66 MRR=0.50
  multi_part             n=8   Hit@5=0.62 Recall@5=0.50 MRR=0.40
  named_reference        n=8   Hit@5=1.00 Recall@5=1.00 MRR=0.78
  simple                 n=34  Hit@5=0.74 Recall@5=0.62 MRR=0.46

retrieval diagnostics
  overall                n=50  dense=0.77 sparse=0.68 pool=0.81 lift=0.86 loss=0.14 near=0.06
  multi_part             n=8   dense=0.77 sparse=0.77 pool=0.90 lift=0.62 loss=0.38 near=0.00
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

wrote /Users/tc/Documents/Github/owl-online/eval/results/20261105T093948Z.csv
```
