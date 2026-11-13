# Run record: #275 DADA median-of-three calibration

- Date: 2026-11-13
- Run id: `exam-20261113-dada-median3`
- Ticket: #275 (adopt median-of-three DADA calibration)
- Bank: `dada` 1.1.0
- Config: `dada-bank-exam`
- Artifacts: `eval/exam/fixtures/calibration.jsonl`, `data/exams/dada/candidates/median-calibration.json` (local, gitignored)
- Calibration SHA256: `c0d00cb0d557bcbb39048cc910df41942949c2fbaadaa3470bdb75aa72eeb970`
- Judge: `mistralai/mistral-small-3.2-24b-instruct`, `dada-bank-judge-v2`, temperature 0.0
- Method: three calibration passes; top-level metrics are medians, calls/passes/retries are totals, the case table is the representative run

## Results

| Run | Exact | Adjacent | MAE | Calls | Retries | Needs review | Gate |
|---|---:|---:|---:|---:|---:|---|---|
| 1 | 0.5833 | 0.9583 | 0.4583 | 3 | 0 | 0 | PASS |
| 2 | 0.6667 | 0.9167 | 0.4167 | 3 | 0 | 0 | PASS |
| 3 | 0.6250 | 0.9583 | 0.4167 | 3 | 0 | 0 | PASS |
| Median | 0.6250 | 0.9583 | 0.4167 | 9 | 0 | 0 | PASS |

All three runs passed on this draw. The median gate passes at adjacent 0.9583
and MAE 0.4167. The #273 re-baseline observed one failing run at adjacent
0.8750, which is why the median protocol is adopted.

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
| `option_length_bias` | gate | PASS | correct option is strictly longest in 36.00% of MCQs; mean gap -0.36; cap 90% |
| `short_quality` | gate | PASS | 25/25 short answers have valid length, rubric and points; 0 unsupported points |
| `near_duplicates` | gate | PASS | exact=0 max_jaccard=0.4545 (limit 0.75) max_cosine=0.8772 (limit 0.90) |
| `coverage` | gate | PASS | topics=0 concepts=0 materials=0 difficulty=0 |

## Independent checks

| Check | Result |
|---|---|
| MCQ solver | 25/25 selected the stored key |
| MCQ ambiguities | 0 |
| MCQ mismatches | none |
| Short golden answers | 25/25 correct and complete |
| Short candidate answers | 23/25 earned full marks (diagnostic) |
| Short review flags | 0 |
| Missing required points | 0 |
| Errors | 0 |

## Calibration

| Metric | Value |
|---|---:|
| Cases | 24 |
| Exact agreement | 0.6250 |
| Adjacent agreement | 0.9583 |
| MAE | 0.4167 |
| Correctness agreement | 0.7083 |
| Completeness agreement | 0.8333 |
| Judge calls | 9 |
| Passes | 9 |
| Retries | 0 |
| Needs review | 0 |
| Verbose delta | 0.0 |
| Word-count correlation | 0.0833 |

## Reading

- All three runs passed on this draw. The #273 re-baseline observed a failing
  run at adjacent 0.8750, so the median protocol remains necessary even when a
  single draw is clean.
- The partial answers remain the variance slice. The median makes the gate more
  stable; it does not claim the judge is stable or improve partial scoring. A
  prompt/model revision remains the root-cause option under #40.
- The representative case table is run 3 of 3, the run closest to the median
  exact, adjacent and MAE. It is not an average.
- No short-answer, rubric, judge-model or prompt changes. DADA stays at 1.1.0.

## Reproduce

```text
uv run python scripts/run_exam_eval.py --subject dada --calibration-repeats 3 \
  --bank /Users/tc/Documents/Github/owl-online/data/exams/dada \
  --subjects /Users/tc/Documents/Github/owl-online/data/subjects \
  --chunks /Users/tc/Documents/Github/owl-online/data/chunks.jsonl \
  --json data/exams/dada/candidates/median-calibration.json
```

## Printed summary

```text
exam eval: dada 1.1.0

Deterministic checks:
  bank_validation        PASS  errors=0 warnings=0
  counts                 PASS  mcq=25 short_answer=25
  grounding              PASS  50/50 items grounded
  mcq_options            PASS  25/25 MCQs have exactly six unique options and one key
  trivial_options        PASS  0 MCQs contain all/none-of-the-above options
  negative_stems         PASS  0 MCQs use a negative equal-completion stem
  answer_positions       PASS  max stored position holds 5/25
  option_length_bias     PASS  correct option is strictly longest in 36.00% of MCQs; mean gap -0.36; cap 90%
  short_quality          PASS  25/25 short answers have valid length, rubric and points; 0 unsupported points
  near_duplicates        PASS  exact=0 max_jaccard=0.4545 (limit 0.75) max_cosine=0.8772 (limit 0.90)
  coverage               PASS  topics=0 concepts=0 materials=0 difficulty=0

Deterministic metrics:
  max_jaccard=0.45454545454545453
  max_jaccard_pair=('dada-mcq-014', 'dada-mcq-024')
  max_cosine=0.877175277200924
  max_cosine_pair=('dada-short-016', 'dada-short-018')
  option_length_bias=0.36
  option_length_mean_gap=-0.36
  answer_positions={'0': 5, '1': 4, '2': 4, '3': 4, '4': 4, '5': 4}

Independent checks:
  model=mistralai/mistral-small-3.2-24b-instruct temperature=0.0 prompt=dada-bank-independent-v1
  MCQ key matches=25/25
  MCQ mismatches=[]
  MCQ ambiguities=0
  MCQ ambiguity ids=[]
  Short golden=25/25
  Short candidate correct and complete=23
  Short review ids=[]
  Short missing points=0
  Errors=0

Calibration (median of 3 runs):
  model=mistralai/mistral-small-3.2-24b-instruct provider=openrouter temperature=0.0 prompt=dada-bank-judge-v2
  set_sha256=c0d00cb0d557bcbb39048cc910df41942949c2fbaadaa3470bdb75aa72eeb970
  n=24 exact=0.6250 adjacent=0.9583 MAE=0.4167
  per_criterion={'completeness': 0.8333333333333334, 'correctness': 0.7083333333333334}
  calls=9 passes=9 retries=0 needs_review=0
  verbose_delta=0.0 word_count_correlation=0.08326389429484357

Calibration stability:
| Run | Exact | Adjacent | MAE | Calls | Retries | Needs review | Gate |
|---|---:|---:|---:|---:|---:|---|---|
| 1 | 0.5833 | 0.9583 | 0.4583 | 3 | 0 | 0 | PASS |
| 2 | 0.6667 | 0.9167 | 0.4167 | 3 | 0 | 0 | PASS |
| 3 | 0.6250 | 0.9583 | 0.4167 | 3 | 0 | 0 | PASS |

Calibration cases (representative run 3 of 3: exact=0.6250 adjacent=0.9583 MAE=0.4167):
| Item | Variant | Human | Judge | Delta | Words | Needs review |
|---|---|---:|---:|---:|---:|---|
| `dada-short-001` | full | 8 | 8 | 0 | 32 | False |
| `dada-short-004` | full | 8 | 8 | 0 | 44 | False |
| `dada-short-006` | full | 8 | 8 | 0 | 35 | False |
| `dada-short-009` | full | 8 | 8 | 0 | 41 | False |
| `dada-short-012` | full | 8 | 8 | 0 | 48 | False |
| `dada-short-014` | full | 8 | 8 | 0 | 40 | False |
| `dada-short-017` | full | 8 | 8 | 0 | 39 | False |
| `dada-short-024` | full | 8 | 8 | 0 | 41 | False |
| `dada-short-001` | partial | 5 | 3 | -2 | 17 | False |
| `dada-short-004` | partial | 5 | 4 | -1 | 22 | False |
| `dada-short-006` | partial | 5 | 4 | -1 | 17 | False |
| `dada-short-009` | partial | 5 | 6 | 1 | 24 | False |
| `dada-short-012` | partial | 5 | 5 | 0 | 20 | False |
| `dada-short-014` | partial | 5 | 6 | 1 | 17 | False |
| `dada-short-017` | partial | 5 | 6 | 1 | 17 | False |
| `dada-short-024` | partial | 5 | 6 | 1 | 21 | False |
| `dada-short-001` | wrong | 0 | 0 | 0 | 20 | False |
| `dada-short-004` | missing_key_term | 7 | 8 | 1 | 32 | False |
| `dada-short-006` | verbose | 8 | 8 | 0 | 89 | False |
| `dada-short-009` | contradictory | 1 | 2 | 1 | 33 | False |
| `dada-short-012` | off_topic | 0 | 0 | 0 | 25 | False |
| `dada-short-014` | blank | 0 | 0 | 0 | 0 | False |
| `dada-short-017` | wrong | 0 | 0 | 0 | 20 | False |
| `dada-short-024` | verbose | 8 | 8 | 0 | 100 | False |

gate: PASS
wrote data/exams/dada/candidates/median-calibration.json
```
