# Run record: #105 multi-book k and selection ablation

- Date: 2026-11-07
- Run id: `20261106T224853Z`
- Ticket: #105 (V2)
- Config: `aggregation` (develop fixture, generation and judge)
- Artifacts: `eval/.cache/20261106T224853Z-multibook-ablation.json` (local, gitignored)

## Configuration

| Field | Value |
|---|---|
| Fixture | `eval/fixtures/aggregation.jsonl` (10 multi-book items) |
| Path | `ask_multi_book()` directly, no routing |
| Generator | `qwen/qwen3-30b-a3b-instruct-2507` |
| Judge | `deepseek/deepseek-v4.1-flash-1017` |
| Reranker | `amazon.rerank-v1:0`, pool 50 |
| Embedder | `local` / `qwen3-embedding:0.6b`, 1024 dims |
| Chunking | size 500, overlap 75, min size 200 |
| Retrieval | hybrid (dense + BM25, RRF), `rrf_k = 60`, per-book filter |
| Final top-k | 7 |
| Selection floor | 0.0 (the retriever floor) |
| Grid | k {1, 3, 5} x {top1_floor, batched_top3, per_book}, plus k=15 per-book |

## Results

| Config | Coverage | Completeness | Answer text | Citation | Faithful | n | Abstain | Calls | p50 ms | p95 ms | Spend |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| k1-top1 | 0.74 | 0.71 | 0.57 | 0.82 | 0.70 | 10 | 0.00 | 8.0 | 7738 | 9522 | $0.0040 |
| k1-batch | 0.76 | 0.72 | 0.56 | 0.81 | 0.70 | 10 | 0.00 | 2.0 | 9249 | 15124 | $0.0031 |
| k1-book | 0.74 | 0.71 | 0.52 | 0.81 | 0.50 | 10 | 0.00 | 8.0 | 9947 | 20084 | $0.0040 |
| k3-top1 | 0.61 | 0.57 | 0.40 | 0.78 | 0.67 | 9 | 0.10 | 8.0 | 13500 | 18346 | $0.0041 |
| k3-batch | 0.66 | 0.63 | 0.50 | 0.75 | 0.56 | 9 | 0.10 | 2.0 | 47721 | 118807 | $0.0064 |
| k3-book | 0.83 | 0.79 | 0.63 | 0.83 | 0.70 | 10 | 0.00 | 8.0 | 18076 | 32089 | $0.0070 |
| k5-top1 | 0.76 | 0.72 | 0.55 | 0.81 | 0.60 | 10 | 0.00 | 8.0 | 11014 | 15522 | $0.0040 |
| k5-batch | 0.80 | 0.76 | 0.64 | 0.79 | 0.40 | 10 | 0.00 | 2.0 | 21891 | 36976 | $0.0065 |
| k5-book | 0.81 | 0.76 | 0.63 | 0.87 | 0.56 | 9 | 0.10 | 8.0 | 13345 | 16258 | $0.0089 |
| k15-book | 0.78 | 0.73 | 0.63 | 0.84 | 0.56 | 9 | 0.10 | 8.0 | 14485 | 23469 | $0.0179 |

## Reading

- k1-batch is the cheapest and uses the fewest calls, but coverage 0.76 is below
  the pre-registered 0.80 bar; completeness 0.72 clears the 0.70 bar. k1-top1
  has the lowest p50 and p95.
- k3-book has the best coverage and completeness (0.83/0.79) and ties the best
  faithfulness (0.70). Its p95 is 32.1s, slightly over the 30s bar on this
  fixture.
- k5-book has the best citation validity (0.87) and a p95 of 16.3s, but
  faithfulness is 0.56. The difference from k3-book is 1-2 judged items.
- The shipped k15-book is not the best on this fixture: coverage 0.78, citation
  0.84, faithfulness 0.56, and the highest spend ($0.0179). k3-book spends about
  39% of k15-book ($0.0070 against $0.0179), not half.
- The batched strategy cuts calls from 8 to 2 but is not reliably faster: k3-batch
  p95 is 118.8s. It loses coverage and faithfulness against k3-book. It always
  uses the top three candidates per book, so k3-batch and k5-batch share the
  same extraction input; their difference is model noise, not a k effect.
- Faithfulness is low and noisy across every config (0.40 to 0.70). The develop
  fixture does not support a confident choice on that metric. The pre-registered
  0.88 point estimate is not reached by any config.
- The top-1 strategies do not beat the per-book strategies on coverage at the
  same k. A positive score floor is not supported by the diagnostic: the
  first-relevant p10 is 0.0015 and some relevant books score 0.0001.
- The generator and judge calls are cached by (model, input); the recorded run
  is one stochastic sample before the cache was added, so a rerun may differ.
- Spend is estimated from character volume at the placeholder
  `OWL_CHAT_*_PRICE_PER_MTOK` settings. It excludes judge, reranker and embedder
  cost, and cache hits still increment the character counters, so it is an upper
  bound, not a bill.
- The final holdout run uses k3-book: the best coverage/completeness config,
  about 39% of k15-book's spend, with the p95 risk noted. The flag stays off
  unless the holdout clears the pre-registered bars.

## Reproduce

```
uv run python scripts/measure_multibook_ablation.py --run-id 20261106T224853Z
```

## Raw summary

```text
running k1-top1 (k=1, selection=top1_floor)...
running k1-batch (k=1, selection=batched_top3)...
running k1-book (k=1, selection=per_book)...
running k3-top1 (k=3, selection=top1_floor)...
running k3-batch (k=3, selection=batched_top3)...
running k3-book (k=3, selection=per_book)...
running k5-top1 (k=5, selection=top1_floor)...
running k5-batch (k=5, selection=batched_top3)...
running k5-book (k=5, selection=per_book)...
running k15-book (k=15, selection=per_book)...

run: 20261106T224853Z
fixture: /Users/tc/Documents/Github/owl-online/eval/fixtures/aggregation.jsonl
items: 10 multi_book
manifest: generator=qwen/qwen3-30b-a3b-instruct-2507 judge=deepseek/deepseek-v4.1-flash-1017 reranker=amazon.rerank-v1:0 pool=50 embedder=qwen3-embedding:0.6b final_top_k=7 selection_floor=0.0

config          cov  comp  text  cite  faith  n  abst  calls  p50ms  p95ms  spend
k1-top1        0.74  0.71  0.57  0.82  0.70 10  0.00   8.0   7738   9522 $0.0040
k1-batch       0.76  0.72  0.56  0.81  0.70 10  0.00   2.0   9249  15124 $0.0031
k1-book        0.74  0.71  0.52  0.81  0.50 10  0.00   8.0   9947  20084 $0.0040
k3-top1        0.61  0.57  0.40  0.78  0.67  9  0.10   8.0  13500  18346 $0.0041
k3-batch       0.66  0.63  0.50  0.75  0.56  9  0.10   2.0  47721 118807 $0.0064
k3-book        0.83  0.79  0.63  0.83  0.70 10  0.00   8.0  18076  32089 $0.0070
k5-top1        0.76  0.72  0.55  0.81  0.60 10  0.00   8.0  11014  15522 $0.0040
k5-batch       0.80  0.76  0.64  0.79  0.40 10  0.00   2.0  21891  36976 $0.0065
k5-book        0.81  0.76  0.63  0.87  0.56  9  0.10   8.0  13345  16258 $0.0089
k15-book       0.78  0.73  0.63  0.84  0.56  9  0.10   8.0  14485  23469 $0.0179

wrote /Users/tc/Documents/Github/owl-online/eval/.cache/20261106T224853Z-multibook-ablation.json
```
