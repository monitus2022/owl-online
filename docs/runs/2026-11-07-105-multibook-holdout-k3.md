# Run record: #105 multi-book final holdout (k=3)

- Date: 2026-11-07
- Run id: `20261106T233126Z`
- Ticket: #105 (V2)
- Config: `multi_book` (per-book k=3, per-book extraction, final top-k 7, reranker on)
- Artifacts: `eval/results/20261106T233126Z-multibook-generation.csv` (local, gitignored)

## Configuration

| Field | Value |
|---|---|
| Path | `ask(multi_book=True)`; routed questions only |
| Per-book k | 3 |
| Selection | `per_book` |
| Final top-k | 7 |
| Generator | `qwen/qwen3-30b-a3b-instruct-2507` |
| Judge | `deepseek/deepseek-v4.1-flash-1017` |
| Reranker | `amazon.rerank-v1:0`, pool 50 |
| Embedder | `local` / `qwen3-embedding:0.6b`, 1024 dims |
| Chunking | size 500, overlap 75, min size 200 |
| Fixture | `eval/fixtures/aggregation_holdout.jsonl`, 15 multi-book, 5 near-miss, frozen |
| Deadline | `OWL_ASK_TIMEOUT_S` 30s |

This is the single final run of the bounded #105 cycle. The configuration was
chosen from the develop-fixture ablation before this run. The holdout was not
tuned on.

## Per-item results

| Item | Route | Books | Entities | Answer text | Citations | Faithful | Calls | Latency |
|---|---|---|---:|---:|---:|---:|---:|---:|
| hold01 | multi_book | 4/4 | 4/4 | 3/4 | 4/4 | yes | 8 | 14184ms |
| hold02 | multi_book | 3/3 | 3/3 | 3/3 | 3/3 | yes | 8 | 12648ms |
| hold03 | multi_book | 3/3 | 3/3 | 3/3 | 3/3 | yes | 8 | 15938ms |
| hold04 | multi_book | 5/6 | 5/6 | 5/6 | 5/5 | yes | 8 | 17859ms |
| hold05 | multi_book | 3/6 | 3/6 | 3/6 | 3/7 | yes | 8 | 17659ms |
| hold06 | multi_book | 7/7 | 7/7 | 6/7 | 7/7 | yes | 8 | 20522ms |
| hold07 | multi_book | 4/5 | 4/5 | 4/5 | 4/4 | yes | 8 | 17991ms |
| hold08 | multi_book | 5/5 | 5/5 | 4/5 | 7/7 | yes | 8 | 16039ms |
| hold09 | multi_book | 7/7 | 7/7 | 7/7 | 7/7 | yes | 8 | 20766ms |
| hold10 | multi_book | 4/4 | 4/4 | 1/4 | 4/4 | yes | 8 | 12936ms |
| hold11 | multi_book | 4/4 | 4/4 | 4/4 | 4/5 | no | 8 | 15952ms |
| hold12 | multi_book | 7/7 | 7/7 | 7/7 | 7/7 | yes | 8 | 22555ms |
| hold13 | multi_book | 4/5 | 4/5 | 4/5 | 6/6 | no | 8 | 22926ms |
| hold14 | multi_book | 2/3 | 2/3 | 2/3 | 2/2 | no | 8 | 8943ms |
| hold15 | multi_book | 2/3 | 2/3 | 3/3 | 5/7 | no | 1 | 4220ms |
| hnear01 | near_miss | 1/1 | 3/3 | 1/1 | 1/1 | yes | 1 | 1832ms |
| hnear02 | near_miss | 0/1 | 0/4 | 0/1 | 0/0 | n/a | 0 | 88ms |
| hnear03 | near_miss | 0/1 | 0/3 | 1/1 | 0/1 | yes | 1 | 1853ms |
| hnear04 | near_miss | 1/1 | 4/4 | 1/1 | 1/1 | yes | 1 | 2081ms |
| hnear05 | near_miss | 1/1 | 3/4 | 1/1 | 3/3 | no | 1 | 11270ms |

Books and entities use the cited evidence. Answer text is stricter: the entity
must appear in that book's answer text.

## Aggregate

| Metric | Value | Bar | Result |
|---|---:|---:|---|
| Book coverage | 0.88 | >= 0.80 | pass |
| Full coverage | 0.60 | n/a | n/a |
| Entity completeness | 0.88 | >= 0.70 | pass |
| Answer-text coverage | 0.82 | n/a | n/a |
| Answer-text completeness | 0.82 | n/a | n/a |
| Citation validity, all 15 | 0.91 | n/a | n/a |
| Citation validity, synthesis 14 | 0.93 (66/71) | >= 0.90 | pass |
| Citation items passing, synthesis | 12/14 (Wilson lower 0.60) | 18/20, Wilson lower 0.80 | fail, bar unsatisfiable |
| Faithfulness, all 15 | 0.73 (11/15) | n/a | n/a |
| Faithfulness, synthesis 14 | 0.79 (11/14), Wilson lower 0.52 | >= 0.88, lower 0.70 | fail |
| Abstention | 0.00 | n/a | n/a |
| Near-miss entity hit | 0.60 | n/a | n/a |
| Near-miss citation validity | 0.83 | n/a | n/a |
| Latency p50 | 16039ms | n/a | n/a |
| Latency p95 (nearest rank) | 22926ms | < 30000ms | pass |
| Latency max | 22926ms | < 30000ms | pass |
| Model calls | 113 | n/a | n/a |
| Input tokens (est.) | 57159 | n/a | n/a |
| Output tokens (est.) | 12731 | n/a | n/a |
| Tokens per multi-book item (est.) | 4659 total / 3811 input | <= 3000 | fail |
| Tokens per holdout item, including near-miss (est.) | 3734 total / 3071 input | <= 3000 | fail |
| Spend (est.) | $0.0095 | n/a | n/a |

The pre-registered citation bar, 18/20 with a Wilson lower bound of 0.80, is
unsatisfiable at 95%: 18/20 is about 0.70 and 20/20 about 0.84. The citation
result is reported but is not independent evidence; the faithfulness failure
decides. The token numerator covers the 15 multi-book items; the 20-item row
adds the near-miss items. Both readings fail the 3k bar.

## Reading

- Coverage and completeness pass comfortably: 0.88/0.88 against 0.80/0.70. The
  k=3 configuration raised coverage from 0.84 to 0.88 and cut spend from $0.0246
  to $0.0095, about 39% of the k=15 run.
- Citation validity after synthesis is 0.93 (66/71), above the 0.90 exit bar.
  At the item level, 12 of 14 synthesis items have no invalid citation, a Wilson
  lower bound of 0.60. The pre-registered 18/20 with a 0.80 lower bound is
  unsatisfiable at 95%, so it is not independent evidence.
- Faithfulness fails clearly: 11/14 (0.79) against 0.88, Wilson lower 0.52
  against 0.70. The three unfaithful synthesis items are hold11, hold13 and
  hold14. This is the same failure mode as the k=15 run, so reducing k did not
  fix extractor precision.
- Latency passes: p95 22.9s against 30s. Tokens are 4.7k total / 3.8k input per
  multi-book item, or 3.7k / 3.1k including the near-miss items; both readings
  fail the 3k bar.
- Near-miss routing stays single-hop. The near-miss entity hit fell from 0.80 to
  0.60 because hnear02 abstained and hnear03 missed, but near-miss behavior is
  not a gating bar. The printed `book_share` is near-miss citation validity
  (valid citations divided by total near-miss citations), not book coverage.
- Spend is estimated from character volume at the placeholder
  `OWL_CHAT_*_PRICE_PER_MTOK` settings. It excludes judge, reranker and embedder
  cost, so it is an order-of-magnitude figure, not a bill.
- The eval gate still covers the single-pass path; it is unchanged by this run.

## Decision

The pre-registered rule fails on faithfulness, the item-level citation Wilson
lower bound (which is unsatisfiable as written) and the 3k token bar on the
conservative total. The multi-book flag stays off. The bounded spike is
complete and there is no second cycle. The k=3 result is recorded as a negative
outcome: coverage and cost improved, but extractor precision, faithfulness and
token volume did not reach the bar.

## Reproduce

```
uv run python scripts/measure_multibook_generation.py \
  --fixture eval/fixtures/aggregation_holdout.jsonl \
  --per-book-k 3 --selection per_book \
  --run-id 20261106T233126Z
```

## Raw summary

```text
hold01   multi_book  route=multi_book books=4/4 ents=4/4 text=3/4 cite=4/4 faithful=True calls=8 14184ms
hold02   multi_book  route=multi_book books=3/3 ents=3/3 text=3/3 cite=3/3 faithful=True calls=8 12648ms
hold03   multi_book  route=multi_book books=3/3 ents=3/3 text=3/3 cite=3/3 faithful=True calls=8 15938ms
hold04   multi_book  route=multi_book books=5/6 ents=5/6 text=5/6 cite=5/5 faithful=True calls=8 17859ms
hold05   multi_book  route=multi_book books=3/6 ents=3/6 text=3/6 cite=3/7 faithful=True calls=8 17659ms
hold06   multi_book  route=multi_book books=7/7 ents=7/7 text=6/7 cite=7/7 faithful=True calls=8 20522ms
hold07   multi_book  route=multi_book books=4/5 ents=4/5 text=4/5 cite=4/4 faithful=True calls=8 17991ms
hold08   multi_book  route=multi_book books=5/5 ents=5/5 text=4/5 cite=7/7 faithful=True calls=8 16039ms
hold09   multi_book  route=multi_book books=7/7 ents=7/7 text=7/7 cite=7/7 faithful=True calls=8 20766ms
hold10   multi_book  route=multi_book books=4/4 ents=4/4 text=1/4 cite=4/4 faithful=True calls=8 12936ms
hold11   multi_book  route=multi_book books=4/4 ents=4/4 text=4/4 cite=4/5 faithful=False calls=8 15952ms
hold12   multi_book  route=multi_book books=7/7 ents=7/7 text=7/7 cite=7/7 faithful=True calls=8 22555ms
hold13   multi_book  route=multi_book books=4/5 ents=4/5 text=4/5 cite=6/6 faithful=False calls=8 22926ms
hold14   multi_book  route=multi_book books=2/3 ents=2/3 text=2/3 cite=2/2 faithful=False calls=8 8943ms
hold15   multi_book  route=single_hop books=2/3 ents=2/3 text=3/3 cite=5/7 faithful=False calls=1 4220ms
hnear01  near_miss   route=single_hop books=1/1 ents=3/3 text=1/1 cite=1/1 faithful=True calls=1 1832ms
hnear02  near_miss   route=single_hop books=0/1 ents=0/4 text=0/1 cite=0/0 faithful=None calls=0 88ms
hnear03  near_miss   route=single_hop books=0/1 ents=0/3 text=1/1 cite=0/1 faithful=True calls=1 1853ms
hnear04  near_miss   route=single_hop books=1/1 ents=4/4 text=1/1 cite=1/1 faithful=True calls=1 2081ms
hnear05  near_miss   route=single_hop books=1/1 ents=3/4 text=1/1 cite=3/3 faithful=False calls=1 11270ms

run: 20261106T233126Z
path=multi_book per_book_k=3 selection=per_book selection_floor=0.0 final_top_k=7 manifest: generator=qwen/qwen3-30b-a3b-instruct-2507 judge=deepseek/deepseek-v4.1-flash-1017 reranker=amazon.rerank-v1:0 pool=50 embedder=qwen3-embedding:0.6b chunking=500/75/200 rrf_k=60 quota=0
aggregate
  multi_book n=15 book_coverage=0.88 full_coverage=0.60 entity_completeness=0.88
  answer_text book_coverage=0.82 entity_completeness=0.82
  citation_validity=0.91 faithfulness=0.73 (n=15) abstention=0.00
  synthesis-only n=14 judged=14 citation_validity=0.93 faithfulness=0.79
  synthesis_items citation_pass=12/14 wilson_lower=0.60 faithful_wilson_lower=0.52
  near_miss n=5 entity_hit=0.60 book_share=0.83
  latency p50=16039ms p95=22926ms max=22926ms deadline=30s model_calls=113 input_tokens~57159 output_tokens~12731 spend~$0.0095
csv: /Users/tc/Documents/Github/owl-online/eval/results/20261106T233126Z-multibook-generation.csv
summary: {"coverage": 0.884, "completeness": 0.884, "answer_text_coverage": 0.817, "answer_text_completeness": 0.817, "citation_validity": 0.91, "faithfulness": 0.733, "synthesis_citation_validity": 0.93, "synthesis_faithfulness": 0.786, "synthesis_citation_items_pass": 12, "synthesis_citation_items_n": 14, "synthesis_citation_wilson_lower": 0.601, "synthesis_faithfulness_wilson_lower": 0.524, "latency_p50_ms": 16039.0, "latency_p95_ms": 22926.0, "latency_max_ms": 22926.0, "spend_usd": 0.0095}
```
