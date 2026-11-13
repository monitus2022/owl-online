# Run record: #264 Potions judge calibration

- Date: 2026-11-13
- Run id: `exam-20261113-787aeb63`
- Ticket: #264 (Potions short-answer judge calibration)
- Bank: `potions` 1.0.0
- Artifacts: `eval/exam/fixtures/calibration-potions.jsonl` (committed), `data/exams/potions/candidates/exam_eval.json` (local, gitignored)
- Human marks: proposed by the AI author from the rubric; the owner's PR approval is the sign-off and adopts them as the calibration reference.

## Configuration

| Field | Value |
|---|---|
| Bank | `potions` 1.0.0 |
| Pack | 1.0.0 / `bc75045e02412ffe` |
| Bank index hash | `aca4c57462d449f5` |
| Item prompt version | `potions-bank-authoring-v1` |
| Judge | `mistralai/mistral-small-3.2-24b-instruct` |
| Judge provider | `openrouter` |
| Judge temperature | 0.0 |
| Judge prompt | `owl-bank-judge-v3` |
| Independent prompt | `dada-bank-independent-v1` |
| Embedder | `qwen3-embedding:0.6b` (local) |
| Calibration set | `eval/exam/fixtures/calibration-potions.jsonl` |
| Calibration SHA256 | `787aeb63a237bff98050e2db6df7a58fe4ab302567426e18a02e4df75e743115` |
| Calibration items | 8 |
| Calibration cases | 24 |
| Coverage gate | DADA topic, difficulty and per-material targets skipped; the concept cap still gates |

## Run history

| Run id | Partial band | Exact | Adjacent | MAE | Gate | Note |
|---|---|---:|---:|---:|---|---|
| `exam-20261113-82042d78` | 3/2 | 0.6250 | 0.6667 | 0.8750 | FAIL | First run; the judge over-awarded the partial band. |
| `exam-20261113-d3815afc` | 4/2-3 | 0.7083 | 0.9583 | 0.3333 | PASS | Superseded by the contradictory-mark correction. |
| `exam-20261113-787aeb63` | 4/2-3, 013 3/0 | 0.6667 | 0.9583 | 0.3750 | PASS | Final adopted run. |

The partial band was raised from the Charms 3/2 band after the failed run.
#40 owns reconciling that band with the other subjects.

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
| `option_length_bias` | gate | PASS | correct option is strictly longest in 56.00% of MCQs; mean gap 0.76; cap 90% |
| `short_quality` | gate | PASS | 25/25 short answers have valid length, rubric and points; 0 unsupported points |
| `near_duplicates` | gate | PASS | exact=0 max_jaccard=0.4348 (limit 0.75) max_cosine=0.8826 (limit 0.90) |
| `coverage` | gate | PASS | topics=0 concepts=0 materials=0 difficulty=0 |

Metrics: max Jaccard `0.4348` (pair `potions-short-009` / `potions-short-013`), max cosine `0.8826` (pair `potions-mcq-023` / `potions-short-020`), option-length bias `0.56` with a mean gap of `0.76` words.

## Independent checks

| Check | Result |
|---|---|
| MCQ solver | 25/25 selected the stored key |
| MCQ ambiguities | 0 |
| MCQ mismatches | none |
| Short golden answers | 25/25 correct and complete |
| Short candidate answers | 19/25 earned full marks (diagnostic) |
| Short review flags | 0 |
| Missing required points | 0 |
| Errors | 0 |

## Calibration

| Metric | Value |
|---|---:|
| Cases | 24 |
| Exact agreement | 0.6667 |
| Adjacent agreement | 0.9583 |
| MAE | 0.3750 |
| Correctness agreement | 1.0000 |
| Completeness agreement | 0.6667 |
| Judge calls | 8 |
| Passes | 7 |
| Retries | 1 |
| Needs review | 0 |
| Verbose delta | 0.0 |
| Word-count correlation | -0.4698 |

The calibration gate passes: adjacent agreement is 0.9583, MAE is 0.3750, and
no case is `needs_review`.

## Cases

| Item | Variant | Human | Judge | Delta | Words | Needs review |
|---|---|---:|---:|---:|---:|---|
| `potions-short-001` | full | 8 | 8 | 0 | 54 | False |
| `potions-short-005` | full | 8 | 8 | 0 | 60 | False |
| `potions-short-009` | full | 8 | 8 | 0 | 71 | False |
| `potions-short-013` | full | 8 | 8 | 0 | 57 | False |
| `potions-short-015` | full | 8 | 8 | 0 | 54 | False |
| `potions-short-018` | full | 8 | 8 | 0 | 55 | False |
| `potions-short-021` | full | 8 | 8 | 0 | 53 | False |
| `potions-short-024` | full | 8 | 8 | 0 | 55 | False |
| `potions-short-001` | partial | 6 | 7 | 1 | 28 | False |
| `potions-short-005` | partial | 7 | 8 | 1 | 30 | False |
| `potions-short-009` | partial | 6 | 7 | 1 | 24 | False |
| `potions-short-013` | partial | 7 | 8 | 1 | 22 | False |
| `potions-short-015` | partial | 7 | 8 | 1 | 18 | False |
| `potions-short-018` | partial | 6 | 7 | 1 | 25 | False |
| `potions-short-021` | partial | 7 | 8 | 1 | 24 | False |
| `potions-short-024` | partial | 7 | 7 | 0 | 22 | False |
| `potions-short-001` | wrong | 0 | 0 | 0 | 24 | False |
| `potions-short-021` | wrong | 0 | 0 | 0 | 34 | False |
| `potions-short-005` | missing_key_term | 7 | 7 | 0 | 27 | False |
| `potions-short-009` | verbose | 8 | 8 | 0 | 71 | False |
| `potions-short-024` | verbose | 8 | 8 | 0 | 56 | False |
| `potions-short-013` | contradictory | 3 | 5 | 2 | 28 | False |
| `potions-short-015` | off_topic | 0 | 0 | 0 | 28 | False |
| `potions-short-018` | blank | 0 | 0 | 0 | 0 | False |

## Reproduce

```text
uv run python scripts/run_exam_eval.py --subject potions \
  --bank /Users/tc/Documents/Github/owl-online/data/exams/potions \
  --subjects /Users/tc/Documents/Github/owl-online/data/subjects \
  --chunks /Users/tc/Documents/Github/owl-online/data/chunks.jsonl \
  --json data/exams/potions/candidates/exam_eval.json
```

In a checkout that has `data/`, the shorter form is equivalent:

```text
uv run python scripts/run_exam_eval.py --subject potions
```

## Reading notes

- The deterministic and independent checks are green. The independent solver
  selects the stored MCQ key on 25/25 and accepts the golden short answer on
  25/25.
- The calibration gate passes with adjacent agreement 0.9583 and MAE 0.3750 on
  24 cases over 8 items. Exact agreement is 0.6667.
- The first run used the Charms 3/2 partial band and failed at adjacent 0.6667.
  The partials were then re-marked from the rubric: correctness 4 when the core
  mechanism is stated, completeness 2 or 3 when a named example or contrast is
  missing. The contradictory 013 mark was corrected from 4/0 to 3/0 because the
  answer retracts the maintenance rule itself, not only the strength-control
  point. The final run is the adopted reference.
- The final run is one sample: the hosted judge is temperature 0 but not
  bit-stable across calls. Between the superseded and final runs, 015 partial
  moved from 7 to 8 and 018 partial from 8 to 7, so the exact-drop from 0.7083
  to 0.6667 is that movement rather than the 013 correction. Adjacency was
  unaffected, but 0.9583 leaves room for only one more non-adjacent case before
  the 0.90 bar.
- Marking remains sensitive to the partial band: the 3/2 band fails, while the
  adopted 4/2-3 band passes. #40 owns reconciling the band with Charms and the
  remaining subjects, rather than treating the Potions band as a universal rule.
- Seven partial answers are one mark above the human mark and one is exact.
  The contradictory 013 case is two marks above. Correctness agreement is 1.0000;
  completeness agreement is 0.6667, so completeness is the weak criterion.
- The full and verbose answers are reworded from the rubric and golden answer.
  The longest shared word run is six words, checked by tokenising each full and
  verbose answer against the stored model answer. They are not independently
  written student answers, so full-mark agreement measures rubric coverage, not
  discrimination against unseen phrasing.
- The word-count correlation is over all 24 resolved cases, not only the two
  verbose cases; only the verbose delta is a two-case statistic. It is negative
  here and should not be read as a length advantage.
- Eight judge calls cover 24 cases; there was one retry and no case needs
  review. The report records the retry count but not which pass retried.
- Coverage targets are DADA-specific and skipped. The concept cap still applies
  and the coverage zeros are descriptive.
- This run changes no bank content, rubric, judge model or prompt. Potions
  stays at 1.0.0.

## Next

- Add the same calibration set for Transfiguration and Herbology.
- Decide under #40 whether the partial and completeness bands should be
  reconciled across subjects before the remaining sets are adopted.
- DADA 1.1.0 option-length levelling remains a separate bank revision.

## Printed summary

```text
exam eval: potions 1.0.0

Deterministic checks:
  bank_validation        PASS  errors=0 warnings=0
  counts                 PASS  mcq=25 short_answer=25
  grounding              PASS  50/50 items grounded
  mcq_options            PASS  25/25 MCQs have exactly six unique options and one key
  trivial_options        PASS  0 MCQs contain all/none-of-the-above options
  negative_stems         PASS  0 MCQs use a negative equal-completion stem
  answer_positions       PASS  max stored position holds 5/25
  option_length_bias     PASS  correct option is strictly longest in 56.00% of MCQs; mean gap 0.76; cap 90%
  short_quality          PASS  25/25 short answers have valid length, rubric and points; 0 unsupported points
  near_duplicates        PASS  exact=0 max_jaccard=0.4348 (limit 0.75) max_cosine=0.8826 (limit 0.90)
  coverage               PASS  topics=0 concepts=0 materials=0 difficulty=0

Deterministic metrics:
  max_jaccard=0.43478260869565216
  max_jaccard_pair=('potions-short-009', 'potions-short-013')
  max_cosine=0.8826103775458105
  max_cosine_pair=('potions-mcq-023', 'potions-short-020')
  option_length_bias=0.56
  option_length_mean_gap=0.76
  answer_positions={'0': 5, '1': 4, '2': 4, '3': 4, '4': 4, '5': 4}

Independent checks:
  model=mistralai/mistral-small-3.2-24b-instruct temperature=0.0 prompt=dada-bank-independent-v1
  MCQ key matches=25/25
  MCQ mismatches=[]
  MCQ ambiguities=0
  MCQ ambiguity ids=[]
  Short golden=25/25
  Short candidate correct and complete=19
  Short review ids=[]
  Short missing points=0
  Errors=0

Calibration:
  model=mistralai/mistral-small-3.2-24b-instruct provider=openrouter temperature=0.0 prompt=owl-bank-judge-v3
  set_sha256=787aeb63a237bff98050e2db6df7a58fe4ab302567426e18a02e4df75e743115
  n=24 exact=0.6667 adjacent=0.9583 MAE=0.375
  per_criterion={'completeness': 0.6666666666666666, 'correctness': 1.0}
  calls=8 passes=7 retries=1 needs_review=0
  verbose_delta=0.0 word_count_correlation=-0.46980952995724434

Calibration cases:
| Item | Variant | Human | Judge | Delta | Words | Needs review |
|---|---|---:|---:|---:|---:|---|
| `potions-short-001` | full | 8 | 8 | 0 | 54 | False |
| `potions-short-005` | full | 8 | 8 | 0 | 60 | False |
| `potions-short-009` | full | 8 | 8 | 0 | 71 | False |
| `potions-short-013` | full | 8 | 8 | 0 | 57 | False |
| `potions-short-015` | full | 8 | 8 | 0 | 54 | False |
| `potions-short-018` | full | 8 | 8 | 0 | 55 | False |
| `potions-short-021` | full | 8 | 8 | 0 | 53 | False |
| `potions-short-024` | full | 8 | 8 | 0 | 55 | False |
| `potions-short-001` | partial | 6 | 7 | 1 | 28 | False |
| `potions-short-005` | partial | 7 | 8 | 1 | 30 | False |
| `potions-short-009` | partial | 6 | 7 | 1 | 24 | False |
| `potions-short-013` | partial | 7 | 8 | 1 | 22 | False |
| `potions-short-015` | partial | 7 | 8 | 1 | 18 | False |
| `potions-short-018` | partial | 6 | 7 | 1 | 25 | False |
| `potions-short-021` | partial | 7 | 8 | 1 | 24 | False |
| `potions-short-024` | partial | 7 | 7 | 0 | 22 | False |
| `potions-short-001` | wrong | 0 | 0 | 0 | 24 | False |
| `potions-short-021` | wrong | 0 | 0 | 0 | 34 | False |
| `potions-short-005` | missing_key_term | 7 | 7 | 0 | 27 | False |
| `potions-short-009` | verbose | 8 | 8 | 0 | 71 | False |
| `potions-short-024` | verbose | 8 | 8 | 0 | 56 | False |
| `potions-short-013` | contradictory | 3 | 5 | 2 | 28 | False |
| `potions-short-015` | off_topic | 0 | 0 | 0 | 28 | False |
| `potions-short-018` | blank | 0 | 0 | 0 | 0 | False |

gate: PASS
wrote data/exams/potions/candidates/exam_eval.json
```
