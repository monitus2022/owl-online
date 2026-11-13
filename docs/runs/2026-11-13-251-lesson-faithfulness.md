# Run record: #251 lesson grounding first slice

- Date: 2026-11-13
- Run id: `20261113T073645Z`
- Ticket: #251 (claim-level citation binding for chat and lesson)
- Config: `rag-eval` (persona on, lesson mode on, lesson fallback on, temperature 0)
- Baseline: `20261112T135058Z` (#248), with #249 already merged
- Artifacts: `eval/results/rag-20261113T073645Z.json` (local, gitignored)

## Configuration

| Field | Value |
|---|---|
| Generator | `openrouter/qwen/qwen3-30b-a3b-instruct-2507`, temperature 0.0 |
| Judge | `deepseek/deepseek-v4.1-flash-1017`, temperature 0.0 |
| Lesson fixture | `eval/rag/fixtures/lesson.jsonl`, SHA-256 `1daac0c1286e` |
| Multi-turn fixture | `eval/rag/fixtures/multiturn.jsonl`, SHA-256 `1a86ba5c554d` |
| Judged lesson sample | 30 |

## Before and after

| Metric | #248 baseline | #251 |
|---|---:|---:|
| Lesson faithfulness | 2/30 (0.0667) | 4/30 (0.1333) |
| Lesson citation recall | 0.9231 | 0.9615 |
| Lesson scope accuracy | 0.9839 | 0.9839 |
| Lesson false refusal | 0.0000 | 0.0000 |
| Lesson mean words | n/a | 196 |
| Lesson max words | n/a | 291 |
| Lesson over 220 words | n/a | 9 |
| Multi-turn query accuracy | 0.9444 | 1.0000 |
| Multi-turn mode accuracy | 0.8611 | 0.8889 |
| Multi-turn citation accuracy | 0.5152 | 0.5758 |
| Multi-turn false refusal | 0.1515 | 0.0909 |
| Multi-turn comparison accuracy | 0.0833 | 0.1667 |
| Multi-turn referral accuracy | 0.0000 | 0.0000 |
| Context contamination | 0 | 0 |

The multi-turn improvement includes #249's implicit-referent work. Against
#249 alone, citation accuracy moved 0.5455 to 0.5758 and comparison accuracy
0.0833 to 0.1667.

## Reading

- The lesson prompt now states an evidence rule: every factual paragraph cites
  the note it comes from; an unsupported example, caution or check is omitted.
  The prompt asks for under 220 words.
- The selector now expands each matched concept to its full reviewed material
  group, capped at five materials. That gives the model every note for the
  concept rather than one note and two neighbours.
- A substantive paragraph without a citation triggers one stricter retry. It
  does not abstain on placement alone. That distinction matters: the first
  attempt often puts citations only at the end, and a hard paragraph gate
  produced two false refusals (`lesson-dada-02` and `lesson-dada-04`) without
  improving faithfulness.
- Faithfulness moved from 2/30 to 4/30. The judge and the lesson calibration
  are owner-adopted, so this is a real movement, not a prompt-specific judge
  change. It is still far below the product bar: the model continues to
  elaborate beyond the notes in most answers.
- Citation recall rose from 0.9231 to 0.9615. Scope and false refusal returned
  to the #248 levels.
- Multi-turn comparison accuracy doubled to 2/12 because the full concept group
  gives the model both sides more often. It is still weak; #252 is the next
  comparison-specific step.
- Length is reported but not gated: mean 196 words, 9 of 52 answers over 220.
  The prompt cap is advisory; a harder cap or a shorter teaching shape is a
  follow-up.
- The remaining faithfulness gap is generation, not retrieval. The evidence is
  present and cited more often; the model still adds claims. The next slice
  should test sentence-level support or a more extractive lesson mode, not
  another top-k change.

## Reproduce

```
uv run python scripts/run_rag_eval.py
uv run python scripts/run_eval.py --rag --check
```

## Raw summary

```text
run_id: 20261113T073645Z
config: rag-eval
generator: openrouter/qwen/qwen3-30b-a3b-instruct-2507
judge: deepseek/deepseek-v4.1-flash-1017
lesson fixture: 1daac0c1286e (judged sample 30)
multi-turn fixture: 1a86ba5c554d

lesson
  total=62 answerable=52 unanswerable=10
  selection precision@3=0.6405 recall@3=0.9660
  scope accuracy=0.9839 citation recall=0.9615
  false refusal=0.0000 abstention accuracy=1.0000
  citation validity=1.0000 source hash=1.0000
  mixed n=1 scope=1.0000 citation=1.0000 false refusal=0.0000
  off-pack n=1 scope=1.0000 citation=1.0000 false refusal=0.0000
  mean words=196 max=291 over-220=9
  judged=30 faithfulness=0.1333

multi-turn
  conversations=17 turns=36
  query accuracy=1.0000 mode accuracy=0.8889
  citation accuracy=0.5758 false refusal=0.0909
  abstention accuracy=1.0000
  referral target accuracy=0.0000 comparison accuracy=0.1667
  context contamination=0

errors: 0
wrote /Users/tc/Documents/Github/owl-online/eval/results/rag-20261113T073645Z.json
```
