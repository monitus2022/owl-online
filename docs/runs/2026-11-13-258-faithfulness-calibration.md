# Run record: #258 lesson faithfulness calibration

- Date: 2026-11-13
- Run id: `20261113T033913Z`
- Ticket: #258 (calibrate the lesson faithfulness judge)
- Config: `rag-calibration`
- Artifacts: `eval/results/rag-calibration-20261113T033913Z.json` (local, gitignored)
- Fixture: `eval/rag/fixtures/faithfulness_calibration.jsonl`, SHA-256 `0cfab6e6b5a1`

## Configuration

| Field | Value |
|---|---|
| Judge | `deepseek/deepseek-v4.1-flash-1017`, temperature 0.0 |
| Prompt | three-level faithfulness rubric (`supported` / `partial` / `unsupported`) |
| Items | 14 total: 13 judged, 1 refusal |
| Label source | agent-proposed; owner review required |
| Labels | 5 supported, 3 partial, 5 unsupported, 1 refusal |

The answers are short synthetic teaching answers. The fixture stores the
question, answer, material ids and chunk ids; the runner loads the published
notes and corpus at run time. No pack prose or corpus text is committed.

## Agreement

| Metric | Value |
|---|---:|
| Exact agreement | 1.0000 |
| Adjacent agreement | 1.0000 |
| Mean absolute error | 0.0000 |
| Parse failures | 0 |
| Refusal check | 1/1 |

## Reading

- The judge agrees with every proposed label on this set, including the partial
  answers. It is not simply marking every teaching-shaped answer unsupported.
- The labels are agent-proposed, not owner-adopted. This run shows the judge is
  usable; it does not close #258. The owner still needs to adopt or correct the
  14 labels before the calibration is pinned as a gate.
- The set is small and synthetic. It should be extended with 5-10 answers from
  real model outputs before the final gate, but those answers must not commit
  pack prose.
- The #248 lesson faithfulness of 2/30 is therefore unlikely to be a simple
  strictness artifact. The next step is #251: tighten the lesson prompt, pass
  the full concept group and bind claims to citations, then measure against
  this calibrated judge.
- The refusal item is checked separately and is not part of the faithfulness
  denominator.

## Reproduce

```
uv run python scripts/run_rag_calibration.py
```

## Raw summary

```text
run_id: 20261113T033913Z
label source: agent-proposed; owner review required
items: 14 judged: 13 refusals: 1
exact agreement: 1.0000
adjacent agreement: 1.0000
mean absolute error: 0.0000
parse failures: 0
gate: PASS
wrote /Users/tc/Documents/Github/owl-online/eval/results/rag-calibration-20261113T033913Z.json
```
