# Run record: #273 DADA calibration re-baseline

- Date: 2026-11-13
- Run id: `exam-20261113-dada-1.1.0` (full eval, recorded in #271), plus probes `exam-20261113-273-rebaseline-1`, `-2`, `-3`
- Ticket: #273 (DADA short-answer judge re-baseline)
- Bank: `dada` 1.1.0
- Config: `dada-bank-exam`
- Artifacts: `eval/exam/fixtures/calibration.jsonl`, `data/exams/dada/candidates/exam_eval-1.1.0.json`, `data/exams/dada/candidates/rebaseline-1.json`, `-2.json`, `-3.json` (local, gitignored)
- Calibration SHA256: `c0d00cb0d557bcbb39048cc910df41942949c2fbaadaa3470bdb75aa72eeb970`
- Judge: `mistralai/mistral-small-3.2-24b-instruct`, `dada-bank-judge-v2`, temperature 0.0
- Runs: one full 1.1.0 eval and three calibration-only probes, all on the same frozen set

## Results

| Run id | Exact | Adjacent | MAE | Correctness | Completeness | Calls | Retries | Needs review | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `exam-20261113-dada-1.1.0` | 0.7083 | 0.9167 | 0.3750 | 0.7083 | 0.7917 | 3 | 0 | 0 | PASS |
| `exam-20261113-273-rebaseline-1` | 0.5833 | 1.0000 | 0.4167 | 0.5833 | 0.6667 | 3 | 0 | 0 | PASS |
| `exam-20261113-273-rebaseline-2` | 0.5833 | 1.0000 | 0.4167 | 0.5833 | 0.6667 | 3 | 0 | 0 | PASS |
| `exam-20261113-273-rebaseline-3` | 0.5833 | 0.8750 | 0.5417 | 0.8333 | 0.6667 | 3 | 0 | 0 | FAIL |

Observed ranges:

| Metric | Range |
|---|---|
| Exact agreement | 0.5833-0.7083 |
| Adjacent agreement | 0.8750-1.0000 |
| MAE | 0.3750-0.5417 |
| Correctness agreement | 0.5833-0.8333 |
| Completeness agreement | 0.6667-0.7917 |

## Reading

- Probes 1 and 2 returned byte-identical calibration blocks and per-case
  scores. The harness does not pass a `JudgeCache`, so this is either a
  reproducible model draw or a replay. The three probe artifacts therefore
  contain one duplicate pair and one distinct outcome, not three independent
  samples. The median over the three probe artifacts is adjacent 1.0000, MAE
  0.4167, exact 0.5833, but that figure is flattered by the duplicate pair; the
  full-run observation is adjacent 0.9167.
- All movement is inside the eight partial answers. The full, wrong, blank,
  off-topic, verbose, missing-key-term and contradictory cases are stable across
  the four runs; the partial pass moves between 3 and 6 marks of 8. Correctness
  agreement is not monotonic with MAE (probe 3 has the highest correctness
  agreement and the worst MAE), so the swing is partial-score severity rather
  than a single criterion. #40 should focus on partial-answer scoring.
- #191's three probes measured adjacent 0.9167-1.0000, MAE 0.4167-0.5000 and
  exact 0.5833. Probes 1-2 reproduce that range; the full run is above on exact
  and below on MAE. Probe 3 is the first observation below the adjacent 0.90
  gate, at 21/24.
- The frozen set and judge pin are unchanged across the four runs. DADA 1.1.0
  changed only MCQ distractor lengths (#271), so no bank-side cause is expected.
- The DADA judge is not stable enough for a single-run 0.90 adjacent gate at
  temperature 0. Lowering the gate to pass 0.8750 would weaken the check without
  fixing the variance.
- Recommended options for #40: adopt a median-of-three protocol for DADA
  calibration (3x judge calls; on this data it gives adjacent 1.0000, MAE
  0.4167, exact 0.5833), or revise the DADA judge prompt/model pin and
  recalibrate. The median buys gate stability, not better scoring.

## Reproduce

```text
uv run python scripts/run_exam_eval.py --subject dada --no-independent \
  --bank /Users/tc/Documents/Github/owl-online/data/exams/dada \
  --subjects /Users/tc/Documents/Github/owl-online/data/subjects \
  --chunks /Users/tc/Documents/Github/owl-online/data/chunks.jsonl \
  --json data/exams/dada/candidates/rebaseline-1.json
```

Repeat with `--json .../rebaseline-2.json` and `.../rebaseline-3.json`. The full
1.1.0 eval uses the same command without `--no-independent`; its printed block is
in `docs/runs/2026-11-13-271-dada-1.1.0.md`.

## Raw summaries

### `exam-20261113-273-rebaseline-1`

```text
Calibration:
  model=mistralai/mistral-small-3.2-24b-instruct provider=openrouter temperature=0.0 prompt=dada-bank-judge-v2
  set_sha256=c0d00cb0d557bcbb39048cc910df41942949c2fbaadaa3470bdb75aa72eeb970
  n=24 exact=0.5833 adjacent=1.0000 MAE=0.4166666666666667
  per_criterion={'completeness': 0.6666666666666666, 'correctness': 0.5833333333333334}
  calls=3 passes=3 retries=0 needs_review=0
  verbose_delta=0.0 word_count_correlation=0.35133957570781094

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
| `dada-short-001` | partial | 5 | 4 | -1 | 17 | False |
| `dada-short-004` | partial | 5 | 4 | -1 | 22 | False |
| `dada-short-006` | partial | 5 | 4 | -1 | 17 | False |
| `dada-short-009` | partial | 5 | 4 | -1 | 24 | False |
| `dada-short-012` | partial | 5 | 4 | -1 | 20 | False |
| `dada-short-014` | partial | 5 | 4 | -1 | 17 | False |
| `dada-short-017` | partial | 5 | 4 | -1 | 17 | False |
| `dada-short-024` | partial | 5 | 4 | -1 | 21 | False |
| `dada-short-001` | wrong | 0 | 0 | 0 | 20 | False |
| `dada-short-004` | missing_key_term | 7 | 8 | 1 | 32 | False |
| `dada-short-006` | verbose | 8 | 8 | 0 | 89 | False |
| `dada-short-009` | contradictory | 1 | 2 | 1 | 33 | False |
| `dada-short-012` | off_topic | 0 | 0 | 0 | 25 | False |
| `dada-short-014` | blank | 0 | 0 | 0 | 0 | False |
| `dada-short-017` | wrong | 0 | 0 | 0 | 20 | False |
| `dada-short-024` | verbose | 8 | 8 | 0 | 100 | False |

gate: PASS
wrote data/exams/dada/candidates/rebaseline-1.json
```

### `exam-20261113-273-rebaseline-2`

```text
Calibration:
  model=mistralai/mistral-small-3.2-24b-instruct provider=openrouter temperature=0.0 prompt=dada-bank-judge-v2
  set_sha256=c0d00cb0d557bcbb39048cc910df41942949c2fbaadaa3470bdb75aa72eeb970
  n=24 exact=0.5833 adjacent=1.0000 MAE=0.4166666666666667
  per_criterion={'completeness': 0.6666666666666666, 'correctness': 0.5833333333333334}
  calls=3 passes=3 retries=0 needs_review=0
  verbose_delta=0.0 word_count_correlation=0.35133957570781094

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
| `dada-short-001` | partial | 5 | 4 | -1 | 17 | False |
| `dada-short-004` | partial | 5 | 4 | -1 | 22 | False |
| `dada-short-006` | partial | 5 | 4 | -1 | 17 | False |
| `dada-short-009` | partial | 5 | 4 | -1 | 24 | False |
| `dada-short-012` | partial | 5 | 4 | -1 | 20 | False |
| `dada-short-014` | partial | 5 | 4 | -1 | 17 | False |
| `dada-short-017` | partial | 5 | 4 | -1 | 17 | False |
| `dada-short-024` | partial | 5 | 4 | -1 | 21 | False |
| `dada-short-001` | wrong | 0 | 0 | 0 | 20 | False |
| `dada-short-004` | missing_key_term | 7 | 8 | 1 | 32 | False |
| `dada-short-006` | verbose | 8 | 8 | 0 | 89 | False |
| `dada-short-009` | contradictory | 1 | 2 | 1 | 33 | False |
| `dada-short-012` | off_topic | 0 | 0 | 0 | 25 | False |
| `dada-short-014` | blank | 0 | 0 | 0 | 0 | False |
| `dada-short-017` | wrong | 0 | 0 | 0 | 20 | False |
| `dada-short-024` | verbose | 8 | 8 | 0 | 100 | False |

gate: PASS
wrote data/exams/dada/candidates/rebaseline-2.json
```

### `exam-20261113-273-rebaseline-3`

```text
Calibration:
  model=mistralai/mistral-small-3.2-24b-instruct provider=openrouter temperature=0.0 prompt=dada-bank-judge-v2
  set_sha256=c0d00cb0d557bcbb39048cc910df41942949c2fbaadaa3470bdb75aa72eeb970
  n=24 exact=0.5833 adjacent=0.8750 MAE=0.5416666666666666
  per_criterion={'completeness': 0.6666666666666666, 'correctness': 0.8333333333333334}
  calls=3 passes=3 retries=0 needs_review=0
  verbose_delta=0.0 word_count_correlation=0.362431122317357

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
| `dada-short-006` | partial | 5 | 3 | -2 | 17 | False |
| `dada-short-009` | partial | 5 | 4 | -1 | 24 | False |
| `dada-short-012` | partial | 5 | 4 | -1 | 20 | False |
| `dada-short-014` | partial | 5 | 4 | -1 | 17 | False |
| `dada-short-017` | partial | 5 | 4 | -1 | 17 | False |
| `dada-short-024` | partial | 5 | 4 | -1 | 21 | False |
| `dada-short-001` | wrong | 0 | 0 | 0 | 20 | False |
| `dada-short-004` | missing_key_term | 7 | 8 | 1 | 32 | False |
| `dada-short-006` | verbose | 8 | 8 | 0 | 89 | False |
| `dada-short-009` | contradictory | 1 | 2 | 1 | 33 | False |
| `dada-short-012` | off_topic | 0 | 0 | 0 | 25 | False |
| `dada-short-014` | blank | 0 | 0 | 0 | 0 | False |
| `dada-short-017` | wrong | 0 | 0 | 0 | 20 | False |
| `dada-short-024` | verbose | 8 | 8 | 0 | 100 | False |

gate: FAIL
wrote data/exams/dada/candidates/rebaseline-3.json
```
