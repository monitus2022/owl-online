# Run record: #113 ingest re-baseline

- Date: 2026-11-07
- Run id: `20261106T214850Z`
- Ticket: #113 (V2)
- Config: `pinned` (reranker on)
- Artifacts: `eval/results/baseline.csv` (re-pinned to this run), `eval/results/20261106T214850Z.csv` (local, gitignored)

## Configuration

| Field | Value |
|---|---|
| Generator | `qwen/qwen3-30b-a3b-instruct-2507` |
| Judge | `deepseek/deepseek-v4.1-flash-1017` |
| Reranker | `amazon.rerank-v1:0`, pool 50 |
| Embedder | `local` / `qwen3-embedding:0.6b`, 1024 dims |
| Chunking | size 500, overlap 75, min size 200 |
| Retrieval | hybrid (dense + BM25, RRF), `k = 5`, `rrf_k = 60`, candidates 50 |
| Sub-query quota | 0 (global fusion) |
| Gold set | 61 items: 51 answerable, 10 unanswerable |
| Judged sample | 15, round-robin across the answerable slices |
| Index text hash | `aca4c57462d449f5` (rebuilt after ingest) |

## Retrieval

| Slice | n | Hit@5 | Recall@5 | MRR |
|---|---:|---:|---:|---:|
| overall | 51 | 0.76 | 0.65 | 0.51 |
| simple | 34 | 0.74 | 0.62 | 0.46 |
| multi_part | 9 | 0.67 | 0.46 | 0.46 |
| named_reference | 8 | 1.00 | 1.00 | 0.78 |

## Abstention

| Slice | Refused | Rate |
|---|---:|---:|
| overall | 10/10 | 1.00 |
| near_miss_unanswerable | 5/5 | 1.00 |
| off_topic | 5/5 | 1.00 |

## Generation (judged sample)

| Slice | n | EM | F1 | Judge correct | Faithful |
|---|---:|---:|---:|---:|---:|
| overall | 15 | 0.00 | 0.31 | 13 correct, 2 partial, 0 wrong | 13/15 (0.87) |
| simple | 5 | 0.00 | 0.30 | 5 correct | 5/5 (1.00) |
| named_reference | 5 | 0.00 | 0.28 | 5 correct | 5/5 (1.00) |
| multi_part | 5 | 0.00 | 0.36 | 3 correct, 2 partial | 3/5 (0.60) |

Judge buckets: 13 correct, 2 partial, 0 wrong. Grounded 13/15. 0 answers in the
sample abstained.

## Reading

- The ingest fix removed 31 front-matter chunks across the seven book boundaries
  and the final copyright page. No chunk now contains a `CONTENTS` or
  `Text copyright` page, and `b1-c17-0079` is gone. The book 1 last chapter
  dropped from 80 to 77 chunks; the other last chapters dropped by 3 to 8.
- All 61 gold questions resolve against the new chunk ids. The only expected id
  in a last chapter is `s07` to `b2-c18-0025`, and its text is still the
  Gryffindor sword passage.
- Retrieval is inside the noise band: overall Hit@5 0.76 is unchanged, Recall@5
  0.65 is down 0.01, MRR 0.51 is up 0.01. The multi-part Recall@5 drop (0.52 to
  0.46) is 0.056, inside the gate's 1/9 floor of 0.111; its MRR rose from 0.41
  to 0.46. Named and simple are unchanged.
- Abstention is 10/10 on both unanswerable slices.
- Generation answers all 15 sampled items, where the previous run abstained on
  one multi-part item. Faithfulness is 13/15 (0.87) against 13/14 (0.93); the
  drop is 0.064, inside the 0.10 band and driven by the extra answered item, not
  by a new fabrication (judge wrong is 0, partial is 2). F1 is 0.31 against 0.30.
- Novel entities are 0/15.
- The baseline is re-pinned because the index text hash changed. The old
  baseline `20261106T060737Z` described the pre-fix corpus and is no longer the
  gate target.

## Reproduce

```
uv run python scripts/run_eval.py --write-baseline
```

## Raw summary

```text
gold: 61 items (51 answerable, 10 unanswerable)
config: pinned
generator: openrouter/qwen/qwen3-30b-a3b-instruct-2507
judge: openrouter/deepseek/deepseek-v4.1-flash-1017
reranker: bedrock

retrieval
  overall                n=51  Hit@5=0.76 Recall@5=0.65 MRR=0.51
  multi_part             n=9   Hit@5=0.67 Recall@5=0.46 MRR=0.46
  named_reference        n=8   Hit@5=1.00 Recall@5=1.00 MRR=0.78
  simple                 n=34  Hit@5=0.74 Recall@5=0.62 MRR=0.46

retrieval diagnostics
  overall                n=51  dense=0.76 sparse=0.68 pool=0.81 lift=0.87 loss=0.13 near=0.06
  multi_part             n=9   dense=0.80 sparse=0.76 pool=0.91 lift=0.67 loss=0.33 near=0.00
  named_reference        n=8   dense=1.00 sparse=1.00 pool=1.00 lift=1.00 loss=0.00 near=0.00
  simple                 n=34  dense=0.69 sparse=0.58 pool=0.75 lift=0.89 loss=0.11 near=0.09

abstention
  overall                10/10 (1.00)
  near_miss_unanswerable 5/5 (1.00)
  off_topic              5/5 (1.00)

generation (judged sample)
  overall                n=15  answered=15  abstained=0   EM=0.00 F1=0.31 faithful=13/15 (0.87) judge correct=13 partial=2 wrong=0 grounded=13 judge_parse=0 faithful_parse=0
  multi_part             n=5   answered=5   abstained=0   EM=0.00 F1=0.36 faithful=3/5 (0.60) judge correct=3 partial=2 wrong=0 grounded=3 judge_parse=0 faithful_parse=0
  named_reference        n=5   answered=5   abstained=0   EM=0.00 F1=0.28 faithful=5/5 (1.00) judge correct=5 partial=0 wrong=0 grounded=5 judge_parse=0 faithful_parse=0
  simple                 n=5   answered=5   abstained=0   EM=0.00 F1=0.30 faithful=5/5 (1.00) judge correct=5 partial=0 wrong=0 grounded=5 judge_parse=0 faithful_parse=0

novel entities: 0/15 answers (0.00), tokens: none

wrote /Users/tc/Documents/Github/owl-online/eval/results/20261106T214850Z.csv
wrote baseline /Users/tc/Documents/Github/owl-online/eval/results/baseline.csv
```
