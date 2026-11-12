# Run record: #249 context-aware retrieval r2

- Date: 2026-11-13
- Run id: `20261112T173800Z`
- Ticket: #249 (context-aware retrieval for follow-up turns)
- Config: `rag-eval` (persona on, lesson mode on, lesson fallback on, temperature 0)
- Baseline: `20261112T135058Z` (`docs/runs/2026-11-12-248-rag-eval-foundation.md`)
- Artifacts: `eval/results/rag-20261112T173800Z.json` (local, gitignored)

## Configuration

| Field | Value |
|---|---|
| Generator | `openrouter/qwen/qwen3-30b-a3b-instruct-2507`, temperature 0.0 |
| Judge | `deepseek/deepseek-v4.1-flash-1017`, temperature 0.0 |
| Embedder | local `qwen3-embedding:0.6b` |
| Lesson fixture | `eval/rag/fixtures/lesson.jsonl`, SHA-256 `1daac0c1286e` |
| Multi-turn fixture | `eval/rag/fixtures/multiturn.jsonl`, SHA-256 `1a86ba5c554d` |
| Judged lesson sample | 30 |

## Before and after

| Metric | #248 baseline | #249 | Delta |
|---|---:|---:|---:|
| Multi-turn query accuracy | 0.9444 | 1.0000 | +0.0556 |
| Mode accuracy | 0.8611 | 0.8889 | +0.0278 |
| Citation accuracy | 0.5152 | 0.5455 | +0.0303 |
| False refusal rate | 0.1515 | 0.0909 | -0.0606 |
| Abstention accuracy | 1.0000 | 1.0000 | 0.0000 |
| Referral target accuracy | 0.0000 | 0.0000 | 0.0000 |
| Comparison accuracy | 0.0833 | 0.0833 | 0.0000 |
| Context contamination | 0 | 0 | 0 |

The lesson metrics are unchanged: selection precision 0.6405, recall 0.9660,
scope 0.9839, citation recall 0.9231, false refusal 0, abstention 1.0000,
citation validity 1.0000, faithfulness 2/30.

## Reading

This is the post-review run. The resolver edge cases (self-contained new topics, correction targets, entity carry-over and proper-name articles) were fixed after `20261112T172756Z`; the metrics are identical to that run.

- The two intended gaps are fixed. `how do I defeat one?` now retrieves
  `how do I defeat a Boggart?`, and `no, I meant a Dementor` retrieves
  `Tell me about a Dementor.` Multi-turn query accuracy is 36/36. The implicit
  rewrite is lowercased, and `query_ok` is case-insensitive in this slice;
  without casefold the metric is 35/36 (0.9722). The resolver change is the
  substantive fix; the casefold removes a casing-only mismatch.
- False refusal fell from 5/33 to 3/33. The remaining three are the
  cross-subject turns that abstain instead of referring; that is #253.
- Mode accuracy rose by one turn. The remaining four misses are the three
  cross-subject turns and the Charms comparison that still routes to `clarify`;
  the router fix is #259.
- Citation accuracy rose by one turn. Comparison accuracy is unchanged at 1/12:
  the model still answers one side of most comparisons. That is #252, not a
  memory rewrite.
- The lesson side did not move. Faithfulness remains 2/30 and is the next
  priority; #258 calibrates the judge and #251 tightens the prompt and claim
  binding.
- Context contamination remains 0: the off-topic turn still abstains and does
  not inherit the previous topic.
- The RAG gate reports `gate: PASS` against the #248 baseline.

## Reproduce

```
uv run python scripts/run_rag_eval.py
uv run python scripts/run_eval.py --rag --check
```

## Raw summary

```text
run_id: 20261112T173800Z
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
  query accuracy=1.0000 mode accuracy=0.8889
  citation accuracy=0.5455 false refusal=0.0909
  abstention accuracy=1.0000
  referral target accuracy=0.0000 comparison accuracy=0.0833
  context contamination=0

errors: 0
wrote /Users/tc/Documents/Github/owl-online/eval/results/rag-20261112T173800Z.json
```
