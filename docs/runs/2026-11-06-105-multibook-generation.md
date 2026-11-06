# Run record: #105 multi-book generation on the held-out set

- Date: 2026-11-06
- Run id: `20261106T110000Z`
- Ticket: #105 (V2)
- Config: `multi_book` (per-book k=15, final top-k 7, reranker on)
- Artifacts: `eval/results/20261106T110000Z-multibook-generation.csv` (local, gitignored)

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
| Deadline | `OWL_ASK_TIMEOUT_S` 30s |

The run exercises routing, per-book extraction, quote binding, synthesis and the
coverage statement. It is a generation run, not the retrieval-only aggregation
run in `2026-11-06-v2-holdout-routed-k7.md`.

This record deviates from the template: a generation run has no gold-set
Retrieval or Abstention tables, so those sections are replaced by the per-item
and aggregate tables below. The printed summary is this script's output, not
`render_run()`.

## Per-item results

| Item | Route | Books | Entities | Answer text | Citations | Faithful | Calls | Latency |
|---|---|---|---:|---:|---:|---:|---:|---:|
| hold01 | multi_book | 4/4 | 4/4 | 3/4 | 4/5 | yes | 8 | 10486ms |
| hold02 | multi_book | 3/3 | 3/3 | 3/3 | 3/3 | yes | 8 | 5814ms |
| hold03 | multi_book | 1/3 | 1/3 | 2/3 | 1/4 | no | 8 | 6967ms |
| hold04 | multi_book | 5/6 | 5/6 | 5/6 | 5/5 | yes | 8 | 9552ms |
| hold05 | multi_book | 4/6 | 4/6 | 4/6 | 4/7 | yes | 8 | 11379ms |
| hold06 | multi_book | 7/7 | 7/7 | 7/7 | 7/7 | yes | 8 | 12494ms |
| hold07 | multi_book | 5/5 | 5/5 | 5/5 | 5/5 | yes | 8 | 11680ms |
| hold08 | multi_book | 5/5 | 5/5 | 5/5 | 7/7 | yes | 8 | 14330ms |
| hold09 | multi_book | 5/7 | 5/7 | 6/7 | 5/6 | yes | 8 | 9347ms |
| hold10 | multi_book | 4/4 | 4/4 | 2/4 | 4/4 | yes | 8 | 7587ms |
| hold11 | multi_book | 4/4 | 4/4 | 4/4 | 4/5 | no | 8 | 9728ms |
| hold12 | multi_book | 6/7 | 6/7 | 6/7 | 6/6 | yes | 8 | 13214ms |
| hold13 | multi_book | 4/5 | 4/5 | 2/5 | 4/4 | no | 8 | 9311ms |
| hold14 | multi_book | 3/3 | 3/3 | 2/3 | 3/3 | yes | 8 | 6862ms |
| hold15 | single_hop | 1/3 | 1/3 | 3/3 | 1/4 | no | 1 | 4535ms |
| hnear01 | single_hop | 1/1 | 3/3 | 1/1 | 1/1 | yes | 1 | 1388ms |
| hnear02 | single_hop | 1/1 | 4/4 | 1/1 | 2/3 | yes | 1 | 1584ms |
| hnear03 | single_hop | 0/1 | 0/3 | 1/1 | 0/1 | yes | 1 | 1337ms |
| hnear04 | single_hop | 1/1 | 4/4 | 1/1 | 1/1 | yes | 1 | 2113ms |
| hnear05 | single_hop | 1/1 | 3/4 | 1/1 | 2/3 | no | 1 | 4200ms |

Books and entities use the cited evidence: a book counts when the answer cites a
chunk from it that names an expected entity. Answer text is stricter: the entity
must appear in that book's answer text. The gap is extractor precision.

## Aggregate

| Metric | Value | Bar | Result |
|---|---:|---:|---|
| Book coverage | 0.84 | >= 0.75 | pass |
| Full coverage | 0.53 | n/a | n/a |
| Entity completeness | 0.84 | >= 0.70 | pass |
| Answer-text coverage | 0.81 | n/a | n/a |
| Answer-text completeness | 0.81 | n/a | n/a |
| Citation validity, all 15 | 0.84 (63/75) | n/a | n/a |
| Citation validity, synthesis 14 | 0.87 (62/71) | >= 0.90 | fail |
| Faithfulness, all 15 | 0.73 (11/15) | n/a | n/a |
| Faithfulness, synthesis 14 | 0.79 (11/14) | no worse than 0.93 | fail |
| Abstention | 0.00 | n/a | n/a |
| Near-miss entity hit | 0.80 | n/a | n/a |
| Near-miss book share | 0.67 | n/a | n/a |
| Latency p50 | 9552ms | n/a | n/a |
| Latency p95 (nearest rank) | 14330ms | < 30000ms | pass |
| Latency max | 14330ms | < 30000ms | pass |
| Model calls | 113 | n/a | n/a |
| Input tokens (est.) | 205859 | n/a | n/a |
| Output tokens (est.) | 13256 | n/a | n/a |
| Spend (est.) | $0.0246 | n/a | n/a |

The ticket's "after synthesis" bar applies to the 14 items that actually ran the
synthesis path. hold15 is a multi-book fixture item that the router sends
single-hop, so it is excluded from the synthesis population and reported
separately.

Spend is estimated from character volume at the placeholder
`OWL_CHAT_*_PRICE_PER_MTOK` settings in `app/config.py`. It excludes judge
tokens. It is an order-of-magnitude figure, not a bill.

## Printed summary

```text
hold01   multi_book  route=multi_book books=4/4 ents=4/4 text=3/4 cite=4/5 faithful=True calls=8 10486ms
hold02   multi_book  route=multi_book books=3/3 ents=3/3 text=3/3 cite=3/3 faithful=True calls=8 5814ms
hold03   multi_book  route=multi_book books=1/3 ents=1/3 text=2/3 cite=1/4 faithful=False calls=8 6967ms
hold04   multi_book  route=multi_book books=5/6 ents=5/6 text=5/6 cite=5/5 faithful=True calls=8 9552ms
hold05   multi_book  route=multi_book books=4/6 ents=4/6 text=4/6 cite=4/7 faithful=True calls=8 11379ms
hold06   multi_book  route=multi_book books=7/7 ents=7/7 text=7/7 cite=7/7 faithful=True calls=8 12494ms
hold07   multi_book  route=multi_book books=5/5 ents=5/5 text=5/5 cite=5/5 faithful=True calls=8 11680ms
hold08   multi_book  route=multi_book books=5/5 ents=5/5 text=5/5 cite=7/7 faithful=True calls=8 14330ms
hold09   multi_book  route=multi_book books=5/7 ents=5/7 text=6/7 cite=5/6 faithful=True calls=8 9347ms
hold10   multi_book  route=multi_book books=4/4 ents=4/4 text=2/4 cite=4/4 faithful=True calls=8 7587ms
hold11   multi_book  route=multi_book books=4/4 ents=4/4 text=4/4 cite=4/5 faithful=False calls=8 9728ms
hold12   multi_book  route=multi_book books=6/7 ents=6/7 text=6/7 cite=6/6 faithful=True calls=8 13214ms
hold13   multi_book  route=multi_book books=4/5 ents=4/5 text=2/5 cite=4/4 faithful=False calls=8 9311ms
hold14   multi_book  route=multi_book books=3/3 ents=3/3 text=2/3 cite=3/3 faithful=True calls=8 6862ms
hold15   multi_book  route=single_hop books=1/3 ents=1/3 text=3/3 cite=1/4 faithful=False calls=1 4535ms
hnear01  near_miss   route=single_hop books=1/1 ents=3/3 text=1/1 cite=1/1 faithful=True calls=1 1388ms
hnear02  near_miss   route=single_hop books=1/1 ents=4/4 text=1/1 cite=2/3 faithful=True calls=1 1584ms
hnear03  near_miss   route=single_hop books=0/1 ents=0/3 text=1/1 cite=0/1 faithful=True calls=1 1337ms
hnear04  near_miss   route=single_hop books=1/1 ents=4/4 text=1/1 cite=1/1 faithful=True calls=1 2113ms
hnear05  near_miss   route=single_hop books=1/1 ents=3/4 text=1/1 cite=2/3 faithful=False calls=1 4200ms

run: 20261106T110000Z
path=multi_book per_book_k=15 final_top_k=7 manifest: generator=qwen/qwen3-30b-a3b-instruct-2507 judge=deepseek/deepseek-v4.1-flash-1017 reranker=amazon.rerank-v1:0 pool=50 embedder=qwen3-embedding:0.6b chunking=500/75/200 rrf_k=60 quota=0
aggregate
  multi_book n=15 book_coverage=0.84 full_coverage=0.53 entity_completeness=0.84
  answer_text book_coverage=0.81 entity_completeness=0.81
  citation_validity=0.84 faithfulness=0.73 (n=15) abstention=0.00
  synthesis-only n=14 citation_validity=0.87 faithfulness=0.79
  near_miss n=5 entity_hit=0.80 book_share=0.67
  latency p50=9552ms p95=14330ms max=14330ms deadline=30s model_calls=113 input_tokens~205859 output_tokens~13256 spend~$0.0246
summary: {"coverage": 0.836, "completeness": 0.836, "answer_text_coverage": 0.813, "answer_text_completeness": 0.813, "citation_validity": 0.84, "faithfulness": 0.733, "synthesis_citation_validity": 0.873, "synthesis_faithfulness": 0.786, "latency_p50_ms": 9552.0, "latency_p95_ms": 14330.0, "latency_max_ms": 14330.0, "spend_usd": 0.0246}
```

## Reading notes

The path is not ready to enable. Coverage and completeness clear their bars, but
citation validity is below 0.90 and faithfulness is well below the 0.93
single-pass baseline.

- Citation validity is 0.87 on the 14 synthesis items and 0.84 on all 15. Twelve
  of 75 citations are not relevant to the expected entity. The items with
  invalid citations are hold01 (1), hold03 (3), hold05 (3), hold09 (1), hold11
  (1) and hold15 (3). hold15 is the single-hop item, so it is not part of the
  synthesis bar.
- Faithfulness is 11/15, or 11/14 on the synthesis items. Four answers were
  judged unfaithful: hold03, hold11, hold13 and hold15. The failures are
  extractor precision, not quote fabrication: every kept line is verbatim in its
  cited chunk, but the chunk can be tangential.
- hold03 cites a dimly lit room chunk for the Room of Requirement. hold13 cites
  a Firenze line for book 7 that does not say Firenze is a centaur. hold11 cites
  a chunk that supports only part of its line.
- Answer-text coverage 0.81 is lower than cited-evidence coverage 0.84 because
  the extractor sometimes quotes a sentence that names an instance rather than
  the fixture's canonical term.
- hold15 routes `single_hop` and is the one router miss, by design (cue-free).
  It is scored through the single-pass path, which is the shipped default.
- Near-miss entity hit is 0.80. That matches the held-out routed retrieval run
  (`2026-11-06-v2-holdout-routed-k7.md`, 0.80), not the development fixture
  (1.00). hnear03 cites no relevant chunk; hnear05 is judged unfaithful.
- Latency p95 is 14.3s and the slowest item is also 14.3s, under the 30s
  `/ask` deadline. The earlier recorded p95 of 16.5s used the wrong index and
  hid a 30.4s item; that run is superseded.
- Two earlier runs of the measurement script (`20261106T090000Z`,
  `20261106T093000Z`) are discarded: the script scored entities anywhere in the
  answer instead of per book, the coverage statement could claim a dropped book,
  and p95 used the wrong index. All three are fixed before this run.

## Decision

`OWL_MULTI_BOOK` stays false. #105 stays open.

The next change is extraction precision: the extractor must reject a chunk that
only shares a keyword with the question, and front-matter chunks must not be
retrieved as evidence. Tune on `aggregation.jsonl`, then rerun this held-out
measurement once and record it.
