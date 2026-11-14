# Run record: #281 mid-band completeness prompt probe

- Date: 2026-11-14
- Run id: `exam-20261114-281-midband-prompt-probe`
- Ticket: #281 (improve mid-band completeness scoring in the bank judge)
- Subjects: `transfiguration` 1.0.0 and `herbology` 1.0.0
- Config: `transfiguration-bank-exam`, `herbology-bank-exam`
- Artifacts: `data/exams/transfiguration/candidates/prompt-probe-*.json` and `data/exams/herbology/candidates/prompt-probe-*.json` (local, gitignored)
- Judge: `mistralai/mistral-small-3.2-24b-instruct`, provider `openrouter`, `owl-bank-judge-v3`, temperature 0.0
- Method: in-memory append to `JUDGE_SYSTEMS` and `RETRY_SYSTEMS` for the bank's pinned version; no prompt version, bank, rubric or manifest file was edited. Three calibration passes per run, gate on the gated slice. All 18 runs were produced in one process and one session.

## Configuration

| Field | Transfiguration | Herbology |
|---|---|---|
| Calibration set | `calibration-transfiguration.jsonl` | `calibration-herbology.jsonl` |
| Calibration SHA256 | `52b099f579187edb69caad5c15be70fffee79e46051300114c9e7392fb22f3bf` | `9a3c14ec92efc442e28f2627d493633eae6f0cb2d037c3f0326a8ad1b09fe7db` |
| Calibration cases | 26 | 28 |
| Gated cases | 24 | 24 |
| Mid-band cases | 2 | 4 |
| Judge prompt | `owl-bank-judge-v3` | `owl-bank-judge-v3` |
| Repeats | 3 (gate on the median) | 3 (gate on the median) |

The probe passed the synthetic label `set_sha256="probe"` to the harness;
the real fixture hashes are the values above. The saved probe supersedes the
unsaved first draft in this ticket: the direction of every conclusion held,
but the numbers changed, so this record is the canonical one.

## Candidates

Candidate 1 appended this to the judge and retry systems:

```text
 When a rubric criterion names more than one element, award marks only for
 the elements the answer actually supplies. Do not award full marks for a
 criterion unless every element it names is addressed. If a criterion names
 two elements and the answer supplies one, award half of that criterion's marks.
```

Candidate 2 replaced that with a reasoning instruction:

```text
 For each criterion, use the `reason` field to name the elements of the
 criterion that the answer supplies and the elements it omits. Then set
 `awarded` from those elements only. If the criterion names two elements and
 the answer supplies one, award half of that criterion's marks; never award
 full marks unless every named element is supplied.
```

## Results

| Subject | Candidate | Gated exact | Gated adjacent | Gated MAE | Gate | Mid exact | Mid adjacent | Mid MAE |
|---|---|---:|---:|---:|---|---:|---:|---:|
| Transfiguration | baseline | 0.9167 | 1.0000 | 0.0833 | PASS | 0.5000 | 0.5000 | 1.0000 |
| Transfiguration | candidate1 | 0.9583 | 1.0000 | 0.0417 | PASS | 1.0000 | 1.0000 | 0.0000 |
| Transfiguration | candidate2 | 0.5833 | 0.6667 | 0.7500 | FAIL | 1.0000 | 1.0000 | 0.0000 |
| Herbology | baseline | 0.9167 | 0.9583 | 0.1250 | PASS | 0.7500 | 0.7500 | 0.5000 |
| Herbology | candidate1 | 0.9167 | 0.9583 | 0.1250 | PASS | 0.5000 | 0.5000 | 1.0000 |
| Herbology | candidate2 | 0.9167 | 0.9167 | 0.2083 | PASS | 0.5000 | 0.5000 | 1.0000 |

The mid-band human total is 6 of 8. The judge usually returns 6 or 8, so exact
and adjacent often coincide, but it can return 7, which is adjacent but not
exact (Transfiguration candidate 2, run 3). Treat exact as the primary signal
and adjacent as a one-mark tolerance; they are not independent.

## Mechanism

The per-criterion agreement below is over all cases (26 and 28), not the gated
slice; the gated exact is computed after excluding the mid-band rows.

| Subject | Candidate | Correctness agreement | Completeness agreement |
|---|---|---:|---:|
| Transfiguration | baseline | 0.9231 | 0.9615 |
| Transfiguration | candidate1 | 0.9615 | 1.0000 |
| Transfiguration | candidate2 | 0.6154 | 1.0000 |
| Herbology | baseline | 0.9643 | 0.9286 |
| Herbology | candidate1 | 0.9643 | 0.8929 |
| Herbology | candidate2 | 0.9643 | 0.8929 |

Candidate 2 on Transfiguration scored all eight gated 4/0 `partial` cases at
total 2 (human 4, delta -2) while completeness agreement rose to 1.0000. The
blanket half rule was applied to the correctness criterion, not only to
completeness, which explains both the gated exact collapse and the apparent
mid-band lift. The trigger is specific to candidate 2's element-reasoning
instruction on the Transfiguration cases: candidate 1 carried the same half rule
and did not halve correctness, and Herbology's gated `partial` cases were
unchanged under both candidates.

## Per-run mid-band

| Subject | Candidate | Run | Gated exact | Gated adjacent | Mid exact | Mid adjacent |
|---|---|---:|---:|---:|---:|---:|
| Transfiguration | baseline | 1 | 0.9167 | 1.0000 | 1.0000 | 1.0000 |
| Transfiguration | baseline | 2 | 0.9583 | 1.0000 | 0.5000 | 0.5000 |
| Transfiguration | baseline | 3 | 0.8750 | 0.9583 | 0.5000 | 0.5000 |
| Transfiguration | candidate1 | 1 | 0.9583 | 1.0000 | 0.5000 | 0.5000 |
| Transfiguration | candidate1 | 2 | 0.9167 | 1.0000 | 1.0000 | 1.0000 |
| Transfiguration | candidate1 | 3 | 0.9583 | 1.0000 | 1.0000 | 1.0000 |
| Transfiguration | candidate2 | 1 | 0.5833 | 0.6667 | 1.0000 | 1.0000 |
| Transfiguration | candidate2 | 2 | 0.5833 | 0.6667 | 1.0000 | 1.0000 |
| Transfiguration | candidate2 | 3 | 0.5833 | 0.6250 | 0.5000 | 1.0000 |
| Herbology | baseline | 1 | 0.9167 | 0.9583 | 0.7500 | 0.7500 |
| Herbology | baseline | 2 | 0.9167 | 0.9583 | 0.7500 | 0.7500 |
| Herbology | baseline | 3 | 0.9167 | 0.9583 | 0.7500 | 0.7500 |
| Herbology | candidate1 | 1 | 0.9167 | 0.9583 | 0.5000 | 0.5000 |
| Herbology | candidate1 | 2 | 0.8750 | 0.8750 | 0.5000 | 0.5000 |
| Herbology | candidate1 | 3 | 0.9583 | 1.0000 | 0.5000 | 0.5000 |
| Herbology | candidate2 | 1 | 0.9167 | 0.9167 | 0.5000 | 0.5000 |
| Herbology | candidate2 | 2 | 0.9583 | 1.0000 | 0.5000 | 0.5000 |
| Herbology | candidate2 | 3 | 0.9167 | 0.9167 | 0.5000 | 0.5000 |

## Mid-band cases (representative run)

| Subject | Candidate | Representative run | Item | Human | Judge | Delta |
|---|---|---|---|---:|---:|---:|
| Transfiguration | baseline | 2 | `transfiguration-short-001` | 6 | 8 | 2 |
| Transfiguration | baseline | 2 | `transfiguration-short-022` | 6 | 6 | 0 |
| Transfiguration | candidate1 | 2 | `transfiguration-short-001` | 6 | 6 | 0 |
| Transfiguration | candidate1 | 2 | `transfiguration-short-022` | 6 | 6 | 0 |
| Transfiguration | candidate2 | 1 | `transfiguration-short-001` | 6 | 6 | 0 |
| Transfiguration | candidate2 | 1 | `transfiguration-short-022` | 6 | 6 | 0 |
| Herbology | baseline | 1 | `herbology-short-001` | 6 | 6 | 0 |
| Herbology | baseline | 1 | `herbology-short-004` | 6 | 8 | 2 |
| Herbology | baseline | 1 | `herbology-short-006` | 6 | 6 | 0 |
| Herbology | baseline | 1 | `herbology-short-025` | 6 | 6 | 0 |
| Herbology | candidate1 | 1 | `herbology-short-001` | 6 | 6 | 0 |
| Herbology | candidate1 | 1 | `herbology-short-004` | 6 | 6 | 0 |
| Herbology | candidate1 | 1 | `herbology-short-006` | 6 | 8 | 2 |
| Herbology | candidate1 | 1 | `herbology-short-025` | 6 | 8 | 2 |
| Herbology | candidate2 | 1 | `herbology-short-001` | 6 | 6 | 0 |
| Herbology | candidate2 | 1 | `herbology-short-004` | 6 | 6 | 0 |
| Herbology | candidate2 | 1 | `herbology-short-006` | 6 | 8 | 2 |
| Herbology | candidate2 | 1 | `herbology-short-025` | 6 | 8 | 2 |

## Reading

- Candidate 1 is not a consistent gain. It moves Transfiguration's two mid-band cases from 0.5000 to 1.0000 exact, but Herbology's four drop from 0.7500 to 0.5000 (one case lower; the per-run table shows the drop is stable at 0.5000 in 3/3 passes). The gated slice is unchanged or slightly better (Transfiguration 0.9167 to 0.9583 exact; Herbology 0.9167 and 0.9583 in both).
- Candidate 2 is rejected on score and mechanism. Transfiguration's gated calibration collapses to exact 0.5833, adjacent 0.6667 and MAE 0.7500, a gate FAIL in 3/3 passes (adjacent 0.6667, 0.6667, 0.6250), and Herbology's gated adjacent drops from 0.9583 to 0.9167. The mechanism table shows why: the rule halves the correctness criterion on every gated 4/0 partial.
- The mid-band baseline is not stable across sessions. Herbology drew 0.5000 in the first ad-hoc probe and 0.7500 here with the same prompt; Transfiguration's per-run mid count ranged 0.5000-1.0000. With four and two cases, the slice cannot support a fine-grained prompt comparison; the per-run table is the evidence.
- The promotion bar cannot be adjacent alone. A judge that returns 7 on every mid-band case scores exact 0.0000, adjacent 1.0000 and no needs_review, which clears the current gate. Any future promotion of this slice must include exact, or an exact floor, so a uniform over-award cannot pass.
- A few-shot example was not tried. Four mid-band cases leave no held-out case to validate an example against, so an example would be tuned to the same cases it is measured on. The ticket allows a prompt or few-shot change; a prompt-only probe satisfies the scope.
- Decision: keep `owl-bank-judge-v3` and `dada-bank-judge-v2` pinned, keep the mid-band as a diagnostic, and leave a judge change to a future ticket with a larger held-out set. No code, prompt version, bank, rubric or manifest change is part of this result.

## Reproduce

The probe used an in-memory append, not a committed prompt version:

```text
judge.JUDGE_SYSTEMS[version] = judge.JUDGE_SYSTEMS[version] + CANDIDATE
judge.RETRY_SYSTEMS[version] = judge.RETRY_SYSTEMS[version] + CANDIDATE
run_calibration_repeated(bank, cases, judge_llm_from_bank(bank), repeats=3)
```

The version is the bank's `judge_prompt_version` (`owl-bank-judge-v3` for
both subjects). The original strings were restored after each run. The
saved JSON artifacts hold the per-run and per-case detail.

## Ad-hoc probe output (not render_report)

```text
transfiguration baseline gated 24 0.9167 1.0000 0.0833 mid 2 0.5000 0.5000 1.0000 calls 27 retries 3 gated_needs 0 mid_needs 0 gate PASS
transfiguration candidate1 gated 24 0.9583 1.0000 0.0417 mid 2 1.0000 1.0000 0.0000 calls 26 retries 2 gated_needs 0 mid_needs 0 gate PASS
transfiguration candidate2 gated 24 0.5833 0.6667 0.7500 mid 2 1.0000 1.0000 0.0000 calls 25 retries 1 gated_needs 0 mid_needs 0 gate FAIL
herbology baseline gated 24 0.9167 0.9583 0.1250 mid 4 0.7500 0.7500 0.5000 calls 24 retries 0 gated_needs 0 mid_needs 0 gate PASS
herbology candidate1 gated 24 0.9167 0.9583 0.1250 mid 4 0.5000 0.5000 1.0000 calls 26 retries 2 gated_needs 0 mid_needs 0 gate PASS
herbology candidate2 gated 24 0.9167 0.9167 0.2083 mid 4 0.5000 0.5000 1.0000 calls 27 retries 3 gated_needs 0 mid_needs 0 gate PASS
```
