# Run record: #213 Herbology bank evaluation (bank pattern)

- Date: 2026-11-10
- Run id: `exam-20261110-herbology-1.0.0`
- Ticket: #187/#213 bank pattern (remaining subject bank)
- Bank: `herbology` 1.0.0
- Artifacts: `data/exams/herbology/candidates/exam_eval.json` (local, gitignored)
- Calibration: not run. The calibration fixture is DADA-specific.

## Configuration

| Field | Value |
|---|---|
| Bank | `herbology` 1.0.0 |
| Pack | 1.0.0 / `da6804d846814ec9` |
| Bank index hash | `aca4c57462d449f5` |
| Item prompt version | `herbology-bank-authoring-v1` |
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
| `option_length_bias` | gate | PASS | correct option is strictly longest in 36.00% of MCQs; mean gap 0.36; cap 90% |
| `short_quality` | gate | PASS | 25/25 short answers have valid length, rubric and points; 0 unsupported points |
| `near_duplicates` | gate | PASS | exact=0 max_jaccard=0.4444 (limit 0.75) max_cosine=0.8520 (limit 0.90) |
| `coverage` | gate | PASS | topics=0 concepts=0 materials=0 difficulty=0 |

## Independent checks

| Check | Result |
|---|---|
| MCQ solver | 25/25 selected the stored key |
| MCQ ambiguities | 0 |
| MCQ mismatches | none |
| Short golden answers | 25/25 correct and complete |
| Short candidate answers | 18/25 earned full marks (diagnostic) |
| Short review flags | 0 |
| Missing required points | 0 |
| Errors | 0 |

## Printed summary

```text
exam eval: herbology 1.0.0

Deterministic checks:
  bank_validation        PASS  errors=0 warnings=0
  counts                 PASS  mcq=25 short_answer=25
  grounding              PASS  50/50 items grounded
  mcq_options            PASS  25/25 MCQs have exactly six unique options and one key
  trivial_options        PASS  0 MCQs contain all/none-of-the-above options
  negative_stems         PASS  0 MCQs use a negative equal-completion stem
  answer_positions       PASS  max stored position holds 5/25
  option_length_bias     PASS  correct option is strictly longest in 36.00% of MCQs; mean gap 0.36; cap 90%
  short_quality          PASS  25/25 short answers have valid length, rubric and points; 0 unsupported points
  near_duplicates        PASS  exact=0 max_jaccard=0.4444 (limit 0.75) max_cosine=0.8520 (limit 0.90)
  coverage               PASS  topics=0 concepts=0 materials=0 difficulty=0

Deterministic metrics:
  max_jaccard=0.4444444444444444
  max_jaccard_pair=('herbology-mcq-001', 'herbology-mcq-016')
  max_cosine=0.8520101718995476
  max_cosine_pair=('herbology-mcq-010', 'herbology-short-010')
  option_length_bias=0.36
  option_length_mean_gap=0.36
  answer_positions={'0': 5, '1': 4, '2': 4, '3': 4, '4': 4, '5': 4}

Independent checks:
  model=mistralai/mistral-small-3.2-24b-instruct temperature=0.0 prompt=dada-bank-independent-v1
  MCQ key matches=25/25
  MCQ mismatches=[]
  MCQ ambiguities=0
  MCQ ambiguity ids=[]
  Short golden=25/25
  Short candidate correct and complete=18
  Short review ids=[]
  Short missing points=0
  Errors=0

gate: PASS
wrote data/exams/herbology/candidates/exam_eval.json
```

## Reading notes

- The bank covers all six Herbology topics and 30 of 31 pack concepts; the
  Whomping Willow knot procedure has no dedicated item because it is a plot
  device rather than a general plant-care concept.
- The default DADA per-material coverage target does not fit a 33-material,
  50-item bank, so this run skips that target and reports topic coverage
  descriptively.
- Seven model-written candidate short answers did not earn full marks; that is
  a diagnostic of candidate wording, not a defect in the stored keys.

## Reproduce

```text
uv run python scripts/run_exam_eval.py --bank data/exams/herbology --no-calibration --skip-coverage-targets --json data/exams/herbology/candidates/exam_eval.json
```
