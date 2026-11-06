# Run record: #105 multi-book generation on the held-out set

- Date: 2026-11-06
- Run id: `20261106T093000Z`
- Ticket: #105 (V2)
- Config: `multi_book` (per-book k=15, final top-k 7, reranker on)
- Artifacts: `eval/results/20261106T093000Z-multibook-generation.csv` (local, gitignored)

## Configuration

| Field | Value |
|---|---|
| Path | `ask(multi_book=True)`; routed questions only |
| Generator | `qwen/qwen3-30b-a3b-instruct-2507` |
| Judge | `deepseek/deepseek-v4.1-flash-1017` |
| Reranker | `amazon.rerank-v1:0`, pool 50 |
| Embedder | `local` / `qwen3-embedding:0.6b`, 1024 dims |
| Chunking | size 500, overlap 75, min size 200 |
| Retrieval | per book, k=15 candidates per book, fan-out 4, final top-k 7 |
| Sub-query quota | 0 (global fusion) |
| Fixture | `eval/fixtures/aggregation_holdout.jsonl`, 15 multi-book, 5 near-miss, frozen |

The run exercises routing, per-book extraction, quote binding, synthesis and the
coverage statement. It is a generation run, not the retrieval-only aggregation
run in `2026-11-06-v2-holdout-routed-k7.md`.

## Per-item results

| Item | Route | Books | Entities | Answer text | Citations | Faithful | Calls | Latency |
|---|---|---|---:|---:|---:|---:|---:|---:|
| hold01 | multi_book | 4/4 | 4/4 | 3/4 | 4/4 | yes | 8 | 9261ms |
| hold02 | multi_book | 3/3 | 3/3 | 3/3 | 3/3 | yes | 8 | 6650ms |
| hold03 | multi_book | 3/3 | 3/3 | 3/3 | 3/4 | no | 8 | 8266ms |
| hold04 | multi_book | 6/6 | 6/6 | 6/6 | 7/7 | yes | 8 | 10796ms |
| hold05 | multi_book | 4/6 | 4/6 | 4/6 | 4/7 | yes | 8 | 11410ms |
| hold06 | multi_book | 7/7 | 7/7 | 7/7 | 7/7 | yes | 8 | 15195ms |
| hold07 | multi_book | 5/5 | 5/5 | 5/5 | 5/5 | yes | 8 | 15688ms |
| hold08 | multi_book | 5/5 | 5/5 | 5/5 | 7/7 | yes | 8 | 14131ms |
| hold09 | multi_book | 7/7 | 7/7 | 7/7 | 7/7 | yes | 8 | 11472ms |
| hold10 | multi_book | 4/4 | 4/4 | 1/4 | 4/4 | yes | 8 | 7977ms |
| hold11 | multi_book | 4/4 | 4/4 | 4/4 | 4/5 | no | 8 | 10243ms |
| hold12 | multi_book | 7/7 | 7/7 | 7/7 | 7/7 | yes | 8 | 16489ms |
| hold13 | multi_book | 5/5 | 5/5 | 3/5 | 5/6 | no | 8 | 30416ms |
| hold14 | multi_book | 3/3 | 3/3 | 2/3 | 3/3 | yes | 8 | 7853ms |
| hold15 | single_hop | 1/3 | 1/3 | 3/3 | 1/4 | no | 1 | 3660ms |
| hnear01 | single_hop | 1/1 | 3/3 | 1/1 | 1/1 | yes | 1 | 1128ms |
| hnear02 | single_hop | 1/1 | 4/4 | 1/1 | 2/3 | yes | 1 | 1904ms |
| hnear03 | single_hop | 0/1 | 0/3 | 1/1 | 0/1 | yes | 1 | 1333ms |
| hnear04 | single_hop | 1/1 | 4/4 | 1/1 | 1/1 | yes | 1 | 1277ms |
| hnear05 | single_hop | 1/1 | 3/4 | 1/1 | 2/3 | no | 1 | 3149ms |

Books and entities use the cited evidence: a book counts when the answer cites a
chunk from it that names an expected entity. Answer text is stricter: the entity
must appear in that book's answer text. The gap is extractor precision.

## Aggregate

| Metric | Value | Bar | Result |
|---|---:|---:|---|
| Book coverage | 0.93 | >= 0.75 | pass |
| Full coverage | 0.87 | n/a | n/a |
| Entity completeness | 0.93 | >= 0.70 | pass |
| Answer-text coverage | 0.86 | n/a | n/a |
| Answer-text completeness | 0.86 | n/a | n/a |
| Citation validity | 0.89 | >= 0.90 | fail |
| Faithfulness | 0.73 (n=15) | no worse than 0.93 | fail |
| Abstention | 0.00 | n/a | n/a |
| Near-miss entity hit | 0.80 | n/a | n/a |
| Near-miss book share | 0.67 | n/a | n/a |
| Latency p50 | 10796ms | n/a | n/a |
| Latency p95 | 16489ms | n/a | n/a |
| Model calls | 113 | n/a | n/a |
| Input tokens (est.) | 206049 | n/a | n/a |
| Output tokens (est.) | 13588 | n/a | n/a |
| Spend (est.) | $0.0247 | n/a | n/a |

## Printed summary

```text
run: 20261106T093000Z
path=multi_book per_book_k=15 final_top_k=7 manifest: generator=qwen/qwen3-30b-a3b-instruct-2507 judge=deepseek/deepseek-v4.1-flash-1017 reranker=amazon.rerank-v1:0 pool=50 embedder=qwen3-embedding:0.6b chunking=500/75/200 rrf_k=60 quota=0
aggregate
  multi_book n=15 book_coverage=0.93 full_coverage=0.87 entity_completeness=0.93
  answer_text book_coverage=0.86 entity_completeness=0.86
  citation_validity=0.89 faithfulness=0.73 (n=15) abstention=0.00
  near_miss n=5 entity_hit=0.80 book_share=0.67
  latency p50=10796ms p95=16489ms model_calls=113 input_tokens~206049 output_tokens~13588 spend~$0.0247
summary: {"coverage": 0.933, "completeness": 0.933, "answer_text_coverage": 0.862, "answer_text_completeness": 0.862, "citation_validity": 0.887, "faithfulness": 0.733, "latency_p50_ms": 10796.0, "latency_p95_ms": 16489.0, "spend_usd": 0.0247}
```

## Reading notes

The path is not ready to enable. Coverage and completeness clear their bars, but
citation validity is just under 0.90 and faithfulness is well below the 0.93
single-pass baseline.

- Citation validity 0.89: two items cite a chunk that is not relevant to the
  expected entity. hold03 cites a dimly lit room chunk for the Room of
  Requirement; hold15 is a single-hop answer with one relevant citation of four.
- Faithfulness 0.73: five of fifteen answers were judged unfaithful. The failures
  are extractor precision, not quote fabrication: every kept line is verbatim in
  its cited chunk, but the chunk can be tangential. hold13 cites a Firenze line
  for book 7 that does not say Firenze is a centaur; hold03 cites a room chunk
  that is not the Room of Requirement.
- Answer-text coverage 0.86 is lower than cited-evidence coverage 0.93 because
  the extractor sometimes quotes a sentence that names an instance rather than
  the fixture's canonical term. hold10 cites Ollivander chunks but the answer
  text does not repeat the name for three of four books.
- hold15 routes `single_hop` and is the one router miss, by design (cue-free).
  It is scored through the single-pass path, which is the shipped default.
- Near-miss entity hit is 0.80, down from 1.00 in the retrieval run. hnear03
  cites no relevant chunk; hnear05 is judged unfaithful.
- Latency p50 is about 11s and p95 about 16s for eight model calls. Spend is
  about $0.025 for 15 items at list prices.
- Two earlier runs of the measurement script (`20261106T090000Z`,
  `20261106T091500Z`) are discarded: the script scored entities anywhere in the
  answer instead of per book, and the coverage statement could claim a book
  whose line was dropped. Both bugs are fixed before this run.

## Decision

`OWL_MULTI_BOOK` stays false. #105 stays open.

The next change is extraction precision: the extractor must reject a chunk that
only shares a keyword with the question. Tune on `aggregation.jsonl`, then rerun
this held-out measurement once and record it.
