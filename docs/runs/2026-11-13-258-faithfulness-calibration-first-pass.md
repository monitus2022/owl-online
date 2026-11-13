# Run record: #258 calibration first pass

- Date: 2026-11-13
- Run id: `20261113T033913Z`
- Ticket: #258 (calibrate the lesson faithfulness judge)
- Config: `rag-calibration`
- Fixture SHA-256: `0cfab6e6b5a1`

## Configuration

| Field | Value |
|---|---|
| Items | 14 total: 13 judged, 1 refusal |
| Slices | in-pack, off-pack only |
| Labels | 6 supported, 3 partial, 4 unsupported, 1 refusal |
| Label source | agent-proposed; owner review required |
| Judge | `deepseek/deepseek-v4.1-flash-1017`, temperature 0.0 |

## Agreement

| Metric | Value |
|---|---:|
| Exact agreement | 1.0000 |
| Adjacent agreement | 1.0000 |
| Mean absolute error | 0.0000 |
| Parse failures | 0 |
| Gate | `PASS` before adoption gating |

## Reading

This pass was too narrow: no paraphrase, multi-concept or mixed items, and the
gate did not require owner adoption. It was superseded by
`20261113T040759Z`; see
`docs/runs/2026-11-13-258-faithfulness-calibration.md`.

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
```
