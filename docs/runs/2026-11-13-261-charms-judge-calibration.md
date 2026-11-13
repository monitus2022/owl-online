# Run record: #261 Charms judge calibration

- Date: 2026-11-13
- Run id: `exam-20261113-5e5fb6bf`
- Ticket: #261 (Charms short-answer judge calibration)
- Bank: `charms` 1.0.0
- Artifacts: `eval/exam/fixtures/calibration-charms.jsonl` (committed), `data/exams/charms/candidates/exam_eval.json` (local, gitignored)
- Human marks: proposed by the AI author from the rubric; the owner's PR approval is the sign-off and adopts them as the calibration reference.

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
| Calibration set | `eval/exam/fixtures/calibration-charms.jsonl` |
| Calibration SHA256 | `5e5fb6bf8bda74368c6dd10afd95126d735497fb11fc88bc66f6bb52977ffcce` |
| Calibration items | 8 |
| Calibration cases | 24 |
| Coverage gate | DADA topic, difficulty and per-material targets skipped; the concept cap still gates |

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

## Independent checks

| Check | Result |
|---|---|
| MCQ solver | 25/25 selected the stored key |
| MCQ ambiguities | 0 |
| MCQ mismatches | none |
| Short golden answers | 25/25 correct and complete |
| Short candidate answers | 25/25 earned full marks (diagnostic) |
| Short review flags | 0 |
| Missing required points | 0 |
| Errors | 0 |

## Calibration

| Metric | Value |
|---|---:|
| Cases | 24 |
| Exact agreement | 0.6250 |
| Adjacent agreement | 1.0000 |
| MAE | 0.3750 |
| Correctness agreement | 0.6250 |
| Completeness agreement | 0.7500 |
| Judge calls | 7 |
| Passes | 7 |
| Retries | 0 |
| Needs review | 0 |
| Verbose delta | 0.0 |
| Word-count correlation | 0.2013 |

The calibration gate passes: adjacent agreement is 1.0000, MAE is 0.3750,
and no case is `needs_review`.

## Cases

| Item | Variant | Human | Judge | Delta | Words | Needs review |
|---|---|---:|---:|---:|---:|---|
| `charms-short-001` | full | 8 | 8 | 0 | 59 | False |
| `charms-short-004` | full | 8 | 8 | 0 | 59 | False |
| `charms-short-007` | full | 8 | 8 | 0 | 49 | False |
| `charms-short-010` | full | 8 | 8 | 0 | 52 | False |
| `charms-short-013` | full | 8 | 8 | 0 | 44 | False |
| `charms-short-016` | full | 8 | 8 | 0 | 37 | False |
| `charms-short-019` | full | 8 | 8 | 0 | 53 | False |
| `charms-short-022` | full | 8 | 8 | 0 | 55 | False |
| `charms-short-001` | partial | 5 | 6 | 1 | 28 | False |
| `charms-short-004` | partial | 5 | 4 | -1 | 26 | False |
| `charms-short-007` | partial | 5 | 4 | -1 | 21 | False |
| `charms-short-010` | partial | 5 | 4 | -1 | 22 | False |
| `charms-short-013` | partial | 5 | 4 | -1 | 19 | False |
| `charms-short-016` | partial | 5 | 6 | 1 | 15 | False |
| `charms-short-019` | partial | 5 | 4 | -1 | 23 | False |
| `charms-short-022` | partial | 5 | 4 | -1 | 27 | False |
| `charms-short-001` | wrong | 0 | 0 | 0 | 28 | False |
| `charms-short-019` | wrong | 0 | 0 | 0 | 32 | False |
| `charms-short-004` | missing_key_term | 7 | 8 | 1 | 37 | False |
| `charms-short-007` | verbose | 8 | 8 | 0 | 77 | False |
| `charms-short-022` | verbose | 8 | 8 | 0 | 84 | False |
| `charms-short-010` | contradictory | 4 | 4 | 0 | 44 | False |
| `charms-short-013` | off_topic | 0 | 0 | 0 | 26 | False |
| `charms-short-016` | blank | 0 | 0 | 0 | 0 | False |

## Reproduce

```text
uv run python scripts/run_exam_eval.py --subject charms \
  --bank /Users/tc/Documents/Github/owl-online/data/exams/charms \
  --subjects /Users/tc/Documents/Github/owl-online/data/subjects \
  --chunks /Users/tc/Documents/Github/owl-online/data/chunks.jsonl \
  --json data/exams/charms/candidates/exam_eval.json
```

In a checkout that has `data/`, the shorter form is equivalent:

```text
uv run python scripts/run_exam_eval.py --subject charms
```

## Reading notes

- The deterministic gate is green with no warnings. The independent solver
  selects the stored MCQ key on 25/25 and accepts the golden short answer on
  25/25.
- The calibration gate passes with adjacent agreement 1.0000 and MAE 0.3750 on
  24 cases over 8 items. Exact agreement is 0.6250.
- The full and verbose answers are reworded from the rubric and the golden
  answer, with no copied sentences and only short overlapping phrases. They are
  not independently written student answers, so the full-mark agreement measures
  rubric coverage, not discrimination against unseen phrasing. The verbose
  cases earned no length advantage: the verbose delta is 0.0 and the word-count
  correlation is weak at 0.2013.
- Three cases are one mark above the human mark: two partial answers
  (`charms-short-001`, `charms-short-016`) and `charms-short-004`
  `missing_key_term`. Six partial answers are one mark below. The dominant
  direction is strict, not lenient. The served-grading implication is a
  one-mark under-award on most partial answers and a one-mark over-award on
  those three cases. A follow-up under #40 should decide whether the
  partial-answer band is too harsh before considering a stricter instruction.
- `charms-short-010` contradictory is marked correctness 4 because it states
  the mood effect correctly, and completeness 0 under the grading contract's
  contradictory-answer rule because it denies the need to control the strength.
  The judge agrees exactly, so the case is not an outlier.
- Seven judge calls cover 24 cases because the calibration groups cases by pass;
  there were no retries and no case needs review.
- Coverage targets are DADA-specific and skipped. The concept cap still applies
  and the deterministic `coverage` check reports zeros for the skipped target
  counts, which is descriptive rather than a Charms coverage failure.
- This run changes no bank content, rubric, judge model or prompt. The Charms
  bank stays at 1.0.0.

## Next

- Add the same calibration set for Potions, Transfiguration and Herbology.
- Decide under #40 whether the partial-answer band is too harsh.
- DADA 1.1.0 option-length levelling remains a separate bank revision.

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
  Short candidate correct and complete=25
  Short review ids=[]
  Short missing points=0
  Errors=0

Calibration:
  model=mistralai/mistral-small-3.2-24b-instruct provider=openrouter temperature=0.0 prompt=owl-bank-judge-v3
  set_sha256=5e5fb6bf8bda74368c6dd10afd95126d735497fb11fc88bc66f6bb52977ffcce
  n=24 exact=0.6250 adjacent=1.0000 MAE=0.375
  per_criterion={'completeness': 0.75, 'correctness': 0.625}
  calls=7 passes=7 retries=0 needs_review=0
  verbose_delta=0.0 word_count_correlation=0.20132496236571812

Calibration cases:
| Item | Variant | Human | Judge | Delta | Words | Needs review |
|---|---|---:|---:|---:|---:|---|
| `charms-short-001` | full | 8 | 8 | 0 | 59 | False |
| `charms-short-004` | full | 8 | 8 | 0 | 59 | False |
| `charms-short-007` | full | 8 | 8 | 0 | 49 | False |
| `charms-short-010` | full | 8 | 8 | 0 | 52 | False |
| `charms-short-013` | full | 8 | 8 | 0 | 44 | False |
| `charms-short-016` | full | 8 | 8 | 0 | 37 | False |
| `charms-short-019` | full | 8 | 8 | 0 | 53 | False |
| `charms-short-022` | full | 8 | 8 | 0 | 55 | False |
| `charms-short-001` | partial | 5 | 6 | 1 | 28 | False |
| `charms-short-004` | partial | 5 | 4 | -1 | 26 | False |
| `charms-short-007` | partial | 5 | 4 | -1 | 21 | False |
| `charms-short-010` | partial | 5 | 4 | -1 | 22 | False |
| `charms-short-013` | partial | 5 | 4 | -1 | 19 | False |
| `charms-short-016` | partial | 5 | 6 | 1 | 15 | False |
| `charms-short-019` | partial | 5 | 4 | -1 | 23 | False |
| `charms-short-022` | partial | 5 | 4 | -1 | 27 | False |
| `charms-short-001` | wrong | 0 | 0 | 0 | 28 | False |
| `charms-short-019` | wrong | 0 | 0 | 0 | 32 | False |
| `charms-short-004` | missing_key_term | 7 | 8 | 1 | 37 | False |
| `charms-short-007` | verbose | 8 | 8 | 0 | 77 | False |
| `charms-short-022` | verbose | 8 | 8 | 0 | 84 | False |
| `charms-short-010` | contradictory | 4 | 4 | 0 | 44 | False |
| `charms-short-013` | off_topic | 0 | 0 | 0 | 26 | False |
| `charms-short-016` | blank | 0 | 0 | 0 | 0 | False |

gate: PASS
wrote data/exams/charms/candidates/exam_eval.json
```
