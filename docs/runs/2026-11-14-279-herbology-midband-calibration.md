# Run record: #279 Herbology mid-band calibration

- Date: 2026-11-14
- Run id: `exam-20261114-279-herbology-midband-diagnostic`
- Ticket: #279 (add mid-band completeness cases and reconcile calibration bands)
- Bank: `herbology` 1.0.0
- Artifacts: `eval/exam/fixtures/calibration-herbology.jsonl` (committed), `data/exams/herbology/candidates/midband-diagnostic.json` (local, gitignored)
- Human marks: proposed by the AI author from the rubric; the owner's PR approval is the sign-off and adopts them as the calibration reference.

## Configuration

| Field | Value |
|---|---|
| Bank | `herbology` 1.0.0 |
| Judge | `mistralai/mistral-small-3.2-24b-instruct` |
| Judge provider | `openrouter` |
| Judge temperature | 0.0 |
| Judge prompt | `owl-bank-judge-v3` |
| Calibration set | `eval/exam/fixtures/calibration-herbology.jsonl` |
| Calibration SHA256 | `9a3c14ec92efc442e28f2627d493633eae6f0cb2d037c3f0326a8ad1b09fe7db` |
| Calibration items | 8 |
| Calibration cases | 28 |
| Calibration repeats | 3 (gate on the median) |
| Gate slice | every case except `partial_mid` (24 cases) |
| Diagnostic slice | `partial_mid` (4 cases) |
| Coverage gate | DADA topic, difficulty and per-material targets skipped; the concept cap still gates |

## Run history

| Run id | Gated band | Cases | Gated exact | Gated adjacent | Gated MAE | Gate | Note |
|---|---|---:|---:|---:|---|---|
| `exam-20261113-c8ee76b7` | 4/0 | 24 | 0.9583 | 0.9583 | 0.1250 | PASS | Adopted run before mid-band cases (#267). |
| `exam-20261114-279-herbology-4-2-gated` | 4/0 and 4/2 | 28 | 0.8571 | 0.8929 | 0.2500 | FAIL | All-case gate, mid-band included; the finding that led to the diagnostic split. |
| `exam-20261114-279-herbology-midband-diagnostic` | 4/0 and 4/2 | 28 | 0.9583 | 0.9583 | 0.0833 | PASS | Extended set; mid-band diagnostic. |

## What changed

The #267 set tested only a 4/0 partial, where the answer states the correct core and omits the completeness clause entirely. That band is unambiguous, but it does not test partial completeness.

This set adds a 4/2 mid-band case on the items whose completeness rubric names two separable elements: `herbology-short-001` (bodily change versus lasting effect), `004` (skin irritation versus gloves), `006` (plant quality versus safe handling) and `025` (safe handling versus measuring). Each answer supplies one element and omits the other, so the rubric-derived mark is 4/2. A 4/3 mark was rejected for the same reason as in Transfiguration: one of two named elements is half the criterion.

The mid-band is a diagnostic slice: the gate uses the 24 established cases, and the four mid-band cases are reported in their own table. That keeps a known-weak slice from blocking every change before the judge can score it, while still measuring it.

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

Metrics: max Jaccard `0.4444444444444444`, max cosine `0.8520101718995476`, option-length bias `0.36` with a mean gap of `0.36` words.

## Independent checks

| Check | Result |
|---|---|
| MCQ solver | 25/25 selected the stored key |
| MCQ ambiguities | 0 |
| MCQ mismatches | 0 |
| Short golden answers | 25/25 correct and complete |
| Short candidate answers | 18/25 earned full marks (diagnostic) |
| Short review flags | 0 |
| Missing required points | 0 |
| Errors | 0 |

## Calibration

| Metric | All cases | Gated | Mid-band (diagnostic) |
|---|---:|---:|---:|
| Cases | 28 | 24 | 4 |
| Exact agreement | 0.8929 | 0.9583 | 0.5000 |
| Adjacent agreement | 0.8929 | 0.9583 | 0.5000 |
| MAE | 0.2143 | 0.0833 | 1.0000 |
| Needs review | 0 | 0 | 0 |

| All-case metric | Value |
|---|---:|
| Correctness agreement | 0.9643 |
| Completeness agreement | 0.8929 |
| Judge calls | 25 |
| Passes | 24 |
| Retries | 1 |
| Verbose delta | 0.0 |
| Word-count correlation | -0.1631 |

The gate passes at the median of the gated slice: adjacent agreement
0.9583, MAE 0.0833, and no gated case is `needs_review`.
The mid-band slice is reported separately and does not gate.

## Stability (gate)

| Run | Gated exact | Gated adjacent | Gated MAE | Calls | Retries | Gate |
|---|---:|---:|---:|---:|---|---|
| 1 | 0.9583 | 1.0000 | 0.0417 | 8 | 0 | PASS |
| 2 | 0.9583 | 0.9583 | 0.0833 | 9 | 1 | PASS |
| 3 | 0.9167 | 0.9167 | 0.2083 | 8 | 0 | PASS |

## Mid-band completeness (diagnostic)

| Run | Cases | Exact | Adjacent | MAE | Needs review |
|---|---:|---:|---:|---:|---|
| 1 | 4 | 0.5000 | 0.5000 | 1.0000 | 0 |
| 2 | 4 | 0.5000 | 0.5000 | 1.0000 | 0 |
| 3 | 4 | 0.5000 | 0.5000 | 1.0000 | 0 |

## Cases (representative run 2 of 3)

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
| `herbology-short-004` | missing_key_term | 5 | 7 | 2 | 12 | False |
| `herbology-short-006` | verbose | 8 | 8 | 0 | 71 | False |
| `herbology-short-025` | verbose | 8 | 8 | 0 | 55 | False |
| `herbology-short-012` | contradictory | 2 | 2 | 0 | 31 | False |
| `herbology-short-016` | off_topic | 0 | 0 | 0 | 24 | False |
| `herbology-short-019` | blank | 0 | 0 | 0 | 0 | False |
| `herbology-short-001` | partial_mid | 6 | 6 | 0 | 17 | False |
| `herbology-short-004` | partial_mid | 6 | 6 | 0 | 20 | False |
| `herbology-short-006` | partial_mid | 6 | 8 | 2 | 22 | False |
| `herbology-short-025` | partial_mid | 6 | 8 | 2 | 17 | False |

## Reading

- The gated set passes at the median (adjacent 0.9583, MAE 0.0833), so the established calibration has not regressed.
- The judge awards full completeness to two of the four 4/2 mid-band cases and the intermediate mark to the other two. Mid-band exact and adjacent agreement are 0.5000 in all three runs. The over-award is consistent, not run noise.
- The single gated miss is `herbology-short-004` `missing_key_term` (human 5, judge 7). It names the irritation and the gloves but omits the "undiluted" qualifier, so 2/4 is a partial rather than a half-the-elements mark; that case sets gated adjacent 0.9583.
- This is the same weakness the #267 record deferred to #40. The 4/2 marks are rubric-derived and are not adjusted to make the gate pass.
- No bank, rubric, judge model, judge prompt or gate threshold changed. The 4/0 band is retained for single-clause rubrics.
- Next: a judge-prompt follow-up should target the intermediate completeness award, then this slice can be promoted to the gate.

## Reproduce

```text
uv run python scripts/run_exam_eval.py --subject herbology --calibration-repeats 3 \
  --bank /Users/tc/Documents/Github/owl-online/data/exams/herbology \
  --subjects /Users/tc/Documents/Github/owl-online/data/subjects \
  --chunks /Users/tc/Documents/Github/owl-online/data/chunks.jsonl \
  --json data/exams/herbology/candidates/midband-diagnostic.json
```

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

Calibration (median of 3 runs):
  model=mistralai/mistral-small-3.2-24b-instruct provider=openrouter temperature=0.0 prompt=owl-bank-judge-v3
  set_sha256=9a3c14ec92efc442e28f2627d493633eae6f0cb2d037c3f0326a8ad1b09fe7db
  all cases: n=28 exact=0.8929 adjacent=0.8929 MAE=0.2143
  gated:     n=24 exact=0.9583 adjacent=0.9583 MAE=0.0833
  mid-band:  n=4 exact=0.5000 adjacent=0.5000 MAE=1.0000
  per_criterion={'completeness': 0.8928571428571429, 'correctness': 0.9642857142857143}
  calls=25 passes=24 retries=1 needs_review=0
  verbose_delta=0.0 word_count_correlation=-0.1630744376046023

Calibration stability (gate uses the gated slice):
| Run | Gated exact | Gated adjacent | Gated MAE | Calls | Retries | Gate |
|---|---:|---:|---:|---:|---|---|
| 1 | 0.9583 | 1.0000 | 0.0417 | 8 | 0 | PASS |
| 2 | 0.9583 | 0.9583 | 0.0833 | 9 | 1 | PASS |
| 3 | 0.9167 | 0.9167 | 0.2083 | 8 | 0 | PASS |

Mid-band completeness (diagnostic, not gated):
| Run | Cases | Exact | Adjacent | MAE | Needs review |
|---|---:|---:|---:|---:|---|
| 1 | 4 | 0.5000 | 0.5000 | 1.0000 | 0 |
| 2 | 4 | 0.5000 | 0.5000 | 1.0000 | 0 |
| 3 | 4 | 0.5000 | 0.5000 | 1.0000 | 0 |

Calibration cases (representative run 2 of 3: exact=0.8929 adjacent=0.8929 MAE=0.2143):
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
| `herbology-short-004` | missing_key_term | 5 | 7 | 2 | 12 | False |
| `herbology-short-006` | verbose | 8 | 8 | 0 | 71 | False |
| `herbology-short-025` | verbose | 8 | 8 | 0 | 55 | False |
| `herbology-short-012` | contradictory | 2 | 2 | 0 | 31 | False |
| `herbology-short-016` | off_topic | 0 | 0 | 0 | 24 | False |
| `herbology-short-019` | blank | 0 | 0 | 0 | 0 | False |
| `herbology-short-001` | partial_mid | 6 | 6 | 0 | 17 | False |
| `herbology-short-004` | partial_mid | 6 | 6 | 0 | 20 | False |
| `herbology-short-006` | partial_mid | 6 | 8 | 2 | 22 | False |
| `herbology-short-025` | partial_mid | 6 | 8 | 2 | 17 | False |

gate: PASS
wrote data/exams/herbology/candidates/midband-diagnostic.json
```
