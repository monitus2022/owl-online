# Run record: #258 superseded calibration passes

- Date: 2026-11-13
- Run ids: `20261113T033913Z` (14-item first pass), `20261113T035711Z` (18-item pre-fix pass)
- Ticket: #258 (calibrate the lesson faithfulness judge)
- Config: `rag-calibration`

These passes are superseded by `20261113T040759Z` and are kept for the record.

## First pass

| Field | Value |
|---|---|
| Run id | `20261113T033913Z` |
| Items | 14 total: 13 judged, 1 refusal |
| Slices | in-pack, off-pack only |
| Labels | 5 supported, 3 partial, 5 unsupported, 1 refusal |
| Exact agreement | 1.0000 |
| Adjacent agreement | 1.0000 |
| MAE | 0.0000 |
| Gate | `PASS` before adoption gating |

The first pass was too narrow: no paraphrase, multi-concept or mixed items, and
the labels were not adoption-gated. It was superseded by the 18-item set.

## Pre-fix 18-item pass

| Field | Value |
|---|---|
| Run id | `20261113T035711Z` |
| Items | 18 total: 16 judged, 2 refusals |
| Slices | in-pack, paraphrase, multi-concept, mixed, off-pack |
| Labels | 8 supported, 4 partial, 4 unsupported, 2 refusal |
| Exact agreement | 1.0000 |
| Binary agreement | 1.0000 |
| Refusal recognition | 1/2 |
| Gate | `REVIEW (labels not adopted)` |

This pass added slice coverage and the production binary judge, but one refusal
paraphrase (`cal-18`) was not recognized by the refusal detector. It was
superseded by `20261113T040759Z`, which uses a recognized lesson-refusal form
and gates on refusal and binary agreement.

## Raw summaries

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
