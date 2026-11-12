# Run record: #248 lesson and multi-turn RAG reproducibility

- Date: 2026-11-12
- Run id: `20261112T135138Z`
- Ticket: #248 (lesson and multi-turn evaluation foundation)
- Config: `rag-eval` (persona on, lesson mode on, lesson fallback on, temperature 0)
- Artifacts: `eval/results/rag-20261112T135138Z.json` (local, gitignored)
- Baseline: `eval/results/rag-baseline.json` (`20261112T135058Z`)

## Purpose

This run checks that the multi-turn eval is reproducible after `CachedLlm`
started caching streamed replies. The model calls were served from
`eval/.cache/rag`. Every metric is identical to the pinned baseline
`20261112T135058Z`.

## Metrics

| Area | Metric | Value |
|---|---|---:|
| Lesson | Items | 62 |
| Lesson | Answerable / unanswerable | 52 / 10 |
| Lesson | Selection precision@3 | 0.6405 |
| Lesson | Selection recall@3 | 0.9660 |
| Lesson | Scope accuracy | 0.9839 |
| Lesson | Citation recall | 0.9231 |
| Lesson | False refusal rate | 0.0000 |
| Lesson | Abstention accuracy | 1.0000 |
| Lesson | Citation validity / source hash | 1.0000 / 1.0000 |
| Lesson | Mixed / off-pack citation | 1.0000 / 1.0000 |
| Lesson | Judged / faithfulness | 30 / 0.0667 |
| Multi-turn | Conversations / turns | 17 / 36 |
| Multi-turn | Query accuracy | 0.9444 |
| Multi-turn | Mode accuracy | 0.8611 |
| Multi-turn | Citation accuracy | 0.5152 |
| Multi-turn | False refusal rate | 0.1515 |
| Multi-turn | Abstention accuracy | 1.0000 |
| Multi-turn | Referral target accuracy | 0.0000 |
| Multi-turn | Comparison accuracy | 0.0833 |
| Multi-turn | Context contamination | 0 |

## Reading

The second run reproduced the pinned metrics exactly. The multi-turn baseline
is now stable because the streamed answers are cached; an uncached stream made
the previous multi-turn numbers depend on the model sample. The lesson fixture
hash is `1daac0c1286e` and the multi-turn fixture hash is `1a86ba5c554d`.

## Reproduce

```
uv run python scripts/run_rag_eval.py
```

## Raw summary

```text
run_id: 20261112T135138Z
config: rag-eval
generator: openrouter/qwen/qwen3-30b-a3b-instruct-2507
judge: deepseek/deepseek-v4.1-flash-1017
lesson fixture: 1daac0c1286e (judged sample 30)
multi-turn fixture: 1a86ba5c554d

lesson
  total=62 answerable=52 unanswerable=10
  selection precision@3=0.6405 recall@3=0.9660
  scope accuracy=0.9839 citation recall=0.9231
  false refusal=0.0000 abstention accuracy=1.0000
  citation validity=1.0000 source hash=1.0000
  mixed n=1 scope=1.0000 citation=1.0000 false refusal=0.0000
  off-pack n=1 scope=1.0000 citation=1.0000 false refusal=0.0000
  judged=30 faithfulness=0.0667

multi-turn
  conversations=17 turns=36
  query accuracy=0.9444 mode accuracy=0.8611
  citation accuracy=0.5152 false refusal=0.1515
  abstention accuracy=1.0000
  referral target accuracy=0.0000 comparison accuracy=0.0833
  context contamination=0

errors: 0
wrote /Users/tc/Documents/Github/owl-online/eval/results/rag-20261112T135138Z.json
```
