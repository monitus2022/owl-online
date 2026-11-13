# Run record: #258 lesson faithfulness calibration

- Date: 2026-11-13
- Run ids: `20261113T033913Z` (14-item first pass), `20261113T035711Z` (18-item final pass)
- Ticket: #258 (calibrate the lesson faithfulness judge)
- Config: `rag-calibration`
- Artifacts: `eval/results/rag-calibration-20261113T035711Z.json` (local, gitignored)
- Fixture: `eval/rag/fixtures/faithfulness_calibration.jsonl`, SHA-256 `0f1cc196aa03`

## Configuration

| Field | Value |
|---|---|
| Judge | `deepseek/deepseek-v4.1-flash-1017`, temperature 0.0 |
| Prompts | three-level `faithfulness-label-v1` and production binary `FAITHFUL_SYSTEM` |
| Items | 18 total: 16 judged, 2 refusals |
| Slices | in-pack, paraphrase, multi-concept, mixed, off-pack |
| Label source | agent-proposed; owner review required |
| Labels | 8 supported, 4 partial, 4 unsupported, 2 refusal |

The answers are short synthetic paraphrases. The fixture stores the question,
answer, material ids and chunk ids; the runner loads the published notes and
corpus at run time. No material or corpus text is stored in the fixture.

## Agreement

| Metric | Value |
|---|---:|
| Three-level exact agreement | 1.0000 |
| Three-level adjacent agreement | 1.0000 |
| Three-level mean absolute error | 0.0000 |
| Production binary judge agreement | 1.0000 |
| Parse failures | 0 |
| Refusal checks | 2/2 |

## Reading

- The three-level judge and the production binary judge both agree with every
  proposed label on this set, including the partial and mixed answers. The
  judge is not simply marking every teaching-shaped answer unsupported.
- The first pass used 14 items and only in-pack/off-pack evidence; it was
  superseded by the 18-item set, which adds paraphrase, multi-concept and mixed
  coverage and a second refusal form.
- The labels are agent-proposed, not owner-adopted. The judge and the label
  proposer are the same model family, so 1.0000 is self-agreement, not
  independent calibration. The gate therefore reports
  `REVIEW (labels not adopted)` and exits non-zero.
- The set is still synthetic and small. Owner adoption is the independence
  step; after adoption, add 5-10 real model answers before pinning the gate,
  without committing pack prose.
- The #248 lesson faithfulness of 2/30 is unlikely to be a simple strictness
  artifact: the judge can separate supported, partial and unsupported answers.
  The next step is #251: tighten the lesson prompt, pass the full concept group
  and bind claims to citations, then measure against the adopted calibration.

## Reproduce

```
uv run python scripts/run_rag_calibration.py
```

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
wrote /Users/tc/Documents/Github/owl-online/eval/results/rag-calibration-20261113T035711Z.json
```
