# Run record: V2 D3 retrieval filter and decomposition

- Date: 2026-11-04
- Run id: `20261104T153229Z`
- Ticket: #78 (V2 D3)
- Config: `pinned` (reranker on)
- Artifacts: `eval/results/baseline.csv` (committed), `eval/results/20261104T153229Z.csv` (local, gitignored)
- Status: pinned D3 baseline
- Supersedes: run `20261104T144856Z` (V2 D1 baseline r4)

## Configuration

| Field | Value |
|---|---|
| Generator | `qwen/qwen3-30b-a3b-instruct-2507` |
| Judge | `deepseek/deepseek-v4.1-flash-1017` |
| Reranker | `amazon.rerank-v1:0`, pool 50 |
| Embedder | `local` / `qwen3-embedding:0.6b`, 1024 dims |
| Chunking | size 500, overlap 75, min size 200 |
| Retrieval | hybrid (dense + BM25, RRF), `k = 5`, `rrf_k = 60`, candidates 50 |
| Filter | numeric/named book and chapter, dense `where` plus BM25 subset, unfiltered fallback |
| Decomposition | at most three sub-queries plus the original question, merged with RRF |
| Gold set | 60 items: 50 answerable, 10 unanswerable |
| Judged sample | 15, round-robin across the answerable slices |

## Retrieval

| Slice | n | Hit@5 | Recall@5 | MRR |
|---|---|---|---|---|
| overall | 50 | 0.78 | 0.66 | 0.51 |
| simple | 34 | 0.76 | 0.62 | 0.47 |
| multi_part | 8 | 0.62 | 0.50 | 0.40 |
| named_reference | 8 | 1.00 | 1.00 | 0.78 |

## Diagnostics

| Slice | n | dense | sparse | pool | lift | loss | near |
|---|---|---|---|---|---|---|---|
| overall | 50 | 0.78 | 0.69 | 0.82 | 0.87 | 0.13 | 0.06 |
| simple | 34 | 0.72 | 0.58 | 0.75 | 0.90 | 0.10 | 0.09 |
| multi_part | 8 | 0.81 | 0.81 | 0.94 | 0.62 | 0.38 | 0.00 |
| named_reference | 8 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 |

## Abstention

| Slice | Refused | Rate |
|---|---|---|
| overall | 10/10 | 1.00 |
| near_miss_unanswerable | 5/5 | 1.00 |
| off_topic | 5/5 | 1.00 |

## Generation (judged sample)

| Slice | n | EM | F1 | Judge correct | Faithful |
|---|---|---|---|---|---|
| overall | 15 | 0.00 | 0.32 | 12/15 | 12/15 (0.80) |
| simple | 5 | 0.00 | 0.30 | 5/5 | 5/5 (1.00) |
| named_reference | 5 | 0.00 | 0.28 | 5/5 | 5/5 (1.00) |
| multi_part | 5 | 0.00 | 0.40 | 2/5 | 2/5 (0.40) |

Judge buckets: 12 correct, 2 partial, 1 wrong. Grounded 12/15. No answer in the
sample abstained. Both judge parsers returned a usable verdict on all 15 answers.

## Reading

- Named references moved from 0.38 to 1.00. The query already carried the book
  and chapter; the retriever now uses it. This is the largest single retrieval
  gain and it came without touching the index.
- Overall Hit@5 moved from 0.58 to 0.78, and simple moved from 0.65 to 0.76. Part
  of the simple gain is the gold-label audit, not a retrieval change; the audit
  replaced adjacent or wrong evidence ids for `q03`, `q08`, `q13` and `q16`.
- Multi-part moved from 0.50 to 0.62. Pool recall is 0.94, so seven of eight
  items now have all expected ids in the merged pool. Item `m07` still misses
  `b3-c10-0020`: the second fact shares no terms with the question, and the chunk
  is outside the top 150 of both legs. That is a query-expansion or embedder
  problem, not a fusion bug.
- The reranker is no longer the main loss. Overall lift is 0.87; multi-part lost
  38% of its pool hits to rerank, so reranking the merged pool is the next
  multi-part tuning target.
- Faithfulness rose from 11/15 to 12/15. `multi_part` remains weak at 2/5
  faithful and 2/5 correct, so multi-fact grounding is still the generation
  problem.
- Abstention is still at ceiling with no answerable abstention in the judged
  sample.

## Next

1. Decide whether `m07` needs a query-expansion rule or a stronger embedder.
2. Tune the reranker on the merged multi-part pool; lift is 0.62.
3. Record an embedder or chunking experiment only if it beats this baseline.

## Reproduce

```
uv run python scripts/run_eval.py
# then, after a later run:
uv run python scripts/run_eval.py --check
```

## Raw summary

```text
gold: 60 items (50 answerable, 10 unanswerable)
config: pinned
generator: openrouter/qwen/qwen3-30b-a3b-instruct-2507
judge: openrouter/deepseek/deepseek-v4.1-flash-1017
reranker: bedrock

retrieval
  overall                n=50  Hit@5=0.78 Recall@5=0.66 MRR=0.51
  multi_part             n=8   Hit@5=0.62 Recall@5=0.50 MRR=0.40
  named_reference        n=8   Hit@5=1.00 Recall@5=1.00 MRR=0.78
  simple                 n=34  Hit@5=0.76 Recall@5=0.62 MRR=0.47

retrieval diagnostics
  overall                n=50  dense=0.78 sparse=0.69 pool=0.82 lift=0.87 loss=0.13 near=0.06
  multi_part             n=8   dense=0.81 sparse=0.81 pool=0.94 lift=0.62 loss=0.38 near=0.00
  named_reference        n=8   dense=1.00 sparse=1.00 pool=1.00 lift=1.00 loss=0.00 near=0.00
  simple                 n=34  dense=0.72 sparse=0.58 pool=0.75 lift=0.90 loss=0.10 near=0.09

abstention
  overall                10/10 (1.00)
  near_miss_unanswerable 5/5 (1.00)
  off_topic              5/5 (1.00)

generation (judged sample)
  overall                n=15  answered=15  abstained=0   EM=0.00 F1=0.32 faithful=12/15 (0.80) judge correct=12 partial=2 wrong=1 grounded=12 judge_parse=0 faithful_parse=0
  multi_part             n=5   answered=5   abstained=0   EM=0.00 F1=0.40 faithful=2/5 (0.40) judge correct=2 partial=2 wrong=1 grounded=2 judge_parse=0 faithful_parse=0
  named_reference        n=5   answered=5   abstained=0   EM=0.00 F1=0.28 faithful=5/5 (1.00) judge correct=5 partial=0 wrong=0 grounded=5 judge_parse=0 faithful_parse=0
  simple                 n=5   answered=5   abstained=0   EM=0.00 F1=0.30 faithful=5/5 (1.00) judge correct=5 partial=0 wrong=0 grounded=5 judge_parse=0 faithful_parse=0

wrote /Users/tc/Documents/Github/owl-online/eval/results/20261104T153229Z.csv
wrote baseline /Users/tc/Documents/Github/owl-online/eval/results/baseline.csv
```
