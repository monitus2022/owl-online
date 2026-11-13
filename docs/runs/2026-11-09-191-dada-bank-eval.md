# Run record: #191 DADA bank evaluation

- Date: 2026-11-09
- Run id: `exam-20261109-c0d00cb0`
- Ticket: #191 (DADA bank quality evaluation and short-answer judge calibration)
- Bank: `dada` 1.0.0
- Artifacts: `eval/exam/fixtures/calibration.jsonl` (committed), `data/exams/dada/candidates/exam_eval.json` (local, gitignored)
- Human marks: proposed by the AI author from the rubric; the owner's approval of the #191 PR is the sign-off and adopts them as the calibration reference.

## Configuration

| Field | Value |
|---|---|
| Bank | `dada` 1.0.0 |
| Pack | 1.0.0 / `e7139cbcc23eaa5c` |
| Bank index hash | `aca4c57462d449f5` |
| Rubric version | `dada-bank-v1` |
| Judge | `mistralai/mistral-small-3.2-24b-instruct` |
| Judge provider | `openrouter` |
| Judge temperature | 0.0 |
| Judge prompt | `dada-bank-judge-v2` |
| Independent prompt | `dada-bank-independent-v1` |
| Embedder | `qwen3-embedding:0.6b` (local) |
| Calibration set | `eval/exam/fixtures/calibration.jsonl` |
| Calibration SHA256 | `c0d00cb0d557bcbb39048cc910df41942949c2fbaadaa3470bdb75aa72eeb970` |
| Calibration items | 8 |
| Calibration cases | 24 |

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
| `option_length_bias` | gate | PASS | correct option is strictly longest in 80.00% of MCQs; mean gap 1.28; cap 90% |
| `short_quality` | gate | PASS | 25/25 short answers have valid length, rubric and points; 0 unsupported points |
| `near_duplicates` | gate | PASS | exact=0 max_jaccard=0.4545 (limit 0.75) max_cosine=0.8772 (limit 0.90) |
| `coverage` | gate | PASS | topics=0 concepts=0 materials=0 difficulty=0 |

Metrics: max Jaccard `0.4545` (pair `['dada-mcq-014', 'dada-mcq-024']`), max cosine `0.8772` (pair `['dada-short-016', 'dada-short-018']`), option-length bias `0.80` with a mean gap of `1.28` words.

### Topic coverage

| Topic | MCQ | Short answer |
|---|---:|---:|
| `dark-arts` | 4 | 4 |
| `dark-creatures` | 10 | 10 |
| `defensive-magic` | 9 | 9 |
| `dueling` | 2 | 2 |

### Concept coverage

| Concept | MCQ | Short answer |
|---|---:|---:|
| `dada-creature-boggart` | 2 | 2 |
| `dada-creature-dementors` | 1 | 1 |
| `dada-creature-grim` | 1 | 1 |
| `dada-creature-grindylow` | 1 | 1 |
| `dada-creature-pixie` | 1 | 1 |
| `dada-creature-thestral` | 1 | 1 |
| `dada-creature-werewolf` | 2 | 2 |
| `dada-magic-boggart-banishing-spell` | 1 | 1 |
| `dada-magic-concealment-charm` | 1 | 1 |
| `dada-magic-corporeal-patronus` | 1 | 1 |
| `dada-magic-countercurse` | 1 | 1 |
| `dada-magic-cruciatus-curse` | 1 | 1 |
| `dada-magic-disarming-charm` | 1 | 1 |
| `dada-magic-fidelius-charm` | 1 | 1 |
| `dada-magic-hex-deflection` | 1 | 1 |
| `dada-magic-imperius-curse` | 1 | 1 |
| `dada-magic-killing-curse` | 1 | 1 |
| `dada-magic-patronus` | 2 | 2 |
| `dada-magic-shield-charm` | 2 | 2 |
| `dada-magic-stunning-spell` | 1 | 1 |
| `dada-magic-unforgivable-curses` | 1 | 1 |

### Difficulty

| Difficulty | MCQ | Short answer |
|---|---:|---:|
| application | 4 | 3 |
| comparison | 4 | 5 |
| explanation | 8 | 9 |
| recall | 8 | 8 |
| scenario | 1 | 0 |

### Material coverage

| Material | MCQ | Short answer |
|---|---:|---:|
| `dada-countering-countercurse-doctrine` | 1 | 1 |
| `dada-countering-detection-and-concealment` | 1 | 1 |
| `dada-countering-hex-deflection` | 1 | 1 |
| `dada-dark-arts-cruciatus-evidence` | 1 | 1 |
| `dada-dark-arts-imperius-demonstration` | 1 | 1 |
| `dada-dark-arts-killing-curse-limits` | 1 | 1 |
| `dada-dark-arts-unforgivables-law` | 1 | 1 |
| `dada-dark-creatures-boggarts-counter` | 1 | 1 |
| `dada-dark-creatures-boggarts-field` | 1 | 1 |
| `dada-dark-creatures-boggarts-nature` | 1 | 1 |
| `dada-dark-creatures-dementors-nature` | 1 | 1 |
| `dada-dark-creatures-fieldcraft-pixies` | 1 | 1 |
| `dada-dark-creatures-fieldcraft-thestrals` | 1 | 1 |
| `dada-dark-creatures-fieldcraft-water-and-marsh` | 1 | 1 |
| `dada-dark-creatures-grim-private-fear` | 1 | 1 |
| `dada-dark-creatures-werewolves-law-and-fear` | 1 | 1 |
| `dada-dark-creatures-werewolves-recognition` | 1 | 1 |
| `dada-dueling-disarming-charm` | 1 | 1 |
| `dada-dueling-shield-charm` | 1 | 1 |
| `dada-dueling-stunning-spell` | 1 | 1 |
| `dada-magic-patronus-theory` | 1 | 1 |
| `dada-magic-patronus-training` | 1 | 1 |
| `dada-protective-fidelius-trust` | 1 | 1 |
| `dada-protective-patronus-field` | 1 | 1 |
| `dada-protective-wards-at-scale` | 1 | 1 |

### Answer positions

| Stored index | MCQs |
|---|---:|
| 0 | 5 |
| 1 | 4 |
| 2 | 4 |
| 3 | 4 |
| 4 | 4 |
| 5 | 4 |

## Independent checks

| Check | Result |
|---|---|
| MCQ key matches | 25/25 |
| MCQ mismatch ids | `[]` |
| MCQ ambiguities | 0 |
| MCQ ambiguity ids | `[]` |
| Short golden correct and complete | 25/25 |
| Short candidate correct and complete | 20/25 (diagnostic) |
| Short review ids | `[]` |
| Short missing required points | 0 |
| Errors | 0 |

## Calibration

| Metric | Value |
|---|---:|
| Exact agreement | 0.5833 |
| Adjacent agreement | 0.9167 |
| Mean absolute error | 0.5000 |
| Correctness agreement | 0.5833 |
| Completeness agreement | 0.9167 |
| Judge calls | 4 |
| Passes with a call | 3 |
| Retry rate | 1/3 |
| Needs review | 0 |
| Verbose mean delta | 0.0 |
| Word-count correlation | -0.0707 |

### Cases

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
| `dada-short-004` | partial | 5 | 3 | -2 | 22 | False |
| `dada-short-006` | partial | 5 | 6 | 1 | 17 | False |
| `dada-short-009` | partial | 5 | 6 | 1 | 24 | False |
| `dada-short-012` | partial | 5 | 6 | 1 | 20 | False |
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

## Reading

- All gated deterministic checks pass. The option-length gate passes at 80% against the 90 percent cap, with a mean gap of 1.28 words. The independent solver selected the key on 25/25 and found no second defensible option. The share is high enough to schedule option-length levelling in the next bank revision without treating it as an ambiguity in 1.0.0.
- The independent model agrees with every MCQ key, reports no mismatch or ambiguity ids, and finds every short-answer golden answer correct and complete with no missing required points. The candidate-answer diagnostic is 20/25 correct and complete; the five short candidates that were not complete do not change the golden-answer result. There are no model-check errors.
- Calibration passes both thresholds: adjacent agreement 0.9167 and MAE 0.5000 on 24 answers over 8 items. Exact agreement is 0.5833; the ten non-exact cases are partial 8 (2 at -2, 6 at +1), missing_key_term 1 (+1) and contradictory 1 (+1). Correctness agreement is 0.5833 and completeness agreement is 0.9167; the partial-answer split is the refinement target, not a blocker.
- The final run used 4 judge calls over 3 passes, a retry rate of 1/3, and no needs_review. One pass retried once after an invalid response; the retry succeeded. There is no unreviewed parse failure.
- The verbose answers scored the same as the full answers: verbose mean delta 0.0, word-count correlation -0.0707. The weak negative correlation does not show a verbosity reward or a length penalty; the judge is slightly harsher on the two partial answers `dada-short-001` and `dada-short-004` (delta -2), while the other six partial answers are +1.
- Stability probes on the same frozen set measured adjacent 0.9167 to 1.0000 and MAE 0.4167 to 0.5000 across three runs; exact agreement stayed 0.5833. Those probes are informal and have no separate records; the run above is the recorded run. The hosted judge is temperature 0 but not bit-for-bit deterministic across calls, so the adjacent and MAE thresholds are the stable gate.
- The calibration answers are original student-style responses. The committed set contains no golden answers or corpus prose. The set is frozen at the SHA256 above.
- The human marks are the reference; the owner's PR approval is the sign-off and adopts the AI-proposed marks. The eval gates a strict one-MCQ and one-short-answer per material; the 1.0.0 bank has no recorded slot swaps. The calibration gate treats any needs_review as a failure because a reviewed state is not modelled yet; this run has no needs_review.

## Reproduce

```text
uv run python scripts/run_exam_eval.py --subject dada --calibration-repeats 1 --json data/exams/dada/candidates/exam_eval.json
```

## Raw summary

```text
exam eval: dada 1.0.0

Deterministic checks:
  bank_validation        PASS  errors=0 warnings=0
  counts                 PASS  mcq=25 short_answer=25
  grounding              PASS  50/50 items grounded
  mcq_options            PASS  25/25 MCQs have exactly six unique options and one key
  trivial_options        PASS  0 MCQs contain all/none-of-the-above options
  negative_stems         PASS  0 MCQs use a negative equal-completion stem
  answer_positions       PASS  max stored position holds 5/25
  option_length_bias     PASS  correct option is strictly longest in 80.00% of MCQs; mean gap 1.28; cap 90%
  short_quality          PASS  25/25 short answers have valid length, rubric and points; 0 unsupported points
  near_duplicates        PASS  exact=0 max_jaccard=0.4545 (limit 0.75) max_cosine=0.8772 (limit 0.90)
  coverage               PASS  topics=0 concepts=0 materials=0 difficulty=0

Deterministic metrics:
  max_jaccard=0.45454545454545453
  max_jaccard_pair=('dada-mcq-014', 'dada-mcq-024')
  max_cosine=0.877175277200924
  max_cosine_pair=('dada-short-016', 'dada-short-018')
  option_length_bias=0.8
  option_length_mean_gap=1.28
  answer_positions={'0': 5, '1': 4, '2': 4, '3': 4, '4': 4, '5': 4}

Independent checks:
  model=mistralai/mistral-small-3.2-24b-instruct temperature=0.0 prompt=dada-bank-independent-v1
  MCQ key matches=25/25
  MCQ mismatches=[]
  MCQ ambiguities=0
  MCQ ambiguity ids=[]
  Short golden=25/25
  Short candidate correct and complete=20
  Short review ids=[]
  Short missing points=0
  Errors=0

Calibration:
  model=mistralai/mistral-small-3.2-24b-instruct provider=openrouter temperature=0.0 prompt=dada-bank-judge-v2
  set_sha256=c0d00cb0d557bcbb39048cc910df41942949c2fbaadaa3470bdb75aa72eeb970
  n=24 exact=0.5833 adjacent=0.9167 MAE=0.5
  per_criterion={'completeness': 0.9166666666666666, 'correctness': 0.5833333333333334}
  calls=4 passes=3 retries=1 needs_review=0
  verbose_delta=0.0 word_count_correlation=-0.07072124965341807

Calibration cases:
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
| `dada-short-004` | partial | 5 | 3 | -2 | 22 | False |
| `dada-short-006` | partial | 5 | 6 | 1 | 17 | False |
| `dada-short-009` | partial | 5 | 6 | 1 | 24 | False |
| `dada-short-012` | partial | 5 | 6 | 1 | 20 | False |
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
wrote data/exams/dada/candidates/exam_eval.json
```

