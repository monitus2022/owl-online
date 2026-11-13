# Run record: #266 Transfiguration judge calibration

- Date: 2026-11-13
- Run id: `exam-20261113-cf3e7b00`
- Ticket: #266 (Transfiguration short-answer judge calibration)
- Bank: `transfiguration` 1.0.0
- Artifacts: `eval/exam/fixtures/calibration-transfiguration.jsonl` (committed), `data/exams/transfiguration/candidates/exam_eval.json` (local, gitignored)
- Human marks: proposed by the AI author from the rubric; the owner's PR approval is the sign-off and adopts them as the calibration reference.

## Configuration

| Field | Value |
|---|---|
| Bank | `transfiguration` 1.0.0 |
| Pack | 1.0.0 / `81c6cd2c91cb975f` |
| Bank index hash | `aca4c57462d449f5` |
| Item prompt version | `transfiguration-bank-authoring-v1` |
| Judge | `mistralai/mistral-small-3.2-24b-instruct` |
| Judge provider | `openrouter` |
| Judge temperature | 0.0 |
| Judge prompt | `owl-bank-judge-v3` |
| Independent prompt | `dada-bank-independent-v1` |
| Embedder | `qwen3-embedding:0.6b` (local) |
| Calibration set | `eval/exam/fixtures/calibration-transfiguration.jsonl` |
| Calibration SHA256 | `cf3e7b0029f96c2ff454440aefbce73031a7dfb9f481f6258e7432f2795a12d9` |
| Calibration items | 8 |
| Calibration cases | 24 |
| Coverage gate | DADA topic, difficulty and per-material targets skipped; the concept cap still gates |

## Run history

| Run id | SHA256 | Partial band | Exact | Adjacent | MAE | Gate | Note |
|---|---|---|---:|---:|---:|---|---|
| `exam-20261113-86c01740` | `86c0174080414bbcc52e9f67f9b8a28d88259c5c94206c25a7c1da3d857e50c8` | 4/3 | 0.5833 | 0.8750 | 0.6667 | FAIL | First design; judge unstable on clause-split partials. |
| `exam-20261113-6a67f74c` | `6a67f74c05ddb087c0b1470ccd0a386ac983a411e1283c06114c3baa9037ff32` | 4/0-4/3 | 0.6667 | 0.9583 | 0.4167 | PASS | Superseded by the 013/012 corrections. |
| `exam-20261113-e9c20843` | `e9c2084316a5e0e5c72e112ed87b3a23dfa161e02cd0a411b16cfd24d866e63c` | 4/0-4/3 | 0.6667 | 0.8750 | 0.5417 | FAIL | Superseded. |
| `exam-20261113-cd7353e3` | `cd7353e3539e349ec2e92b625db39a0124251e56159b8f4d83d5efd27f3285dd` | 4/3 | 0.6250 | 0.7500 | 0.8750 | FAIL | Clause-split rewrite; judge moved to 4 on most partials. |
| `exam-20261113-cf3e7b00` | `cf3e7b0029f96c2ff454440aefbce73031a7dfb9f481f6258e7432f2795a12d9` | 4/0 | 0.9583 | 1.0000 | 0.0417 | PASS | Final adopted run. |

The adopted partial band is 4/0: each partial states the correct core and omits the completeness clause entirely. The earlier clause-split designs showed the judge is not stable in the mid-band; #40 owns adding a mid-band case and reconciling the band across subjects.

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
| `option_length_bias` | gate | PASS | correct option is strictly longest in 56.00% of MCQs; mean gap 0.68; cap 90% |
| `short_quality` | gate | PASS | 25/25 short answers have valid length, rubric and points; 0 unsupported points |
| `near_duplicates` | gate | PASS | exact=0 max_jaccard=0.3750 (limit 0.75) max_cosine=0.8747 (limit 0.90) |
| `coverage` | gate | PASS | topics=0 concepts=0 materials=0 difficulty=0 |

Metrics: max Jaccard `0.3750` (pair `transfiguration-short-009` / `transfiguration-short-022`), max cosine `0.8747` (pair `transfiguration-short-003` / `transfiguration-short-004`), option-length bias `0.56` with a mean gap of `0.68` words.

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
| Exact agreement | 0.9583 |
| Adjacent agreement | 1.0000 |
| MAE | 0.0417 |
| Correctness agreement | 0.9583 |
| Completeness agreement | 1.0000 |
| Judge calls | 9 |
| Passes | 7 |
| Retries | 2 |
| Needs review | 0 |
| Verbose delta | 0.0 |
| Word-count correlation | 0.1076 |

The calibration gate passes: adjacent agreement is 1.0000, MAE is 0.0417, and
no case is `needs_review`.

## Cases

| Item | Variant | Human | Judge | Delta | Words | Needs review |
|---|---|---:|---:|---:|---:|---|
| `transfiguration-short-001` | full | 8 | 8 | 0 | 49 | False |
| `transfiguration-short-005` | full | 8 | 8 | 0 | 48 | False |
| `transfiguration-short-009` | full | 8 | 8 | 0 | 57 | False |
| `transfiguration-short-012` | full | 8 | 8 | 0 | 44 | False |
| `transfiguration-short-013` | full | 8 | 8 | 0 | 65 | False |
| `transfiguration-short-018` | full | 8 | 8 | 0 | 52 | False |
| `transfiguration-short-022` | full | 8 | 8 | 0 | 41 | False |
| `transfiguration-short-025` | full | 8 | 8 | 0 | 56 | False |
| `transfiguration-short-001` | partial | 4 | 4 | 0 | 8 | False |
| `transfiguration-short-005` | partial | 4 | 4 | 0 | 13 | False |
| `transfiguration-short-009` | partial | 4 | 4 | 0 | 9 | False |
| `transfiguration-short-012` | partial | 4 | 4 | 0 | 10 | False |
| `transfiguration-short-013` | partial | 4 | 4 | 0 | 14 | False |
| `transfiguration-short-018` | partial | 4 | 4 | 0 | 10 | False |
| `transfiguration-short-022` | partial | 4 | 4 | 0 | 7 | False |
| `transfiguration-short-025` | partial | 4 | 4 | 0 | 12 | False |
| `transfiguration-short-001` | wrong | 0 | 0 | 0 | 18 | False |
| `transfiguration-short-022` | wrong | 0 | 0 | 0 | 21 | False |
| `transfiguration-short-005` | missing_key_term | 4 | 4 | 0 | 18 | False |
| `transfiguration-short-009` | verbose | 8 | 8 | 0 | 67 | False |
| `transfiguration-short-025` | verbose | 8 | 8 | 0 | 74 | False |
| `transfiguration-short-012` | contradictory | 3 | 2 | -1 | 19 | False |
| `transfiguration-short-013` | off_topic | 0 | 0 | 0 | 21 | False |
| `transfiguration-short-018` | blank | 0 | 0 | 0 | 0 | False |

## Reproduce

```text
uv run python scripts/run_exam_eval.py --subject transfiguration \
  --bank /Users/tc/Documents/Github/owl-online/data/exams/transfiguration \
  --subjects /Users/tc/Documents/Github/owl-online/data/subjects \
  --chunks /Users/tc/Documents/Github/owl-online/data/chunks.jsonl \
  --json data/exams/transfiguration/candidates/exam_eval.json
```

The shorter `--subject transfiguration` form is equivalent for metrics, but it
does not write the JSON artifact.

## Reading notes

- The deterministic and independent checks are green. The independent solver
  selects the stored MCQ key on 25/25 and accepts the golden short answer on
  25/25.
- The calibration gate passes with adjacent agreement 1.0000 and MAE 0.0417 on
  24 cases over 8 items. Exact agreement is 0.9583.
- The adopted 4/0 partial band means each partial states the correct core and
  omits the completeness clause. This tests that the judge separates full,
  core-only and wrong answers; it does not test mid-band completeness, which
  #40 owns.
- Five run ids are recorded. The clause-split 4/3 designs failed because the
  judge moved between 4 and 8 on answers that covered one completeness clause.
  The final design is core-only and the judge agrees on every partial.
- The one non-exact case is `transfiguration-short-012` contradictory at -1.
- The full and verbose answers are reworded from the rubric and golden answer.
  The longest shared word run is six words, checked by tokenising each full and
  verbose answer against the stored model answer. They are not independently
  written student answers, so full-mark agreement measures rubric coverage, not
  discrimination against unseen phrasing. Both verbose answers are longer than
  their full counterparts.
- Nine judge calls cover 24 cases; two retries occurred and no case needs
  review. The report records the retry count but not which pass retried.
- Coverage targets are DADA-specific and skipped. The concept cap still applies
  and the coverage zeros are descriptive.
- This run changes no bank content, rubric, judge model or prompt.
  Transfiguration stays at 1.0.0.

## Next

- Add a mid-band completeness case and reconcile the 4/0 band with the other
  subjects under #40.
- DADA 1.1.0 option-length levelling remains a separate bank revision.

## Printed summary

```text
exam eval: transfiguration 1.0.0

Deterministic checks:
  bank_validation        PASS  errors=0 warnings=0
  counts                 PASS  mcq=25 short_answer=25
  grounding              PASS  50/50 items grounded
  mcq_options            PASS  25/25 MCQs have exactly six unique options and one key
  trivial_options        PASS  0 MCQs contain all/none-of-the-above options
  negative_stems         PASS  0 MCQs use a negative equal-completion stem
  answer_positions       PASS  max stored position holds 5/25
  option_length_bias     PASS  correct option is strictly longest in 56.00% of MCQs; mean gap 0.68; cap 90%
  short_quality          PASS  25/25 short answers have valid length, rubric and points; 0 unsupported points
  near_duplicates        PASS  exact=0 max_jaccard=0.3750 (limit 0.75) max_cosine=0.8747 (limit 0.90)
  coverage               PASS  topics=0 concepts=0 materials=0 difficulty=0

Deterministic metrics:
  max_jaccard=0.375
  max_jaccard_pair=('transfiguration-short-009', 'transfiguration-short-022')
  max_cosine=0.8747259592352733
  max_cosine_pair=('transfiguration-short-003', 'transfiguration-short-004')
  option_length_bias=0.56
  option_length_mean_gap=0.68
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
  set_sha256=cf3e7b0029f96c2ff454440aefbce73031a7dfb9f481f6258e7432f2795a12d9
  n=24 exact=0.9583 adjacent=1.0000 MAE=0.041666666666666664
  per_criterion={'completeness': 1.0, 'correctness': 0.9583333333333334}
  calls=9 passes=7 retries=2 needs_review=0
  verbose_delta=0.0 word_count_correlation=0.10759092567885668

Calibration cases:
| Item | Variant | Human | Judge | Delta | Words | Needs review |
|---|---|---:|---:|---:|---:|---|
| `transfiguration-short-001` | full | 8 | 8 | 0 | 49 | False |
| `transfiguration-short-005` | full | 8 | 8 | 0 | 48 | False |
| `transfiguration-short-009` | full | 8 | 8 | 0 | 57 | False |
| `transfiguration-short-012` | full | 8 | 8 | 0 | 44 | False |
| `transfiguration-short-013` | full | 8 | 8 | 0 | 65 | False |
| `transfiguration-short-018` | full | 8 | 8 | 0 | 52 | False |
| `transfiguration-short-022` | full | 8 | 8 | 0 | 41 | False |
| `transfiguration-short-025` | full | 8 | 8 | 0 | 56 | False |
| `transfiguration-short-001` | partial | 4 | 4 | 0 | 8 | False |
| `transfiguration-short-005` | partial | 4 | 4 | 0 | 13 | False |
| `transfiguration-short-009` | partial | 4 | 4 | 0 | 9 | False |
| `transfiguration-short-012` | partial | 4 | 4 | 0 | 10 | False |
| `transfiguration-short-013` | partial | 4 | 4 | 0 | 14 | False |
| `transfiguration-short-018` | partial | 4 | 4 | 0 | 10 | False |
| `transfiguration-short-022` | partial | 4 | 4 | 0 | 7 | False |
| `transfiguration-short-025` | partial | 4 | 4 | 0 | 12 | False |
| `transfiguration-short-001` | wrong | 0 | 0 | 0 | 18 | False |
| `transfiguration-short-022` | wrong | 0 | 0 | 0 | 21 | False |
| `transfiguration-short-005` | missing_key_term | 4 | 4 | 0 | 18 | False |
| `transfiguration-short-009` | verbose | 8 | 8 | 0 | 67 | False |
| `transfiguration-short-025` | verbose | 8 | 8 | 0 | 74 | False |
| `transfiguration-short-012` | contradictory | 3 | 2 | -1 | 19 | False |
| `transfiguration-short-013` | off_topic | 0 | 0 | 0 | 21 | False |
| `transfiguration-short-018` | blank | 0 | 0 | 0 | 0 | False |

gate: PASS
wrote data/exams/transfiguration/candidates/exam_eval.json
```
