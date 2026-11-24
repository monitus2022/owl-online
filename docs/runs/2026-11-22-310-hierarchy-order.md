# Run record: #310 instruction hierarchy ordering

- Date: 2026-11-22
- Run ids (experiment record): corpus `20261122T120323Z`, RAG `20261122T122234Z`
- Ticket: #310 (move the instruction hierarchy before the grounding rules)
- Config: `pinned` (corpus), `rag-eval` (RAG)
- Baseline: corpus `20261106T214850Z` (`eval/results/baseline.csv`), RAG `20261113T082614Z` (`eval/results/rag-baseline.json`)
- Artifacts: `eval/results/20261122T120323Z.csv`, `eval/results/rag-20261122T122234Z.json` (local, gitignored)

## Configuration

| Field | Value |
|---|---|
| Generator | `openrouter/qwen/qwen3-30b-a3b-instruct-2507`, temperature 0.0 |
| Judge | `openrouter/deepseek/deepseek-v4.1-flash-1017`, temperature 0.0 |
| Embedder | local `qwen3-embedding:0.6b` |
| Reranker | Bedrock `amazon.rerank-v1:0`, pool 50, floor 0.0 |
| Chunking | size 500, overlap 75, min size 200 |
| Retrieval | top-k 5, rrf_k 60, candidates 50, sub-query quota 0 |
| Retry budget | 1 |
| Corpus gold | 61 items, 51 answerable, judged sample 15 |
| Lesson fixture | `eval/rag/fixtures/lesson.jsonl`, SHA-256 `de4e373b1acf`, judged sample 30 |
| Multi-turn fixture | `eval/rag/fixtures/multiturn.jsonl`, SHA-256 `1a86ba5c554d` |
| Lesson settings | top-k 3, cosine floor 0.58, fallback on, persona on |
| Index text hash | `aca4c57462d449f5` |

## Why

#307 added the instruction hierarchy to every prompt as the last paragraph,
after the citation and abstention contract. The full corpus eval then failed the
grounded-rate gate:

| Run id | Prompt order | Grounded | Faithful | Gate |
|---|---|---:|---:|---|
| `20261122T111548Z` | hierarchy appended last | 11/15 (0.733) | 12/15 | FAIL, dropped 0.1333 (band 0.10) |
| `20261122T111630Z` | same, repeat | 11/15 (0.733) | 12/15 | FAIL |
| `20261122T111807Z` | hierarchy disabled | 12/15 (0.800) | 13/15 | PASS |
| `20261122T111929Z` | hierarchy prepended | 12/15 (0.800) | 12/15 | PASS |
| `20261122T120323Z` | shipped, constants prepended | 13/15 (0.867) | 13/15 | PASS |

The appended line is the last thing the model reads and it displaced the
citation rule as the closing instruction. Prepending it restores the gate.

## Composition

- Every prompt constant opens with the hierarchy exactly once.
- The corpus answer prompts end with the abstention contract. In a served
  request the persona suffix, the student note and the conversation note are
  appended after it.
- The lesson composition puts the hierarchy first, then the persona preamble,
  then the grounding rules, then the voice reminder. It closes with the voice
  reminder, not the contract.
- Retry prompts keep their retry sentence as the last line.
- The corpus eval runs persona-off; the RAG eval runs persona-on. The RAG run
  below measured the persona composition.

## Corpus metrics, shipped run

| Metric | Baseline | Shipped | Delta |
|---|---:|---:|---:|
| Hit@5 | 0.76 | 0.76 | 0.00 |
| Recall@5 | 0.65 | 0.65 | 0.00 |
| MRR | 0.51 | 0.51 | 0.00 |
| Abstention | 1.00 | 1.00 | 0.00 |
| Faithful | 13/15 | 13/15 | 0 |
| Grounded rate | 0.8667 | 0.8667 | 0.00 |
| F1 | 0.3121 | 0.31 | within band |
| Novel entity rate | 0.0000 | 0.0667 | 1 answer; reported, not gated |

## RAG metrics, shipped run

| Metric | Baseline | Shipped | Delta |
|---|---:|---:|---:|
| Lesson citation recall | 0.9615 | 0.9615 | 0.00 |
| Lesson scope accuracy | 0.9839 | 0.9839 | 0.00 |
| Lesson false refusal | 0.0000 | 0.0000 | 0.00 |
| Lesson off-pack citation recall | 1.0000 | 1.0000 | 0.00 |
| Lesson faithfulness | 4/30 (0.1333) | 11/30 (0.3667) | +7 items |
| Lesson length violations | 11 | 12 | reported, not gated |
| Multi-turn citation accuracy | 0.5758 | 0.6061 | +0.0303 |
| Multi-turn comparison accuracy | 0.1667 | 0.2500 | +0.0833 |
| Multi-turn false refusal | 0.0909 | 0.0606 | -0.0303 |
| Context contamination | 0 | 0 | 0 |

## Slices, corpus

| Slice | n | Hit@5 | Recall@5 | MRR | Grounded | Faithful |
|---|---:|---:|---:|---:|---:|---:|
| overall | 51 | 0.76 | 0.65 | 0.51 | 13/15 | 13/15 |
| multi_part | 9 | 0.67 | 0.46 | 0.46 | 3/5 | 3/5 |
| named_reference | 8 | 1.00 | 1.00 | 0.78 | 5/5 | 5/5 |
| simple | 34 | 0.74 | 0.62 | 0.46 | 5/5 | 5/5 |

## Slices, RAG

| Slice | n | Scope | Citation | False refusal |
|---|---:|---:|---:|---:|
| mixed | 1 | 1.0000 | 1.0000 | 0.0000 |
| off-pack | 1 | 1.0000 | 1.0000 | 0.0000 |

## Off-pack sampling note

The off-pack lesson slice has one fixture (`lesson-dada-13`). Two earlier RAG
runs (`20261122T113354Z`, `20261122T113448Z`) scored its citation recall at 0.0
and failed the gate. Those runs also reported citation recall 0.9327, length
violations 14 and faithfulness 0.2667 (8/30), so they are not comparable
samples. Their cache key included an earlier lesson composition; the shipped
composition ran with a fresh cache (`20261122T122234Z`) and scored the off-pack
item at 1.0 with citation recall 0.9615.

The off-pack metric is any-hit over `expected_chunk_ids`, so citing two of three
expected ids scores 1.0. One fixture is still a noisy gate; stabilising it needs
more off-pack fixtures, which is a fixture change.

## Run-id note

`20261122T112218Z` and `20261122T120323Z` replay the same cached generation with
the same prompt and report identical metrics. They are not independent samples;
the record cites `20261122T120323Z` as the shipped id.

## Reading

- Prompt order matters on this model: a closing guard line can cost grounding.
  The hierarchy belongs at the top, and the citation/abstention contract closes
  the first-attempt answer prompts.
- Corpus retrieval, abstention, faithfulness and grounded rate are unchanged
  against the baseline within the gate bands.
- Lesson citation recall matches the baseline; faithfulness improves from 4/30
  to 11/30.
- Multi-turn citation and comparison accuracy improve, and false refusal falls.
- Lesson length and novel-entity rates are reported but not gated.
- The one novel-entity hit is the connective `Additionally`, not an invented
  name.

## Reproduce

```text
uv run python scripts/run_eval.py \
  --chunks /path/to/data/chunks.jsonl \
  --index /path/to/data/index/chroma
uv run python scripts/run_eval.py --check
uv run python scripts/run_rag_eval.py --cache /path/to/rag-cache
uv run python scripts/run_rag_eval.py --check
```

## Printed summary, corpus

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
  overall                n=15  answered=15  abstained=0   EM=0.00 F1=0.31 faithful=13/15 (0.87) judge correct=12 partial=3 wrong=0 grounded=13 judge_parse=0 faithful_parse=0
  multi_part             n=5   answered=5   abstained=0   EM=0.00 F1=0.36 faithful=3/5 (0.60) judge correct=2 partial=3 wrong=0 grounded=3 judge_parse=0 faithful_parse=0
  named_reference        n=5   answered=5   abstained=0   EM=0.00 F1=0.28 faithful=5/5 (1.00) judge correct=5 partial=0 wrong=0 grounded=5 judge_parse=0 faithful_parse=0
  simple                 n=5   answered=5   abstained=0   EM=0.00 F1=0.29 faithful=5/5 (1.00) judge correct=5 partial=0 wrong=0 grounded=5 judge_parse=0 faithful_parse=0

novel entities: 1/15 answers (0.07), tokens: Additionally

wrote /Users/tc/Documents/Github/owl-online-charms-calibration/eval/results/20261122T120323Z.csv
```

## Printed summary, RAG

```text
run_id: 20261122T122234Z
config: rag-eval
generator: openrouter/qwen/qwen3-30b-a3b-instruct-2507
judge: deepseek/deepseek-v4.1-flash-1017
lesson fixture: de4e373b1acf (judged sample 30)
multi-turn fixture: 1a86ba5c554d

lesson
  total=62 answerable=52 unanswerable=10
  selection precision@3=0.6405 recall@3=0.9660
  scope accuracy=0.9839 citation recall=0.9615
  false refusal=0.0000 abstention accuracy=1.0000
  citation validity=1.0000 source hash=1.0000
  mixed n=1 scope=1.0000 citation=1.0000 false refusal=0.0000
  off-pack n=1 scope=1.0000 citation=1.0000 false refusal=0.0000
  mean words=206 max=318 at-or-over-limit=12
  judged=30 faithfulness=0.3667

multi-turn
  conversations=17 turns=36
  query accuracy=1.0000 mode accuracy=0.8889
  citation accuracy=0.6061 false refusal=0.0606
  abstention accuracy=1.0000
  referral target accuracy=0.0000 comparison accuracy=0.2500
  context contamination=0

errors: 0
```
