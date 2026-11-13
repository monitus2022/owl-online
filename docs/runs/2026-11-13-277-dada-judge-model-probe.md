# Run record: #277 DADA judge model probe

- Date: 2026-11-13
- Run id: `exam-20261113-277-judge-probe`
- Ticket: #277 (probe alternative DADA judge models)
- Bank: `dada` 1.1.0
- Config: `dada-bank-exam`
- Artifacts: `data/exams/dada/candidates/median-calibration.json` (Small baseline from #275), `data/exams/dada/candidates/judge-model-qwen.json`, `data/exams/dada/candidates/judge-model-medium.json` (local, gitignored)
- Calibration set: `eval/exam/fixtures/calibration.jsonl`
- Calibration SHA256: `c0d00cb0d557bcbb39048cc910df41942949c2fbaadaa3470bdb75aa72eeb970`
- Provider: OpenRouter
- Prompt: `dada-bank-judge-v2`, temperature 0.0
- Method: in-memory manifest model override; no bank file was edited. Small is the #275 three-pass baseline; Qwen is one pass; Medium is three passes.

## Results

| Model | Passes | Exact | Adjacent | MAE | Correctness | Completeness | Calls | Retries | Needs review | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `mistralai/mistral-small-3.2-24b-instruct` (current) | 3 | 0.6250 | 0.9583 | 0.4167 | 0.7083 | 0.8333 | 9 | 0 | 0 | PASS |
| `qwen/qwen3-32b` | 1 | 0.3750 | 0.7083 | 0.4706 | 0.3750 | 0.3750 | 6 | 3 | 7 | FAIL |
| `mistralai/mistral-medium-3.1` | 3 | 0.5833 | 1.0000 | 0.4167 | 0.5833 | 0.6667 | 9 | 0 | 0 | PASS |

Mistral Small per-run: `(.5833, .9583, .4583)`, `(.6667, .9167, .4167)`,
`(.6250, .9583, .4167)`. Mistral Medium per-run: `(.5833, .9583, .5000)`,
`(.5833, 1.0000, .4167)`, `(.5833, 1.0000, .4167)`.

## Reading

- Qwen3 32B is not a viable drop-in judge. Its three pass-group calls all
  triggered retries, and 7 of 24 cases still ended in `needs_review`. Exact and
  adjacent agreement are depressed because unresolved cases stay in the
  denominator; the MAE is computed over the 17 resolved cases only. One pass is
  enough to reject it because the failure is structural: repeating the same
  schema-invalid output cannot make it parse.
- Mistral Medium 3.1 is parse-compliant and its median adjacent is 1.0000 with
  the same MAE as Small, but exact agreement is lower (0.5833 vs 0.6250). It is
  also a closed-weight model, so the project's model-access rules exclude it
  regardless of the metrics. It is not a candidate.
- Mistral Small stays pinned. The median-of-three protocol remains the
  stabilization mechanism. The probe does not change partial-score variance; a
  prompt revision is still the next quality option.

## Reproduce

The probe used an in-memory `ExamBank.model_copy` override for `judge_model`,
then:

```text
run_calibration_repeated(candidate, cases, llm, repeats=N, set_sha256="probe")
```

Qwen used `N=1`; Medium used `N=3`. The JSON artifacts above hold the full
representative case tables and per-run metrics. The probe passed the synthetic
label `set_sha256="probe"`; the frozen set hash is the declared
`c0d00cb0...` value, and the synthetic label only identifies these local probe
artifacts.

## Raw summary

```text
Ad-hoc probe output (not render_report):
qwen/qwen3-32b elapsed 436.5 exact 0.375 adjacent 0.7083333333333334 mae 0.47058823529411764 per {'completeness': 0.375, 'correctness': 0.375} calls 6 retries 3 needs 7
 run 1 0.375 0.7083333333333334 0.47058823529411764 False
mistralai/mistral-medium-3.1 elapsed 70.8 exact 0.5833333333333334 adjacent 1.0 mae 0.4166666666666667 per {'completeness': 0.6666666666666666, 'correctness': 0.5833333333333334} calls 9 retries 0 needs 0
 run 1 0.5833333333333334 0.9583333333333334 0.5 True
 run 2 0.5833333333333334 1.0 0.4166666666666667 True
 run 3 0.5833333333333334 1.0 0.4166666666666667 True
```

## Recommendation

Keep `mistralai/mistral-small-3.2-24b-instruct` and the median-of-three
protocol. Do not change the judge model. If partial scoring still needs work,
revise the DADA prompt and recalibrate on the frozen set.
