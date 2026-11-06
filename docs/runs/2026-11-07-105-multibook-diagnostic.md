# Run record: #105 multi-book retrieval diagnostic

- Date: 2026-11-07
- Run id: `20261106T224550Z`
- Ticket: #105 (V2)
- Config: `aggregation` (retrieval only, no generation tokens)
- Artifacts: `eval/.cache/20261106T224550Z-multibook-diagnostic.json` (local, gitignored)

## Configuration

| Field | Value |
|---|---|
| Fixture | `eval/fixtures/aggregation.jsonl` |
| Items | 10 multi-book, 56 (item, book) pairs |
| Per-book k | 15 |
| Reranker | `amazon.rerank-v1:0`, pool 50 |
| Embedder | `local` / `qwen3-embedding:0.6b`, 1024 dims |
| Retrieval | hybrid (dense + BM25, RRF), `rrf_k = 60`, per-book filter |
| Generation | none |

## Per-book hit rate

| k | Hit rate | Count |
|---:|---:|---:|
| 1 | 0.82 | 46/56 |
| 3 | 0.95 | 53/56 |
| 5 | 0.96 | 54/56 |
| 7 | 0.98 | 55/56 |
| 15 | 0.98 | 55/56 |

## Score distribution

| Series | n | p10 | p50 | p90 |
|---|---:|---:|---:|---:|
| First relevant chunk | 55 | 0.0015 | 0.0267 | 0.0964 |
| Top-1 chunk | 56 | 0.0015 | 0.0279 | 0.1301 |

First relevant rank: p50 1, p90 2, max 6.

## Reading

- Most of the retrieval gain is between k=1 and k=3: 0.82 to 0.95. k=5, 7 and 15 add
  one pair each at most. This supports the k ablation {1, 3, 5} and suggests k=3
  is the useful point; k=15 is a control, not a requirement.
- One (item, book) pair misses at every k up to 15: `agg08` book 4 for
  `Sirius Black`. More candidates do not recover it, so the ablation should not
  treat k=5 as a fix for that item.
- The first-relevant scores overlap the top-1 scores (p50 0.0267 against
  0.0279), and the p10 is 0.0015. A single absolute floor would drop relevant
  books; the top-1-plus-floor strategy needs a low floor, or a relative rule.
- The diagnostic spent no generation tokens. It does call the reranker 56 times.
- The develop fixture only. The holdout was not touched.

## Reproduce

```
uv run python scripts/measure_multibook_diagnostic.py
```

## Raw summary

```text
run: 20261106T224550Z
fixture: /Users/tc/Documents/Github/owl-online/eval/fixtures/aggregation.jsonl
items: 10 multi_book, 56 (item, book) pairs
per_book_k=15 reranker=amazon.rerank-v1:0 pool=50 embedder=qwen3-embedding:0.6b top_k=15 rrf_k=60

per-book hit rate (any expected entity in the top k)
  k=1  0.82 (46/56)
  k=3  0.95 (53/56)
  k=5  0.96 (54/56)
  k=7  0.98 (55/56)
  k=15 0.98 (55/56)

score distribution
  first relevant chunk         n= 55 p10=0.0015 p50=0.0267 p90=0.0964
  top-1 chunk                  n= 56 p10=0.0015 p50=0.0279 p90=0.1301
  first relevant rank          n= 55 p50=1 p90=2 max=6

per item
  agg01    b1 rank=   1 score= 0.1503 entities=Quirrell
  agg01    b2 rank=   6 score= 0.0208 entities=Lockhart
  agg01    b3 rank=   1 score= 0.5027 entities=Lupin
  agg01    b4 rank=   1 score= 0.1784 entities=Moody
  agg01    b5 rank=   2 score= 0.1005 entities=Umbridge
  agg01    b6 rank=   1 score= 0.2402 entities=Snape
  agg01    b7 rank=   5 score= 0.0260 entities=Amycus
  agg02    b2 rank=   1 score= 0.0439 entities=Dobby
  agg02    b4 rank=   1 score= 0.0779 entities=Dobby
  agg02    b5 rank=   1 score= 0.0262 entities=Dobby
  agg02    b6 rank=   1 score= 0.0166 entities=Dobby
  agg02    b7 rank=   1 score= 0.0095 entities=Dobby
  agg03    b1 rank=   1 score= 0.0539 entities=Dumbledore
  agg03    b2 rank=   1 score= 0.0267 entities=Dumbledore
  agg03    b3 rank=   1 score= 0.0225 entities=Dumbledore
  agg03    b4 rank=   1 score= 0.0663 entities=Dumbledore
  agg03    b5 rank=   1 score= 0.0569 entities=Dumbledore
  agg03    b6 rank=   1 score= 0.0275 entities=Dumbledore
  agg03    b7 rank=   2 score= 0.0327 entities=Snape
  agg04    b1 rank=   1 score= 0.0359 entities=Fudge
  agg04    b2 rank=   1 score= 0.0285 entities=Fudge
  agg04    b3 rank=   1 score= 0.0836 entities=Fudge
  agg04    b4 rank=   2 score= 0.0278 entities=Fudge
  agg04    b5 rank=   1 score= 0.1388 entities=Fudge
  agg04    b6 rank=   1 score= 0.0389 entities=Scrimgeour
  agg04    b7 rank=   1 score= 0.0353 entities=Thicknesse
  agg05    b1 rank=   1 score= 0.0057 entities=Draco
  agg05    b2 rank=   1 score= 0.0122 entities=Lucius,Draco
  agg05    b3 rank=   1 score= 0.0330 entities=Lucius,Draco
  agg05    b4 rank=   1 score= 0.0166 entities=Lucius,Draco,Narcissa
  agg05    b5 rank=   2 score= 0.0056 entities=Lucius,Draco,Narcissa
  agg05    b6 rank=   2 score= 0.0097 entities=Lucius,Draco,Narcissa
  agg05    b7 rank=   1 score= 0.0194 entities=Lucius,Draco,Narcissa
  agg06    b5 rank=   1 score= 0.0102 entities=Order of the Phoenix
  agg06    b6 rank=   1 score= 0.0013 entities=Order of the Phoenix
  agg06    b7 rank=   1 score= 0.0037 entities=Order of the Phoenix
  agg07    b2 rank=   2 score= 0.0001 entities=diary
  agg07    b6 rank=   1 score= 0.0005 entities=Horcrux
  agg07    b7 rank=   1 score= 0.0076 entities=Horcrux
  agg08    b3 rank=   1 score= 0.0015 entities=Sirius Black
  agg08    b4 rank=miss score=    n/a entities=Sirius Black
  agg08    b5 rank=   2 score= 0.0014 entities=Sirius Black
  agg09    b1 rank=   1 score= 0.0144 entities=Quidditch
  agg09    b2 rank=   1 score= 0.0065 entities=Quidditch
  agg09    b3 rank=   1 score= 0.0015 entities=Quidditch
  agg09    b4 rank=   1 score= 0.0139 entities=Quidditch
  agg09    b5 rank=   1 score= 0.0028 entities=Quidditch
  agg09    b6 rank=   1 score= 0.0011 entities=Quidditch
  agg09    b7 rank=   1 score= 0.0025 entities=Quidditch
  agg10    b1 rank=   1 score= 0.0626 entities=Dursley
  agg10    b2 rank=   1 score= 0.0901 entities=Dursley
  agg10    b3 rank=   1 score= 0.0285 entities=Dursley
  agg10    b4 rank=   1 score= 0.0283 entities=Dursley
  agg10    b5 rank=   1 score= 0.0314 entities=Dursley
  agg10    b6 rank=   1 score= 0.0624 entities=Dursley
  agg10    b7 rank=   1 score= 0.0310 entities=Dursley

missing in top 15: 1
  agg08 b4 entities=Sirius Black

wrote /Users/tc/Documents/Github/owl-online/eval/.cache/20261106T224550Z-multibook-diagnostic.json
```
