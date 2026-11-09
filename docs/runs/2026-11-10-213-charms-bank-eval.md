# Run record: #213 Charms bank evaluation

- Date: 2026-11-10
- Run id: `exam-20261110-charms-1.0.0`
- Ticket: #213 (Charms exam bank 1.0.0)
- Bank: `charms` 1.0.0
- Artifacts: `data/exams/charms/candidates/exam_eval.json` (local, gitignored)
- Calibration: not run. The calibration fixture in `eval/exam/fixtures/calibration.jsonl` is DADA-specific; the Charms bank uses the shared rubric judge but has no owner-marked calibration set.

## Configuration

| Field | Value |
|---|---|
| Bank | `charms` 1.0.0 |
| Pack | 1.0.0 / `12e1ee2fe077a004` |
| Bank index hash | `aca4c57462d449f5` |
| Item prompt version | `charms-bank-authoring-v1` |
| Judge | `mistralai/mistral-small-3.2-24b-instruct` |
| Judge provider | `openrouter` |
| Judge temperature | 0.0 |
| Judge prompt | `owl-bank-judge-v3` |
| Independent prompt | `dada-bank-independent-v1` |
| Embedder | `qwen3-embedding:0.6b` (local) |
| Coverage gate | DADA topic, difficulty and per-material targets skipped |

## Deterministic checks

| Check | Gate | Status | Detail |
|---|---|---|---|
| `bank_validation` | gate | PASS | errors=0 warnings=0 |
| `counts` | gate | PASS | mcq=25 short_answer=25 |
| `grounding` | gate | PASS | 50/50 items grounded |
| `mcq_options` | gate | PASS | 25/25 MCQs have exactly six unique options and one key |
| `trivial_options` | gate | PASS | 0 MCQs contain all/none-of-the-above options |
| `negative_stems` | gate | PASS | 0 MCQs use a negative equal-completion stem |
| `answer_positions` | gate | PASS | max stored position holds 5/25 |
| `option_length_bias` | gate | PASS | correct option is strictly longest in 48.00% of MCQs; mean gap 0.72; cap 90% |
| `short_quality` | gate | PASS | 25/25 short answers have valid length, rubric and points; 0 unsupported points |
| `near_duplicates` | gate | PASS | exact=0 max_jaccard=0.6500 (limit 0.75) max_cosine=0.8628 (limit 0.90) |
| `coverage` | gate | PASS | topics=0 concepts=0 materials=0 difficulty=0 |

Metrics: max Jaccard `0.6500` (pair `charms-short-008` / `charms-short-009`), max cosine `0.8628` (pair `charms-mcq-022` / `charms-short-021`), option-length bias `0.48` with a mean gap of `0.72` words.

## Coverage

| Topic | MCQ | Short answer |
|---|---:|---:|
| `charms-elements` | 5 | 6 |
| `charms-foundations` | 5 | 2 |
| `charms-jinxes` | 4 | 6 |
| `charms-movement` | 5 | 2 |
| `charms-practice` | 0 | 2 |
| `charms-sound` | 3 | 2 |
| `charms-utility` | 3 | 5 |

The bank covers all 7 topics and all 49 pack concepts. It cites 44 of the 50
materials; the six practice, classroom and examination-administration materials
are intentionally not tested because the bank tests charm concepts only. The
DADA blueprint's one-item-per-kind-per-material target would require 100 items
for a 50-material pack, so this run skips that target and reports coverage
descriptively. The concept cap (no more than two items of one kind per concept)
still applies and passes.

## Independent checks

| Check | Result |
|---|---|
| MCQ solver | 25/25 selected the stored key |
| MCQ ambiguities | 0 |
| MCQ mismatches | none |
| Short golden answers | 25/25 correct and complete |
| Short candidate answers | 24/25 earned full marks (diagnostic) |
| Short review flags | 0 |
| Missing required points | 0 |
| Errors | 0 |

## Printed summary

```text
exam eval: charms 1.0.0

Deterministic checks:
  bank_validation        PASS  errors=0 warnings=0
  counts                 PASS  mcq=25 short_answer=25
  grounding              PASS  50/50 items grounded
  mcq_options            PASS  25/25 MCQs have exactly six unique options and one key
  trivial_options        PASS  0 MCQs contain all/none-of-the-above options
  negative_stems         PASS  0 MCQs use a negative equal-completion stem
  answer_positions       PASS  max stored position holds 5/25
  option_length_bias     PASS  correct option is strictly longest in 48.00% of MCQs; mean gap 0.72; cap 90%
  short_quality          PASS  25/25 short answers have valid length, rubric and points; 0 unsupported points
  near_duplicates        PASS  exact=0 max_jaccard=0.6500 (limit 0.75) max_cosine=0.8628 (limit 0.90)
  coverage               PASS  topics=0 concepts=0 materials=0 difficulty=0

Deterministic metrics:
  max_jaccard=0.65
  max_jaccard_pair=('charms-short-008', 'charms-short-009')
  max_cosine=0.8627607372383191
  max_cosine_pair=('charms-mcq-022', 'charms-short-021')
  option_length_bias=0.48
  option_length_mean_gap=0.72
  answer_positions={'0': 5, '1': 4, '2': 4, '3': 4, '4': 4, '5': 4}

Independent checks:
  model=mistralai/mistral-small-3.2-24b-instruct temperature=0.0 prompt=dada-bank-independent-v1
  MCQ key matches=25/25
  MCQ mismatches=[]
  MCQ ambiguities=0
  MCQ ambiguity ids=[]
  Short golden=25/25
  Short candidate correct and complete=24
  Short review ids=[]
  Short missing points=0
  Errors=0

gate: PASS
wrote data/exams/charms/candidates/exam_eval.json
```

## Reading notes

- The deterministic gate is green with no warnings.
- The independent solver agrees with every MCQ key and every golden answer.
- The one candidate short answer that did not earn full marks is a diagnostic
  measure of a model-written candidate, not a defect in the stored key.
- No retrieval or generation slice is part of this run; the RAG gate is
  unchanged.

## Next

No bank content change follows from this run. The Charms bank is published at
1.0.0 and served as `charms-1.0.0`.
