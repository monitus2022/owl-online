# Run record: #258 calibration pre-fix pass

- Date: 2026-11-13
- Run id: `20261113T035711Z`
- Ticket: #258 (calibrate the lesson faithfulness judge)
- Config: `rag-calibration`
- Fixture SHA-256: `0f1cc196aa03`

## Configuration

| Field | Value |
|---|---|
| Items | 18 total: 16 judged, 2 refusals |
| Slices | in-pack, paraphrase, multi-concept, mixed, off-pack |
| Labels | 8 supported, 4 partial, 4 unsupported, 2 refusal |
| Label source | agent-proposed; owner review required |
| Judge | `deepseek/deepseek-v4.1-flash-1017`, temperature 0.0 |

## Agreement

| Metric | Value |
|---|---:|
| Exact agreement | 1.0000 |
| Adjacent agreement | 1.0000 |
| Mean absolute error | 0.0000 |
| Binary agreement | 1.0000 |
| Refusal recognition | 1/2 |
| Parse failures | 0 |
| Gate | REVIEW (labels not adopted) |

## Reading

This pass added slice coverage and the production binary judge, but one refusal
paraphrase (`cal-18`) was not recognized by the refusal detector. It was
superseded by `20261113T040759Z`, which uses a recognized lesson-refusal form
and gates on refusal and binary agreement.

## Raw summary

```text
run_id: 20261113T035711Z
fixture sha: 0f1cc196aa03
label source: agent-proposed; owner review required
items: 18 judged: 16 refusals: 2
exact agreement: 1.0000
adjacent agreement: 1.0000
mean absolute error: 0.0000
binary judge agreement: 1.0000
labels adopted: False
parse failures: 0
gate: REVIEW (labels not adopted)
```
