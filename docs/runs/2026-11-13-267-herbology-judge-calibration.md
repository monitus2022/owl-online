# Run record: #267 Herbology judge calibration

- Date: 2026-11-13
- Run id: `exam-20261113-c8ee76b7`
- Ticket: #267 (Herbology short-answer judge calibration)
- Bank: `herbology` 1.0.0
- Artifacts: `eval/exam/fixtures/calibration-herbology.jsonl` (committed), `data/exams/herbology/candidates/exam_eval.json` (local, gitignored)
- Human marks: proposed by the AI author from the rubric; the owner's PR approval is the sign-off and adopts them as the calibration reference.

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
| Calibration set | `eval/exam/fixtures/calibration-herbology.jsonl` |
| Calibration SHA256 | `c8ee76b7c77559a61ae35252da15d2e0ff310fc4e6dbe43c6fb46ae32c024134` |
| Calibration items | 8 |
| Calibration cases | 24 |
| Coverage gate | DADA topic, difficulty and per-material targets skipped; the concept cap still gates |

## Run history

| Run id | SHA256 | Human 004 missing | Judge 004 missing | Exact | Adjacent | MAE | Gate | Note |
|---|---|---|---:|---:|---:|---:|---|---|
| `exam-20261113-605efece` | `605efece38edd9f0a04dc85bab3b55f970c2689e13c27d441c49dfe5999f7dfc` | 7 (3/4) | 4 (-3) | 0.9167 | 0.9167 | 0.2083 | PASS | Superseded; both the reference and the judge moved. |
| `exam-20261113-c8ee76b7` | `c8ee76b7c77559a61ae35252da15d2e0ff310fc4e6dbe43c6fb46ae32c024134` | 5 (3/2) | 8 (+3) | 0.9583 | 0.9583 | 0.1250 | PASS | Final adopted run. |

The prior 004 reference was 7 because the answer was credited with the irritation/gloves clause at 4. The final reference is 5 because the answer omits the swellings and the undiluted detail. Across the two runs the reference moved 7 to 5 (-2) and the judge moved 4 to 8 (+4), for a net +3. The prior run's other non-adjacent case was `herbology-short-012` contradictory (+2), which is why exact and adjacent were both 0.9167.

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

Metrics: max Jaccard `0.4444` (pair `herbology-mcq-001` / `herbology-mcq-016`), max cosine `0.8520` (pair `herbology-mcq-010` / `herbology-short-010`), option-length bias `0.36` with a mean gap of `0.36` words.

## Independent checks

| Check | Result |
|---|---|
| MCQ solver | 25/25 selected the stored key |
| MCQ ambiguities | 0 |
| MCQ mismatches | none |
| Short golden answers | 25/25 correct and complete |
| Short candidate answers | 21/25 earned full marks (diagnostic) |
| Short review flags | 0 |
| Missing required points | 0 |
| Errors | 0 |

## Calibration

| Metric | Value |
|---|---:|
| Cases | 24 |
| Exact agreement | 0.9583 |
| Adjacent agreement | 0.9583 |
| MAE | 0.1250 |
| Correctness agreement | 0.9583 |
| Completeness agreement | 0.9583 |
| Judge calls | 8 |
| Passes | 7 |
| Retries | 1 |
| Needs review | 0 |
| Verbose delta | 0.0 |
| Word-count correlation | -0.1771 |

The calibration gate passes: adjacent agreement is 0.9583, MAE is 0.1250, and
no case is `needs_review`.

## Cases

| Item | Variant | Human | Judge | Delta | Words | Needs review |
|---|---|---:|---:|---:|---:|---|
| `herbology-short-001` | full | 8 | 8 | 0 | 40 | False |
| `herbology-short-004` | full | 8 | 8 | 0 | 41 | False |
| `herbology-short-006` | full | 8 | 8 | 0 | 53 | False |
| `herbology-short-012` | full | 8 | 8 | 0 | 45 | False |
| `herbology-short-016` | full | 8 | 8 | 0 | 53 | False |
| `herbology-short-019` | full | 8 | 8 | 0 | 50 | False |
| `herbology-short-022` | full | 8 | 8 | 0 | 51 | False |
| `herbology-short-025` | full | 8 | 8 | 0 | 46 | False |
| `herbology-short-001` | partial | 4 | 4 | 0 | 6 | False |
| `herbology-short-004` | partial | 4 | 4 | 0 | 10 | False |
| `herbology-short-006` | partial | 4 | 4 | 0 | 12 | False |
| `herbology-short-012` | partial | 4 | 4 | 0 | 11 | False |
| `herbology-short-016` | partial | 4 | 4 | 0 | 8 | False |
| `herbology-short-019` | partial | 4 | 4 | 0 | 9 | False |
| `herbology-short-022` | partial | 4 | 4 | 0 | 10 | False |
| `herbology-short-025` | partial | 4 | 4 | 0 | 10 | False |
| `herbology-short-001` | wrong | 0 | 0 | 0 | 19 | False |
| `herbology-short-022` | wrong | 0 | 0 | 0 | 21 | False |
| `herbology-short-004` | missing_key_term | 5 | 8 | 3 | 12 | False |
| `herbology-short-006` | verbose | 8 | 8 | 0 | 71 | False |
| `herbology-short-025` | verbose | 8 | 8 | 0 | 55 | False |
| `herbology-short-012` | contradictory | 2 | 2 | 0 | 31 | False |
| `herbology-short-016` | off_topic | 0 | 0 | 0 | 24 | False |
| `herbology-short-019` | blank | 0 | 0 | 0 | 0 | False |

## Reproduce

```text
uv run python scripts/run_exam_eval.py --subject herbology \
  --bank /Users/tc/Documents/Github/owl-online/data/exams/herbology \
  --subjects /Users/tc/Documents/Github/owl-online/data/subjects \
  --chunks /Users/tc/Documents/Github/owl-online/data/chunks.jsonl \
  --json data/exams/herbology/candidates/exam_eval.json
```

The shorter `--subject herbology` form is equivalent for metrics, but it does
not write the JSON artifact.

## Reading notes

- The deterministic and independent checks are green. The independent solver
  selects the stored MCQ key on 25/25 and accepts the golden short answer on
  25/25.
- The calibration gate passes with adjacent agreement 0.9583 and MAE 0.1250 on
  24 cases over 8 items. Exact agreement is 0.9583.
- The one adjacent miss is `herbology-short-004` `missing_key_term`: human 5,
  judge 8 (+3). The same answer scored 4 in the prior run, so the judge is not
  bit-stable at temperature 0, and the human reference also moved from 7 to 5.
  One more non-adjacent case would leave adjacent 0.9167 and still pass; a
  second would drop to 0.8750 and fail.
- The adopted 4/0 partial band means each partial states the correct core and
  omits the completeness clause. This tests the full/core-only/wrong separation;
  it does not test mid-band completeness, which #40 owns.
- The full and verbose answers are reworded from the rubric and golden answer.
  The longest shared word run is seven words, checked by tokenising each full
  and verbose answer against the stored model answer. They are not independently
  written student answers, so full-mark agreement measures rubric coverage, not
  discrimination against unseen phrasing. Both verbose answers are longer than
  their full counterparts.
- Eight judge calls cover 24 cases; one retry occurred and no case needs review.
  The report records the retry count but not which pass retried.
- Coverage targets are DADA-specific and skipped. The concept cap still applies
  and the coverage zeros are descriptive.
- This run changes no bank content, rubric, judge model or prompt. Herbology
  stays at 1.0.0.

## Next

- Add a mid-band completeness case and reconcile the 4/0 band with the other
  subjects under #40.
- DADA 1.1.0 option-length levelling remains a separate bank revision.

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
  Short candidate correct and complete=21
  Short review ids=[]
  Short missing points=0
  Errors=0

Calibration:
  model=mistralai/mistral-small-3.2-24b-instruct provider=openrouter temperature=0.0 prompt=owl-bank-judge-v3
  set_sha256=c8ee76b7c77559a61ae35252da15d2e0ff310fc4e6dbe43c6fb46ae32c024134
  n=24 exact=0.9583 adjacent=0.9583 MAE=0.125
  per_criterion={'completeness': 0.9583333333333334, 'correctness': 0.9583333333333334}
  calls=8 passes=7 retries=1 needs_review=0
  verbose_delta=0.0 word_count_correlation=-0.17274532627107597

Calibration cases:
| Item | Variant | Human | Judge | Delta | Words | Needs review |
|---|---|---:|---:|---:|---:|---|
| `herbology-short-001` | full | 8 | 8 | 0 | 40 | False |
| `herbology-short-004` | full | 8 | 8 | 0 | 41 | False |
| `herbology-short-006` | full | 8 | 8 | 0 | 53 | False |
| `herbology-short-012` | full | 8 | 8 | 0 | 45 | False |
| `herbology-short-016` | full | 8 | 8 | 0 | 53 | False |
| `herbology-short-019` | full | 8 | 8 | 0 | 50 | False |
| `herbology-short-022` | full | 8 | 8 | 0 | 51 | False |
| `herbology-short-025` | full | 8 | 8 | 0 | 46 | False |
| `herbology-short-001` | partial | 4 | 4 | 0 | 6 | False |
| `herbology-short-004` | partial | 4 | 4 | 0 | 10 | False |
| `herbology-short-006` | partial | 4 | 4 | 0 | 12 | False |
| `herbology-short-012` | partial | 4 | 4 | 0 | 11 | False |
| `herbology-short-016` | partial | 4 | 4 | 0 | 8 | False |
| `herbology-short-019` | partial | 4 | 4 | 0 | 9 | False |
| `herbology-short-022` | partial | 4 | 4 | 0 | 10 | False |
| `herbology-short-025` | partial | 4 | 4 | 0 | 10 | False |
| `herbology-short-001` | wrong | 0 | 0 | 0 | 19 | False |
| `herbology-short-022` | wrong | 0 | 0 | 0 | 21 | False |
| `herbology-short-004` | missing_key_term | 5 | 8 | 3 | 12 | False |
| `herbology-short-006` | verbose | 8 | 8 | 0 | 71 | False |
| `herbology-short-025` | verbose | 8 | 8 | 0 | 55 | False |
| `herbology-short-012` | contradictory | 2 | 2 | 0 | 31 | False |
| `herbology-short-016` | off_topic | 0 | 0 | 0 | 24 | False |
| `herbology-short-019` | blank | 0 | 0 | 0 | 0 | False |

gate: PASS
wrote data/exams/herbology/candidates/exam_eval.json
```
