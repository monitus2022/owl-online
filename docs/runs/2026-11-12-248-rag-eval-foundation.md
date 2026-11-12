# Run record: #248 lesson and multi-turn RAG baseline

- Date: 2026-11-12
- Run id: `20261112T122937Z`
- Ticket: #248 (lesson and multi-turn evaluation foundation)
- Config: `rag-eval` (persona on, lesson mode on, lesson fallback on, temperature 0)
- Artifacts: `eval/results/rag-20261112T122937Z.json` (local, gitignored), `eval/results/rag-baseline.json` (committed)

## Configuration

| Field | Value |
|---|---|
| Generator | `openrouter/qwen/qwen3-30b-a3b-instruct-2507`, temperature 0.0 |
| Judge | `deepseek/deepseek-v4.1-flash-1017`, temperature 0.0 |
| Embedder | local `qwen3-embedding:0.6b` |
| Lesson selection | top-k 3, cosine floor 0.58, lexical extras on |
| Lesson fallback | on |
| Lesson fixture | `eval/rag/fixtures/lesson.jsonl`, 62 items, SHA-256 `703b128ad6c6` |
| Multi-turn fixture | `eval/rag/fixtures/multiturn.jsonl`, 17 conversations / 36 turns, SHA-256 `1a86ba5c554d` |
| Judged lesson sample | 30, round-robin across slices |
| Cache | `eval/.cache/rag` |

The fixtures store concept titles, material ids and source-ref structure only.
No pack prose or corpus text is committed. The generator and judge temperature
are pinned at 0; a baseline with a different setting is refused unless
`--force-baseline` is passed deliberately.

## Lesson

| Metric | Value |
|---|---:|
| Items | 62 |
| Answerable | 52 |
| Unanswerable | 10 |
| Selection precision@3 | 0.6405 |
| Selection recall@3 | 0.9660 |
| Scope accuracy | 0.9839 |
| Citation recall | 0.8942 |
| False refusal rate | 0.0000 |
| Abstention accuracy | 1.0000 |
| Citation validity | 1.0000 |
| Source hash validity | 1.0000 |
| Judged | 30 |
| Faithfulness | 0.0667 |

## Multi-turn

| Metric | Value |
|---|---:|
| Conversations | 17 |
| Turns | 36 |
| Retrieval-query accuracy | 0.9444 |
| Mode accuracy | 0.8611 |
| Citation accuracy | 0.5455 |
| False refusal rate | 0.0909 |
| Abstention accuracy | 1.0000 |
| Referral target accuracy | 0.0000 |
| Comparison accuracy | 0.0833 |
| Context contamination | 0 |
| Errors | 0 |

## Reading

- The lesson contract is structurally sound but not claim-safe. Scope accuracy
  is 61/62, citation validity and source hashes are 1.0000, false refusals are
  0/52, and unanswerable abstention is 10/10.
- Faithfulness is the headline. Only 2 of 30 judged lesson answers are
  supported by the evidence shown: `lesson-dada-13` (off-pack) and
  `lesson-transfiguration-05` (paraphrase). The other 28 are fluent
  elaborations beyond the selected notes. Citation validity is 1.0000 at the
  same time, so a valid citation is not evidence that the claim is supported.
  This is the case for #251.
- Selection recall is 0.9660, but precision is 0.6405. The selector finds the
  intended concept and spends the third slot on a near neighbour. Selection is
  not the main bottleneck.
- One scope miss remains. `lesson-charms-07` (Wand-Extinguishing against
  Summoning) selected the generic charm definition, Nox and Wands, then fell to
  `mixed` with only the Nox material cited.
- The mixed case `lesson-dada-12` (Boggart against the Triwizard Tournament)
  answered with `scope=mixed` and cited a material plus corpus chunks, but the
  corpus chunks were not the expected Triwizard chunk and the answer is judged
  unfaithful. The off-pack case `lesson-dada-13` answered with
  `scope=off_pack` and is judged faithful, but cited `b1-c15-0018` rather than
  the expected `b1-c11-0042`. Both are evidence-target findings for the next
  retrieval and grounding tickets.
- Multi-turn query accuracy is 34/36. The two misses are the intended gaps:
  `how do I defeat one?` is not rewritten to include the Boggart, and
  `no, I meant a Dementor` is not rewritten to the correction. These are the
  target behaviours for #249.
- Mode accuracy is 31/36. Three misses are the cross-subject referral cases
  (the contract is #253 and is not implemented yet), one is the implicit
  follow-up abstaining instead of staying lesson, and one is
  `Compare Summoning Charm with Levitation Charm.` routing to `clarify`
  instead of lesson.
- Citation accuracy is 18/33. Most misses are comparisons that answer only one
  side: Potions cites Veritaserum but not Felix Felicis, Charms cites Nox but
  not Lumos, Herbology cites Devil's Snare but not Mandrake, and the
  third-topic DADA turns cite one side only. The group-level check requires one
  material from each side.
- False refusal is 3/33, and all three are the cross-subject turns that
  abstained instead of referring. No other turn that should answer abstained.
  Abstention accuracy is 1/1: the off-topic turn abstained and did not inherit
  the previous topic.
- Comparison accuracy is 1/12. The denominator is now only turns with two
  expected concept groups; the earlier 12/22 figure counted first turns that
  were single-topic. The corrected number is the real comparison result.
- Referral target accuracy is 0/3 by construction. The cross-subject fixture is
  the acceptance case for #253; the baseline records the current
  abstention/lesson behaviour, not a regression.
- Context contamination is 0.
- The existing corpus gate still passes:
  `scripts/run_eval.py --check --latest eval/results/20261108T080558Z.csv`
  reports `gate: PASS`.

## Reproduce

```
uv run python scripts/build_rag_fixtures.py
uv run python scripts/run_rag_eval.py
uv run python scripts/run_rag_eval.py --write-baseline
uv run python scripts/run_rag_eval.py --check
uv run python scripts/run_eval.py --rag --check
```

## Raw summary

```text
run_id: 20261112T122937Z
config: rag-eval
generator: openrouter/qwen/qwen3-30b-a3b-instruct-2507
judge: deepseek/deepseek-v4.1-flash-1017
lesson fixture: 703b128ad6c6 (judged sample 30)
multi-turn fixture: 1a86ba5c554d

lesson
  total=62 answerable=52 unanswerable=10
  selection precision@3=0.6405 recall@3=0.9660
  scope accuracy=0.9839 citation recall=0.8942
  false refusal=0.0000 abstention accuracy=1.0000
  citation validity=1.0000 source hash=1.0000
  judged=30 faithfulness=0.0667

multi-turn
  conversations=17 turns=36
  query accuracy=0.9444 mode accuracy=0.8611
  citation accuracy=0.5455 false refusal=0.0909
  abstention accuracy=1.0000
  referral target accuracy=0.0000 comparison accuracy=0.0833
  context contamination=0

errors: 0
pinned baseline: /Users/tc/Documents/Github/owl-online/eval/results/rag-baseline.json
wrote /Users/tc/Documents/Github/owl-online/eval/results/rag-20261112T122937Z.json
```
