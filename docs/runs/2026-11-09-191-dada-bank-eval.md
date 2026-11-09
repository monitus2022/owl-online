# Run record: #191 DADA bank evaluation

- Date: 2026-11-09
- Run id: `exam-20261109-c0d00cb0`
- Ticket: #191 (DADA bank quality evaluation and short-answer judge calibration)
- Bank: `dada` 1.0.0
- Artifacts: `eval/exam/fixtures/calibration.jsonl` (committed), `data/exams/dada/candidates/exam_eval.json` (local, gitignored)
- Human marks: proposed by the AI author from the rubric; the owner's approval of the #191 PR is the sign-off.

## Configuration

| Field | Value |
|---|---|
| Bank | `dada` 1.0.0 |
| Pack | 1.0.0 / `e7139cbcc23eaa5c` |
| Bank index hash | `aca4c57462d449f5` |
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
| `mcq_options` | gate | PASS | 25/25 MCQs have six unique options and one key |
| `answer_positions` | gate | PASS | max stored position holds 5/25 |
| `option_length_bias` | diagnostic | WARN | correct option is longest in 88.00% of MCQs; mean gap 1.28 |
| `short_quality` | gate | PASS | 25/25 short answers have valid length, rubric and points; 0 unsupported points |
| `near_duplicates` | gate | PASS | exact=0 max_jaccard=0.4545 max_cosine=0.8772 |
| `coverage` | gate | PASS | topics=0 concepts=0 materials=0 difficulty=0 |

Metrics: max Jaccard `0.4545`, max cosine `0.8772`, option-length bias `0.88` with a mean gap of `1.28` words.

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
|---|---:|
| MCQ key matches | 25/25 |
| MCQ ambiguities | 0 |
| Short golden correct and complete | 25/25 |
| Short missing required points | 0 |
| Errors | 0 |

## Calibration

| Metric | Value |
|---|---:|
| Exact agreement | 0.5833 |
| Adjacent agreement | 1.0000 |
| Mean absolute error | 0.4167 |
| Correctness agreement | 0.5833 |
| Completeness agreement | 0.6667 |
| Judge calls | 3 |
| Passes with a call | 3 |
| Retries | 0 |
| Needs review | 0 |
| Verbose mean delta | 0.0 |
| Word-count correlation | -0.0312 |

### Cases

| Item | Variant | Human | Judge | Delta | Needs review |
|---|---|---:|---:|---:|---|
| `dada-short-001` | full | 8 | 8 | 0 | False |
| `dada-short-004` | full | 8 | 8 | 0 | False |
| `dada-short-006` | full | 8 | 8 | 0 | False |
| `dada-short-009` | full | 8 | 8 | 0 | False |
| `dada-short-012` | full | 8 | 8 | 0 | False |
| `dada-short-014` | full | 8 | 8 | 0 | False |
| `dada-short-017` | full | 8 | 8 | 0 | False |
| `dada-short-024` | full | 8 | 8 | 0 | False |
| `dada-short-001` | partial | 5 | 4 | -1 | False |
| `dada-short-004` | partial | 5 | 4 | -1 | False |
| `dada-short-006` | partial | 5 | 4 | -1 | False |
| `dada-short-009` | partial | 5 | 4 | -1 | False |
| `dada-short-012` | partial | 5 | 4 | -1 | False |
| `dada-short-014` | partial | 5 | 4 | -1 | False |
| `dada-short-017` | partial | 5 | 4 | -1 | False |
| `dada-short-024` | partial | 5 | 4 | -1 | False |
| `dada-short-001` | wrong | 0 | 0 | 0 | False |
| `dada-short-004` | missing_key_term | 7 | 8 | 1 | False |
| `dada-short-006` | verbose | 8 | 8 | 0 | False |
| `dada-short-009` | contradictory | 1 | 2 | 1 | False |
| `dada-short-012` | off_topic | 0 | 0 | 0 | False |
| `dada-short-014` | blank | 0 | 0 | 0 | False |
| `dada-short-017` | wrong | 0 | 0 | 0 | False |
| `dada-short-024` | verbose | 8 | 8 | 0 | False |

## Reading

- All gated deterministic checks pass. The option-length diagnostic is the one warning: the correct option is the longest in 88 percent of MCQs, with a mean gap of 1.28 words. The independent solver selected the key on 25/25 and found no second defensible option, so this is a presentation risk for a future bank revision, not an ambiguity in 1.0.0. Written disposition: accept for 1.0.0 and level option lengths in the next bank version.
- The independent model agrees with every MCQ key and finds no ambiguous option. Every short-answer golden answer is judged correct and complete with no missing required points. There are no model-check errors.
- Calibration passes both thresholds: adjacent agreement 1.0000 and MAE 0.4167 on 24 answers over 8 items. Exact agreement is 0.5833 because the judge differs by one mark from the human partial marks on the eight partial answers; the partial-answer split is the refinement target, not a blocker. Correctness agreement is 0.5833 and completeness agreement is 0.6667.
- A second run of the same frozen set (same set hash) measured adjacent 0.9167, MAE 0.5000, exact 0.5833, correctness 0.5833 and completeness 0.9167. The partial-answer marks moved by one or two; the exact agreement and both thresholds held. The judge is temperature 0 but not bit-for-bit deterministic across hosted calls; the adjacent/MAE thresholds are the stable gate.
- There are no retries and no needs_review cases. The verbose answers scored the same as the full answers, the verbose mean delta is 0.0 and the word-count correlation is -0.031, so there is no measured verbosity bias.
- The calibration answers are original student-style responses. The committed set contains no golden answers or corpus prose.
- The human marks are the reference; the owner's PR approval is the sign-off. The set is frozen at the SHA256 above.

## Reproduce

```text
uv run python scripts/run_exam_eval.py --json data/exams/dada/candidates/exam_eval.json
```

## Raw summary

```text
exam eval: dada 1.0.0

Deterministic checks:
  bank_validation        PASS  errors=0 warnings=0
  counts                 PASS  mcq=25 short_answer=25
  grounding              PASS  50/50 items grounded
  mcq_options            PASS  25/25 MCQs have six unique options and one key
  answer_positions       PASS  max stored position holds 5/25
  option_length_bias     WARN (diagnostic)  correct option is longest in 88.00% of MCQs; mean gap 1.28
  short_quality          PASS  25/25 short answers have valid length, rubric and points; 0 unsupported points
  near_duplicates        PASS  exact=0 max_jaccard=0.4545 max_cosine=0.8772
  coverage               PASS  topics=0 concepts=0 materials=0 difficulty=0

Deterministic metrics:
  max_jaccard=0.45454545454545453
  max_cosine=0.877175277200924
  option_length_bias=0.88
  option_length_mean_gap=1.28
  answer_positions={'0': 5, '1': 4, '2': 4, '3': 4, '4': 4, '5': 4}

Independent checks:
  model=mistralai/mistral-small-3.2-24b-instruct temperature=0.0 prompt=dada-bank-independent-v1
  MCQ key matches=25/25
  MCQ ambiguities=0
  Short golden=25/25
  Short missing points=0
  Errors=0

Calibration:
  model=mistralai/mistral-small-3.2-24b-instruct provider=openrouter temperature=0.0 prompt=dada-bank-judge-v2
  set_sha256=c0d00cb0d557bcbb39048cc910df41942949c2fbaadaa3470bdb75aa72eeb970
  n=24 exact=0.5833 adjacent=1.0000 MAE=0.4166666666666667
  per_criterion={'completeness': 0.6666666666666666, 'correctness': 0.5833333333333334}
  calls=3 passes=3 retries=0 needs_review=0
  verbose_delta=0.0 word_count_correlation=-0.03124598115183978

Calibration cases:
| Item | Variant | Human | Judge | Delta | Needs review |
|---|---|---:|---:|---:|---|
| `dada-short-001` | full | 8 | 8 | 0 | False |
| `dada-short-004` | full | 8 | 8 | 0 | False |
| `dada-short-006` | full | 8 | 8 | 0 | False |
| `dada-short-009` | full | 8 | 8 | 0 | False |
| `dada-short-012` | full | 8 | 8 | 0 | False |
| `dada-short-014` | full | 8 | 8 | 0 | False |
| `dada-short-017` | full | 8 | 8 | 0 | False |
| `dada-short-024` | full | 8 | 8 | 0 | False |
| `dada-short-001` | partial | 5 | 4 | -1 | False |
| `dada-short-004` | partial | 5 | 4 | -1 | False |
| `dada-short-006` | partial | 5 | 4 | -1 | False |
| `dada-short-009` | partial | 5 | 4 | -1 | False |
| `dada-short-012` | partial | 5 | 4 | -1 | False |
| `dada-short-014` | partial | 5 | 4 | -1 | False |
| `dada-short-017` | partial | 5 | 4 | -1 | False |
| `dada-short-024` | partial | 5 | 4 | -1 | False |
| `dada-short-001` | wrong | 0 | 0 | 0 | False |
| `dada-short-004` | missing_key_term | 7 | 8 | 1 | False |
| `dada-short-006` | verbose | 8 | 8 | 0 | False |
| `dada-short-009` | contradictory | 1 | 2 | 1 | False |
| `dada-short-012` | off_topic | 0 | 0 | 0 | False |
| `dada-short-014` | blank | 0 | 0 | 0 | False |
| `dada-short-017` | wrong | 0 | 0 | 0 | False |
| `dada-short-024` | verbose | 8 | 8 | 0 | False |

gate: PASS
wrote data/exams/dada/candidates/exam_eval.json
```

