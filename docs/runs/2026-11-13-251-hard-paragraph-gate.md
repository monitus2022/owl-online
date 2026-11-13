# Run record: #251 hard paragraph gate, rejected

- Date: 2026-11-13
- Run id: `20261113T072932Z`
- Ticket: #251 (claim-level citation binding for chat and lesson)
- Config: `rag-eval` (persona on, lesson mode on, lesson fallback on, temperature 0)
- Variant: evidence rule, full concept group, paragraph gate that abstains
- Baseline: `20261112T135058Z` (#248), with #249 already merged
- Artifacts: `eval/results/rag-20261113T072932Z.json` (local, gitignored)

## Configuration

| Field | Value |
|---|---|
| Generator | `openrouter/qwen/qwen3-30b-a3b-instruct-2507`, temperature 0.0 |
| Judge | `deepseek/deepseek-v4.1-flash-1017`, temperature 0.0 |
| Lesson fixture | `eval/rag/fixtures/lesson.jsonl`, SHA-256 `1daac0c1286e` |
| Multi-turn fixture | `eval/rag/fixtures/multiturn.jsonl`, SHA-256 `1a86ba5c554d` |
| Judged lesson sample | 30 of 50 answered |
| Paragraph gate | hard: a draft with an uncited factual paragraph abstains |

This variant differs from the shipped slice in the paragraph gate: the draft
was converted to an abstention instead of getting a paragraph-specific retry and
being served. It also predates the best-draft fallback, the round-robin
expansion, the grounded-answer paragraph check and the off-pack gold-set
correction, so it is a rejected experiment, not a configuration to reproduce
from `main`.

## Result

| Metric | #248/#249 | Hard gate |
|---|---:|---:|
| Lesson faithfulness | 2/30 (0.0667) | 5/30 (0.1667) |
| Lesson citation recall | 0.9231 | 0.9231 |
| Lesson scope accuracy | 0.9839 | 0.9516 |
| Lesson false refusal | 0.0000 | 0.0385 (2/52) |
| Lesson mean words | n/a | 197 |
| Lesson max words | n/a | 291 |
| Lesson over 220 words | n/a | 9 |
| Multi-turn query accuracy | 1.0000 | 1.0000 |
| Multi-turn mode accuracy | 0.8889 | 0.8889 |
| Multi-turn citation accuracy | 0.5455 | 0.5455 |
| Multi-turn false refusal | 0.0909 | 0.1212 |
| Multi-turn comparison accuracy | 0.0833 | 0.1667 |

## Reading

- The gate refused two answerable items, `lesson-dada-02` and
  `lesson-dada-04`. Scope accuracy 0.9516 is 59/62: those two refusals plus the
  pre-existing `lesson-charms-07` miss, which is already `mixed` in the #248
  baseline and is not a gate effect. Both refusals came from citation placement:
  the model put the note ids at the end of the answer, not at the end of each
  paragraph. The notes were present and correct.
- The faithfulness number is 5/30, one item above the shipped 4/30, but the
  judged sample is not comparable. The sampler draws the judged 30 from
  answered results only, so this run judged 30 of 50 answers while the shipped
  run judged 30 of 52. A two-item difference at n=30 is inside noise.
- The false refusals and the scope miss are a product regression. A student who
  asks about the Disarming Charm must not get the abstention line because the
  model cited one paragraph late.
- Rejected. The shipped slice keeps the retry and serves the cited answer.

## Reproduce

The variant is not on `main`. It was produced by making `paragraphs_ok` part of
`has_required` and abstaining with `abstain_reason="uncited"` when it failed,
then running:

```
uv run python scripts/run_rag_eval.py
```

## Raw summary

The printed summary uses the label `over-220`, which was the report label at the
time of the run; it is now `at-or-over-limit`.

```text
run_id: 20261113T072932Z
config: rag-eval
generator: openrouter/qwen/qwen3-30b-a3b-instruct-2507
judge: deepseek/deepseek-v4.1-flash-1017
lesson fixture: 1daac0c1286e (judged sample 30)
multi-turn fixture: 1a86ba5c554d

lesson
  total=62 answerable=52 unanswerable=10
  selection precision@3=0.6405 recall@3=0.9660
  scope accuracy=0.9516 citation recall=0.9231
  false refusal=0.0385 abstention accuracy=1.0000
  citation validity=1.0000 source hash=1.0000
  mixed n=1 scope=1.0000 citation=1.0000 false refusal=0.0000
  off-pack n=1 scope=1.0000 citation=1.0000 false refusal=0.0000
  mean words=197 max=291 over-220=9
  judged=30 faithfulness=0.1667

multi-turn
  conversations=17 turns=36
  query accuracy=1.0000 mode accuracy=0.8889
  citation accuracy=0.5455 false refusal=0.1212
  abstention accuracy=1.0000
  referral target accuracy=0.0000 comparison accuracy=0.1667
  context contamination=0

errors: 0
wrote /Users/tc/Documents/Github/owl-online/eval/results/rag-20261113T072932Z.json
```
