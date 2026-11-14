# Run record: #279 Transfiguration mid-band calibration

- Date: 2026-11-14
- Run id: `exam-20261114-279-transfiguration-midband-diagnostic`
- Ticket: #279 (add mid-band completeness cases and reconcile calibration bands)
- Bank: `transfiguration` 1.0.0
- Artifacts: `eval/exam/fixtures/calibration-transfiguration.jsonl` (committed), `data/exams/transfiguration/candidates/midband-diagnostic.json` (local, gitignored)
- Human marks: proposed by the AI author from the rubric; the owner's PR approval is the sign-off and adopts them as the calibration reference.

## Configuration

| Field | Value |
|---|---|
| Bank | `transfiguration` 1.0.0 |
| Judge | `mistralai/mistral-small-3.2-24b-instruct` |
| Judge provider | `openrouter` |
| Judge temperature | 0.0 |
| Judge prompt | `owl-bank-judge-v3` |
| Calibration set | `eval/exam/fixtures/calibration-transfiguration.jsonl` |
| Calibration SHA256 | `52b099f579187edb69caad5c15be70fffee79e46051300114c9e7392fb22f3bf` |
| Calibration items | 8 |
| Calibration cases | 26 |
| Calibration repeats | 3 (gate on the median) |
| Gate slice | every case except `partial_mid` (24 cases) |
| Diagnostic slice | `partial_mid` (2 cases) |
| Coverage gate | DADA topic, difficulty and per-material targets skipped; the concept cap still gates |

## Run history

| Run id | Gated band | Cases | Gated exact | Gated adjacent | Gated MAE | Gate | Note |
|---|---|---:|---:|---:|---|---|
| `exam-20261113-cf3e7b00` | 4/0 | 24 | 0.9583 | 1.0000 | 0.0417 | PASS | Adopted run before mid-band cases (#266). |
| `exam-20261114-279-transfiguration-4-2-gated` | 4/0 and 4/2 | 26 | 0.8846 | 0.9615 | 0.1538 | PASS | All-case gate, mid-band included; superseded by the diagnostic split. |
| `exam-20261114-279-transfiguration-midband-diagnostic` | 4/0 and 4/2 | 26 | 0.9167 | 1.0000 | 0.0833 | PASS | Extended set; mid-band diagnostic. |

## What changed

The #266 set tested only a 4/0 partial, where the answer states the correct core and omits the completeness clause entirely. That band is unambiguous, but it does not test partial completeness. An earlier #266 clause-split attempt split every item, including single-clause rubrics, and failed.

This set adds a 4/2 mid-band case on the items whose completeness rubric names two separable elements: `transfiguration-short-001` (illusion contrast versus control) and `022` (slow versus watched). Each answer supplies one element and omits the other, so the rubric-derived mark is 4/2. A 4/3 mark was rejected: one of two named elements is half the criterion, and 4/3 made the cases too close to full to exercise the adjacent gate.

`transfiguration-short-013` was dropped from the mid-band set because the rubric names a tool element but does not operationalise "technique", so a two-element split there was not defensible.

The mid-band is a diagnostic slice: the gate uses the 24 established cases, and the two mid-band cases are reported in their own table. That keeps a known-weak slice from blocking every change before the judge can score it, while still measuring it.

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

Metrics: max Jaccard `0.375`, max cosine `0.8747259592352733`, option-length bias `0.56` with a mean gap of `0.68` words.

## Independent checks

| Check | Result |
|---|---|
| MCQ solver | 25/25 selected the stored key |
| MCQ ambiguities | 0 |
| MCQ mismatches | 0 |
| Short golden answers | 25/25 correct and complete |
| Short candidate answers | 23/25 earned full marks (diagnostic) |
| Short review flags | 0 |
| Missing required points | 0 |
| Errors | 0 |

## Calibration

| Metric | All cases | Gated | Mid-band (diagnostic) |
|---|---:|---:|---:|
| Cases | 26 | 24 | 2 |
| Exact agreement | 0.8846 | 0.9167 | 0.5000 |
| Adjacent agreement | 0.9615 | 1.0000 | 0.5000 |
| MAE | 0.1538 | 0.0833 | 1.0000 |
| Needs review | 0 | 0 | 0 |

| All-case metric | Value |
|---|---:|
| Correctness agreement | 0.9231 |
| Completeness agreement | 0.9231 |
| Judge calls | 26 |
| Passes | 24 |
| Retries | 2 |
| Verbose delta | 0.0 |
| Word-count correlation | 0.0473 |

The gate passes at the median of the gated slice: adjacent agreement
1.0000, MAE 0.0833, and no gated case is `needs_review`.
The mid-band slice is reported separately and does not gate.

## Stability (gate)

| Run | Gated exact | Gated adjacent | Gated MAE | Calls | Retries | Gate |
|---|---:|---:|---:|---:|---|---|
| 1 | 0.9167 | 1.0000 | 0.0833 | 9 | 1 | PASS |
| 2 | 0.9167 | 1.0000 | 0.0833 | 9 | 1 | PASS |
| 3 | 0.8750 | 0.9583 | 0.1667 | 8 | 0 | PASS |

## Mid-band completeness (diagnostic)

| Run | Cases | Exact | Adjacent | MAE | Needs review |
|---|---:|---:|---:|---:|---|
| 1 | 2 | 0.5000 | 0.5000 | 1.0000 | 0 |
| 2 | 2 | 0.5000 | 0.5000 | 1.0000 | 0 |
| 3 | 2 | 1.0000 | 1.0000 | 0.0000 | 0 |

## Cases (representative run 1 of 3)

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
| `transfiguration-short-005` | missing_key_term | 4 | 5 | 1 | 18 | False |
| `transfiguration-short-009` | verbose | 8 | 8 | 0 | 67 | False |
| `transfiguration-short-025` | verbose | 8 | 8 | 0 | 74 | False |
| `transfiguration-short-012` | contradictory | 3 | 2 | -1 | 19 | False |
| `transfiguration-short-013` | off_topic | 0 | 0 | 0 | 21 | False |
| `transfiguration-short-018` | blank | 0 | 0 | 0 | 0 | False |
| `transfiguration-short-001` | partial_mid | 6 | 8 | 2 | 37 | False |
| `transfiguration-short-022` | partial_mid | 6 | 6 | 0 | 14 | False |

## Reading

- The gated set passes at the median (adjacent 1.0000, MAE 0.0833), so the established calibration has not regressed.
- The judge under-scores or over-scores the mid-band in two of three runs; the mid-band exact and adjacent agreement are 0.5000 at the median. This is the honest state: a 4/2 answer is sometimes read as full completeness and sometimes as none.
- The mid-band cases move exact agreement only in the gated run; they cannot flip the adjacent gate because they are excluded from it. Promoting them to the gate requires a judge that can award the intermediate completeness mark.
- No bank, rubric, judge model, judge prompt or gate threshold changed. The 4/0 band is retained for single-clause rubrics.
- Next: a judge-prompt follow-up should target the intermediate completeness award, then this slice can be promoted to the gate.

## Reproduce

```text
uv run python scripts/run_exam_eval.py --subject transfiguration --calibration-repeats 3 \
  --bank /Users/tc/Documents/Github/owl-online/data/exams/transfiguration \
  --subjects /Users/tc/Documents/Github/owl-online/data/subjects \
  --chunks /Users/tc/Documents/Github/owl-online/data/chunks.jsonl \
  --json data/exams/transfiguration/candidates/midband-diagnostic.json
```

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
  Short candidate correct and complete=23
  Short review ids=[]
  Short missing points=0
  Errors=0

Calibration (median of 3 runs):
  model=mistralai/mistral-small-3.2-24b-instruct provider=openrouter temperature=0.0 prompt=owl-bank-judge-v3
  set_sha256=52b099f579187edb69caad5c15be70fffee79e46051300114c9e7392fb22f3bf
  all cases: n=26 exact=0.8846 adjacent=0.9615 MAE=0.1538
  gated:     n=24 exact=0.9167 adjacent=1.0000 MAE=0.0833
  mid-band:  n=2 exact=0.5000 adjacent=0.5000 MAE=1.0000
  per_criterion={'completeness': 0.9230769230769231, 'correctness': 0.9230769230769231}
  calls=26 passes=24 retries=2 needs_review=0
  verbose_delta=0.0 word_count_correlation=0.04729453553930416

Calibration stability (gate uses the gated slice):
| Run | Gated exact | Gated adjacent | Gated MAE | Calls | Retries | Gate |
|---|---:|---:|---:|---:|---|---|
| 1 | 0.9167 | 1.0000 | 0.0833 | 9 | 1 | PASS |
| 2 | 0.9167 | 1.0000 | 0.0833 | 9 | 1 | PASS |
| 3 | 0.8750 | 0.9583 | 0.1667 | 8 | 0 | PASS |

Mid-band completeness (diagnostic, not gated):
| Run | Cases | Exact | Adjacent | MAE | Needs review |
|---|---:|---:|---:|---:|---|
| 1 | 2 | 0.5000 | 0.5000 | 1.0000 | 0 |
| 2 | 2 | 0.5000 | 0.5000 | 1.0000 | 0 |
| 3 | 2 | 1.0000 | 1.0000 | 0.0000 | 0 |

Calibration cases (representative run 1 of 3: exact=0.8846 adjacent=0.9615 MAE=0.1538):
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
| `transfiguration-short-005` | missing_key_term | 4 | 5 | 1 | 18 | False |
| `transfiguration-short-009` | verbose | 8 | 8 | 0 | 67 | False |
| `transfiguration-short-025` | verbose | 8 | 8 | 0 | 74 | False |
| `transfiguration-short-012` | contradictory | 3 | 2 | -1 | 19 | False |
| `transfiguration-short-013` | off_topic | 0 | 0 | 0 | 21 | False |
| `transfiguration-short-018` | blank | 0 | 0 | 0 | 0 | False |
| `transfiguration-short-001` | partial_mid | 6 | 8 | 2 | 37 | False |
| `transfiguration-short-022` | partial_mid | 6 | 6 | 0 | 14 | False |

gate: PASS
wrote data/exams/transfiguration/candidates/midband-diagnostic.json
```
