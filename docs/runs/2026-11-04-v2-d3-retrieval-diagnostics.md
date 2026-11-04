# Run record: V2 D3 retrieval diagnostics

- Date: 2026-11-04
- Run id: `20261104T152008Z`
- Ticket: #78 (V2 D3)
- Config: `pinned` (reranker on)
- Artifacts: `eval/results/20261104T152008Z.csv` (local, gitignored)
- Status: diagnostic run, not pinned as the baseline

## Configuration

| Field | Value |
|---|---|
| Generator | `qwen/qwen3-30b-a3b-instruct-2507` |
| Judge | `deepseek/deepseek-v4.1-flash-1017` |
| Reranker | `amazon.rerank-v1:0`, pool 50 |
| Embedder | `local` / `qwen3-embedding:0.6b`, 1024 dims |
| Chunking | size 500, overlap 75, min size 200 |
| Retrieval | hybrid (dense + BM25, RRF), `k = 5`, `rrf_k = 60`, candidates 50 |
| Gold set | 60 items: 50 answerable, 10 unanswerable; hash `63e1f42eb549` |
| Judged sample | 15, round-robin across the answerable slices |

## Retrieval

| Slice | n | Hit@5 | Recall@5 | MRR |
|---|---|---|---|---|
| overall | 50 | 0.58 | 0.48 | 0.37 |
| simple | 34 | 0.65 | 0.55 | 0.39 |
| multi_part | 8 | 0.50 | 0.31 | 0.35 |
| named_reference | 8 | 0.38 | 0.38 | 0.29 |

## Diagnostics

`dense` and `sparse` are recall@50 per leg. `pool` is recall@50 before rerank.
`lift` is the share of pool hits the reranker converts into top-5 hits. `near`
is the share of items where the expected id is missed but a chunk in the same
chapter one position either side is returned.

| Slice | n | dense | sparse | pool | lift | loss | near |
|---|---|---|---|---|---|---|---|
| overall | 50 | 0.60 | 0.48 | 0.60 | 0.85 | 0.15 | 0.08 |
| simple | 34 | 0.63 | 0.52 | 0.66 | 0.88 | 0.12 | 0.12 |
| multi_part | 8 | 0.56 | 0.44 | 0.56 | 0.67 | 0.33 | 0.00 |
| named_reference | 8 | 0.50 | 0.38 | 0.38 | 1.00 | 0.00 | 0.00 |

Stage outcome over 50 answerable items: 29 exact hits, 14 leg misses, 2 fusion
losses and 5 rerank losses. Four of the 19 misses are neighbour hits, all on the
simple slice.

## Ten-miss audit

| Item | Slice | Stage | Finding |
|---|---|---|---|
| `q03` | simple | leg miss | Gold `b1-c09-0026` is the Wood introduction; `b4-c05-0048` states the Seeker position. Label too strict. |
| `q08` | simple | leg miss | Gold `b2-c16-0026/0028`; top `b2-c16-0027` is the adjacent passage and names the Basilisk. Neighbour hit. |
| `q13` | simple | leg miss | Gold `b4-c05-0045` is about wands; top `b4-c07-0032` explicitly names Viktor Krum as the Bulgarian Seeker. Wrong label. |
| `q16` | simple | leg miss | Gold `b6-c04-0032` introduces Slughorn but not the Potions post; `b6-c08-0045` names him as new staff. Ambiguous label. |
| `n01` | named_reference | leg miss | Gold `b1-c07-0028`; `b1-c07-0032` is in the requested chapter. The retriever never uses the book/chapter in the query. |
| `n02` | named_reference | leg miss | Gold `b2-c13-0017`; results come from other books and chapters. Filter target. |
| `n05` | named_reference | leg miss | Gold `b4-c20-0048`; top `b4-c20-0014` is the requested chapter. Filter target. |
| `m03` | multi_part | leg miss | Gold `b1-c11-0042` names Fluffy and the loan to Dumbledore; the query says three-headed dog. Lexical gap. |
| `q09` | simple | leg miss | Gold `b2-c03-0029` contains THE BURROW; the query says Weasley family home. Semantic gap. |
| `s13` | simple | leg miss | Gold `b1-c15-0055` names Firenze; the query asks which centaur rescues Harry. Semantic gap. |

## Reading

- The reranker is not the bottleneck. Overall lift is 0.85 and loss is 0.15; the
  pool ceiling is 0.60.
- Dense recall is 0.60 overall and 0.50 on named references. Sparse recall is
  0.48 and adds little. A stronger embedder and a metadata filter are the two
  retrieval levers that can move the ceiling.
- The named slice is the clearest miss: the query contains the book and chapter,
  but dense recall is 0.50 and pool recall is 0.38 because fusion drops
  dense-only hits. A filter should raise both, and the pool truncation needs a
  check.
- Four simple misses are neighbour hits. If adjacent chunks count, the simple
  ceiling rises from 0.66 to about 0.77. At least one gold label is wrong
  (`q13`) and several are too strict (`q03`, `q08`, `q16`). Fix the labels before
  treating 0.58 as the retrieval quality.
- `multi_part` loses a third of its pool hits in the reranker. Decomposition is
  still the right fix, but the merged pool must be scored before rerank.
- Faithfulness is unchanged at 11/15. The multi-part slice is the weakest
  generation slice at 2/5 faithful.

## Next

1. Correct the four gold labels with an audit note.
2. Add the book/chapter filter and the empty-filter fallback.
3. Re-run this diagnostic table; do not start embedder or chunking work until the
   filtered baseline is measured.

## Reproduce

```
uv run python scripts/run_eval.py
```

The diagnostics are in the printed `retrieval diagnostics` section and in the
CSV columns `dense_recall_at_pool`, `sparse_recall_at_pool`,
`pool_recall_at_pool`, `rerank_lift`, `rerank_loss` and `neighbor_hit_rate`.

## Raw summary

```text
gold: 60 items (50 answerable, 10 unanswerable)
config: pinned
generator: openrouter/qwen/qwen3-30b-a3b-instruct-2507
judge: openrouter/deepseek/deepseek-v4.1-flash-1017
reranker: bedrock

retrieval
  overall                n=50  Hit@5=0.58 Recall@5=0.48 MRR=0.37
  multi_part             n=8   Hit@5=0.50 Recall@5=0.31 MRR=0.35
  named_reference        n=8   Hit@5=0.38 Recall@5=0.38 MRR=0.29
  simple                 n=34  Hit@5=0.65 Recall@5=0.55 MRR=0.39

retrieval diagnostics
  overall                n=50  dense=0.60 sparse=0.48 pool=0.60 lift=0.85 loss=0.15 near=0.08
  multi_part             n=8   dense=0.56 sparse=0.44 pool=0.56 lift=0.67 loss=0.33 near=0.00
  named_reference        n=8   dense=0.50 sparse=0.38 pool=0.38 lift=1.00 loss=0.00 near=0.00
  simple                 n=34  dense=0.63 sparse=0.52 pool=0.66 lift=0.88 loss=0.12 near=0.12

abstention
  overall                10/10 (1.00)
  near_miss_unanswerable 5/5 (1.00)
  off_topic              5/5 (1.00)

generation (judged sample)
  overall                n=15  answered=15  abstained=0   EM=0.00 F1=0.28 faithful=11/15 (0.73) judge correct=11 partial=2 wrong=2 grounded=11 judge_parse=0 faithful_parse=0
  multi_part             n=5   answered=5   abstained=0   EM=0.00 F1=0.33 faithful=2/5 (0.40) judge correct=2 partial=2 wrong=1 grounded=2 judge_parse=0 faithful_parse=0
  named_reference        n=5   answered=5   abstained=0   EM=0.00 F1=0.21 faithful=4/5 (0.80) judge correct=4 partial=0 wrong=1 grounded=4 judge_parse=0 faithful_parse=0
  simple                 n=5   answered=5   abstained=0   EM=0.00 F1=0.30 faithful=5/5 (1.00) judge correct=5 partial=0 wrong=0 grounded=5 judge_parse=0 faithful_parse=0

wrote /Users/tc/Documents/Github/owl-online/eval/results/20261104T152008Z.csv
```
