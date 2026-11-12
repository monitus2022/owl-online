# Run record: #248 lesson and multi-turn RAG baseline

- Date: 2026-11-12
- Run id: `20261112T113707Z`
- Ticket: #248 (lesson and multi-turn evaluation foundation)
- Config: `rag-eval` (persona on, lesson mode on, lesson fallback on)
- Artifacts: `eval/results/rag-20261112T113707Z.json` (local, gitignored), `eval/results/rag-baseline.json` (committed)

## Configuration

| Field | Value |
|---|---|
| Generator | `openrouter/qwen/qwen3-30b-a3b-instruct-2507` |
| Judge | `deepseek/deepseek-v4.1-flash-1017`, temperature 0.0 |
| Embedder | local `qwen3-embedding:0.6b` |
| Lesson selection | top-k 3, cosine floor 0.58, lexical extras on |
| Lesson fallback | on |
| Lesson fixture | `eval/rag/fixtures/lesson.jsonl`, 60 items, SHA-256 `16f5c7b3f6cb` |
| Multi-turn fixture | `eval/rag/fixtures/multiturn.jsonl`, 17 conversations / 36 turns, SHA-256 `1a86ba5c554d` |
| Judged lesson sample | 30, round-robin across slices |
| Cache | `eval/.cache/rag` |

The fixtures store concept titles, material ids and source-ref structure only.
No pack prose or corpus text is committed.

## Lesson

| Metric | Value |
|---|---:|
| Items | 60 |
| Answerable | 50 |
| Unanswerable | 10 |
| Selection precision@3 | 0.6333 |
| Selection recall@3 | 0.9653 |
| Scope accuracy | 0.9833 |
| Citation recall | 0.9600 |
| False refusal rate | 0.0000 |
| Abstention accuracy | 1.0000 |
| Citation validity | 1.0000 |
| Source hash validity | 1.0000 |
| Judged | 30 |
| Faithfulness | 0.1667 |

## Multi-turn

| Metric | Value |
|---|---:|
| Conversations | 17 |
| Turns | 36 |
| Retrieval-query accuracy | 0.9444 |
| Mode accuracy | 0.8611 |
| Citation accuracy | 0.5758 |
| Abstention accuracy | 0.8824 |
| Referral target accuracy | 0.0000 |
| Comparison accuracy | 0.5455 |
| Context contamination | 0 |
| Errors | 0 |

## Reading

- The lesson contract is structurally sound. Scope accuracy is 59/60,
  citation validity and source hashes are 1.0000, false refusals are 0/50, and
  unanswerable abstention is 10/10. The invented terms were refused, not
  answered from the corpus.
- Selection recall is 0.9653, but precision is 0.6333. The selector finds the
  intended concept and spends the third slot on a near neighbour. Selection is
  not the main bottleneck; it is a useful signal for the multi-concept pairs.
- Faithfulness is the headline. Only 5 of 30 judged lesson answers are
  supported by the selected notes: `lesson-dada-04`, `lesson-charms-00`,
  `lesson-potions-01`, `lesson-transfiguration-05` and
  `lesson-herbology-05`. The other 25 are fluent elaborations beyond the
  selected material. Citation validity is 1.0000 at the same time, so a valid
  citation is not evidence that the claim is supported. This is the case for
  #251.
- One scope miss remains: `lesson-charms-07` (Wand-Extinguishing against
  Summoning) selected the generic charm definition, Nox and Wands, then fell
  to `mixed` with only the Nox material cited. The selector did not reach the
  Summoning material.
- Multi-turn query accuracy is 34/36. The two misses are the intended gaps:
  `how do I defeat one?` is not rewritten to include the Boggart, and
  `no, I meant a Dementor` is not rewritten to the correction. These are the
  target behaviours for #249.
- Mode accuracy is 31/36. Three misses are the cross-subject referral cases
  (the contract is #253 and is not implemented yet), one is the implicit
  follow-up abstaining instead of staying lesson, and one is
  `Compare Summoning Charm with Levitation Charm.` routing to `clarify`
  instead of lesson. The clarify route needs its own investigation.
- Citation accuracy is 19/33. Most misses are comparisons that answer only
  one side: Potions cites Veritaserum but not Felix Felicis, Charms cites Nox
  but not Lumos, Herbology cites Devil's Snare but not Mandrake, and the
  third-topic DADA turn cites the Boggart but not the Dementor. The group-level
  check requires one material from each side; the metric is not penalising a
  second material on the same concept.
- Abstention accuracy is 30/34. The misses are the implicit and correction
  turns, the cross-subject Potions and DADA turns, and the third Charms turn
  abstaining instead of comparing Nox with the Unlocking Charm.
- Referral target accuracy is 0/3 by construction. The cross-subject fixture
  is the acceptance case for #253; the baseline records the current
  abstention/lesson behaviour, not a regression.
- Context contamination is 0. The off-topic turn abstained and did not inherit
  the Boggart.
- The judged sample is 30 and the multi-concept slice has 20 items. The lesson
  fixture is large enough to separate the faithfulness gap from noise; the
  multi-turn citation denominator is 33 turns, so a single comparison flip is
  visible.

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
run_id: 20261112T113707Z
config: rag-eval
generator: openrouter/qwen/qwen3-30b-a3b-instruct-2507
judge: deepseek/deepseek-v4.1-flash-1017
lesson fixture: 16f5c7b3f6cb (judged sample 30)
multi-turn fixture: 1a86ba5c554d

lesson
  total=60 answerable=50 unanswerable=10
  selection precision@3=0.6333 recall@3=0.9653
  scope accuracy=0.9833 citation recall=0.9600
  false refusal=0.0000 abstention accuracy=1.0000
  citation validity=1.0000 source hash=1.0000
  judged=30 faithfulness=0.1667

multi-turn
  conversations=17 turns=36
  query accuracy=0.9444 mode accuracy=0.8611
  citation accuracy=0.5758 abstention accuracy=0.8824
  referral target accuracy=0.0000 comparison accuracy=0.5455
  context contamination=0

errors: 0
pinned baseline: /Users/tc/Documents/Github/owl-online/eval/results/rag-baseline.json
wrote /Users/tc/Documents/Github/owl-online/eval/results/rag-20261112T113707Z.json
```
