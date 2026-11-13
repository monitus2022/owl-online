# Run record: #258 lesson faithfulness calibration adopted

- Date: 2026-11-13
- Run id: `20261113T070629Z`
- Ticket: #258 (calibrate the lesson faithfulness judge)
- Config: `rag-calibration`
- Fixture: `eval/rag/fixtures/faithfulness_calibration.jsonl`, SHA-256 `86d6d3c7758d`
- Labels: owner-adopted 2026-11-13

## Configuration

| Field | Value |
|---|---|
| Judge | `deepseek/deepseek-v4.1-flash-1017`, temperature 0.0 |
| Prompt | three-level `faithfulness-label-v1` |
| Production prompt | binary `FAITHFUL_SYSTEM` |
| Items | 18 total: 16 judged, 2 refusals |
| Slices | in-pack, paraphrase, multi-concept, mixed, off-pack |
| Labels | 8 supported, 4 partial, 4 unsupported, 2 refusal |

The owner adopted the 18 proposed labels on 2026-11-13. The fixture stores the
question, answer, material ids and chunk ids; the runner loads the published
notes and corpus at run time.

## Agreement

| Metric | Value |
|---|---:|
| Three-level exact agreement | 1.0000 |
| Three-level adjacent agreement | 1.0000 |
| Three-level mean absolute error | 0.0000 |
| Production binary agreement | 1.0000 |
| Refusal checks | 2/2 |
| Parse failures | 0 |
| Gate | PASS |

## Reading

- The owner adopted the labels and the judge agrees with every one. The gate
  moves from `REVIEW (labels not adopted)` to `PASS`.
- The set covers all five slices and both refusal forms. It is still small and
  synthetic; add 5-10 real model answers before the final release pin, without
  committing extended pack prose.
- #251 can now use this calibration as its faithfulness reference. The target is
  a material improvement over the #248 2/30 baseline, not a judge-specific
  number.

## Reproduce

```
uv run python scripts/run_rag_calibration.py
```

## Raw summary

```text
run_id: 20261113T070629Z
fixture sha: 86d6d3c7758d
label source: owner-adopted 2026-11-13
items: 18 judged: 16 refusals: 2
exact agreement: 1.0000
adjacent agreement: 1.0000
mean absolute error: 0.0000
binary judge agreement: 1.0000
refusal checks: 2/2
labels adopted: True
parse failures: 0
gate: PASS
wrote /Users/tc/Documents/Github/owl-online/eval/results/rag-calibration-20261113T070629Z.json
```
