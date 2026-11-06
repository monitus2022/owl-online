# Mini-eval

A deliberately small eval for V1 (ticket #51): retrieval scored on chunk ids,
and a judged sample of generated answers. The full harness as a CI gate is V2
(#9-#12).

## Layout

| Path | Contents |
|---|---|
| `eval/harness/gold.py` | `GoldItem`, `load_gold` |
| `eval/harness/aggregation.py` | multi-book fixture loader, coverage and citation metrics |
| `eval/harness/retrieval.py` | Hit@k, Recall@k, MRR |
| `app/pipeline/retrieve/multibook.py` | per-book retrieval, merge and fan-out cap |
| `eval/harness/abstention.py` | refusal counts and rate |
| `eval/harness/generation.py` | EM, F1, judge buckets, aggregates |
| `eval/harness/judging.py` | judge prompts, reply parsers, sample selection |
| `eval/harness/cache.py` | `CachedLlm` |
| `eval/results.py` | result CSV, baseline copy and diff |
| `eval/thresholds.toml` | baseline, gate bands and slice kinds |
| `eval/test_harness.py` | harness tests, no network |
| `eval/test_aggregation.py` | aggregation fixture and metric tests, no network |
| `tests/test_multibook.py` | per-book retrieval tests, no network |
| `eval/fixtures/aggregation.jsonl` | 10 multi-book questions and 5 near-misses |
| `eval/fixtures/aggregation_holdout.jsonl` | 15 held-out multi-book questions and 5 near-misses |
| `eval/test_results.py` | result CSV tests, no network |
| `eval/runner.py` | one run: compose, score, write the CSV |
| `eval/report.py` | result rows and printed summary |
| `eval/check.py` | baseline diff and gate for `--check` |
| `eval/test_check.py` | gate tests, no network |
| `eval/test_report.py` | row and rendering tests, no network |
| `scripts/run_eval.py` | CLI params and dispatch |
| `scripts/measure_aggregation.py` | aggregation fixture measurement |

`eval/harness/__init__.py` re-exports the public names, so callers keep
importing from `eval.harness`.

```text
gold/questions.jsonl (61 items)
        |
        +-- retrieval pass --> Hit@k, Recall@k, MRR        (51 answerable)
        +-- abstention pass --> refused / n                 (10 unanswerable)
        +-- judged sample ---> EM, F1, judge buckets,
                               faithfulness                (15 answerable)
        |
        v
eval/results/<timestamp>.csv   (one row per config, slice, metric)
        |
        +-- --write-baseline --> eval/results/baseline.csv
        +-- --check ----------> deltas + gate pass/fail
        |
        v
docs/runs/<date>-<ticket>-<slug>.md   (committed run record)
```

## What it measures

- Retrieval: `Hit@k`, `Recall@k`, `MRR` on the chunk ids that answer each gold question.
- Abstention: how often `ask()` refuses on questions the corpus cannot answer.
- Generation: a sample of answers graded by a second model (correct / partial /
  wrong, and grounded / ungrounded).

## Current baseline

Pinned run `20261106T060737Z`, quota 0; canonical record: `docs/runs/2026-11-06-v2-quota-baseline.md`:

| Metric | Value |
|---|---:|
| Hit@5 overall | 0.76 |
| Hit@5 multi-part | 0.67 |
| Hit@5 named reference | 1.00 |
| Judge correct | 13/14 |
| Faithful | 13/14 |
| Abstention on unanswerable | 10/10 |

The aggregation fixture adds cross-book coverage: 0.46 book coverage, 0.45 entity
completeness and 0.00 full coverage. The routed per-book prototype reaches 0.79
coverage and 0.76 completeness at equal k=7, but citation validity is 0.56 and
it is not wired into chat. The router separates 10/10 multi-book items from 0/5
near-misses on the fixture, in-sample.

## Gold set

`gold/questions.jsonl`: 51 answerable and 10 unanswerable items. Each item is an
original question plus the expected chunk ids and a short reference answer. No
corpus text is stored; ids and short answers only.

| Slice | Items | Purpose |
|---|---|---|
| `simple` | 34 | single-fact questions across all seven books |
| `named_reference` | 8 | the question names a book and chapter |
| `multi_part` | 9 | the question asks two or more things, and both/each must be retrieved |
| `near_miss_unanswerable` | 5 | topically close to the corpus but not answerable from it |
| `off_topic` | 5 | clearly outside the corpus |

Unanswerable items carry a `reason` instead of evidence ids. Answerable items
carry locatable evidence ids, checked against the corpus before they were added.

## Aggregation fixture

`fixtures/aggregation.jsonl`: 10 true multi-book questions and 5 near-misses that
sound plural but are single-hop. A multi-book item lists the expected entities
for each book, not one reference answer. A near-miss lists one book, so a plural
count alone cannot pass as multi-book.

`scripts/measure_aggregation.py` scores retrieval on:

| Metric | Meaning |
|---|---|
| Book coverage | fraction of expected books with a retrieved chunk containing an expected entity |
| Full coverage | fraction of multi-book items with every expected book covered |
| Entity completeness | fraction of expected entities found in the retrieved set |
| Citation validity | fraction of retrieved chunks from an expected book that also contain an expected entity for that book |
| Near-miss entity hit | fraction of near-miss items with at least one expected entity |
| Near-miss entity completeness | fraction of near-miss expected entities found |
| Near-miss book precision | fraction of near-miss chunks that are relevant to the single expected book |

The script also scores the deterministic router on the fixture: precision and
recall for `multi_book` versus `near_miss`. The cue set was chosen after seeing
the fixture, so a perfect score is in-sample and not a generalisation claim.

`--strategy` selects the retrieval path: `single_hop` is the current one-pass
baseline, `multi_book` runs every item through the per-book path, and `routed`
uses the router so near-misses stay single-hop. The per-book path is capped at
seven map calls with a fan-out of four.

`fixtures/aggregation_holdout.jsonl` is the held-out set: 15 multi-book
questions and 5 near-misses, written before tuning and not used to change the
cues or the path. Held-out retrieval at k=7:

| Metric | Single-hop | Routed per-book |
|---|---:|---:|
| Book coverage | 0.68 | 0.77 |
| Full coverage | 0.13 | 0.47 |
| Entity completeness | 0.68 | 0.77 |
| Citation validity | 0.74 | 0.51 |

The router scores 1.00 precision and 0.93 recall on the held-out set. The one
miss is `How many books mention an Animagus?`, which has no coverage cue. The
held-out set is frozen; failures are recorded, not fixed on this set.

The script verifies every expected entity against the corpus before measuring, so
the fixture cannot drift into invented facts. It is retrieval only; synthesis
faithfulness is measured with the multi-book path.

## Run

```
uv run python scripts/run_eval.py
```

This writes `eval/results/<timestamp>.csv`, one row per configuration, slice and
metric. Every row repeats the manifest values (models, chunking, `top_k`,
`rrf_k`, candidate count, embedder) so two runs stay comparable.

Pin the current run as the baseline:

```
uv run python scripts/run_eval.py --write-baseline
```

Diff the current run against the baseline:

```
uv run python scripts/run_eval.py --check
```

`--check` prints per-metric deltas, lists metrics that appear on only one side,
and applies the gate in `eval/thresholds.toml`. It exits 0 with `gate: PASS` when
every gated metric stays inside its band, and exits 1 with `gate: FAIL` when one
drops further, a gated metric is missing on either side, or a value is not a
finite number. The TOML `baseline` key is the default; pass `--baseline` only to
compare against a different file. It also refuses to diff two runs whose recorded
manifest values differ (models, chunking, retrieval settings, judged sample, gold
set hash or rerank floor), because those deltas would not be comparable. The CI
workflow that runs this on pull requests is still open in #16.

Bands are absolute. For rate metrics the effective band is `max(base, 1 / n)` for
that slice, so one item is normally allowed: 0.05 on overall retrieval with n=50,
0.125 on an 8-item slice, 0.067 on the 15-item F1 sample, and 0.20 on a 5-item
slice. The exception is over-abstention, which fails through `judged` and
`faithfulness_n` as well as `abstained_rate`, because losing an answer is not a
sampling artifact. The gate treats metrics by direction:

| Group | Metrics | Failure rule |
|---|---|---|
| Sample invariants | `retrieval_n`, `abstention_n`, `generation_n` | any change |
| Quality, drop | Hit@k, Recall@k, MRR, F1, faithfulness rate, judge-correct rate, grounded rate, abstention rate | drop beyond band |
| Answerability, drop | `judged`, `faithfulness_n` | drop beyond band |
| Quality, rise | `abstained_rate`, `judge_parse_failures`, `faithful_parse_failures` | rise beyond band |

Outcome counts (`answered`, `abstained`, `faithful`, `grounded`, the judge buckets)
stay in the CSV as diagnostics but are not gated directly; their rates carry the
quality signal, so an improvement cannot fail the gate. A gold-set or sample
change fails through the sample invariants instead of hiding inside an average.
EM is reported but not gated.

`[slice_kinds]` in the TOML marks each slice as `answerable` or `unanswerable`;
a new slice must be added there before the gate can score it. `--sample` must be
at least the number of answerable slices, otherwise a slice has no generation
rows and the gate fails closed.

Generation and judge calls are pinned to temperature 0, and the result rows
record `generator_temperature` and `judge_temperature`. The cache key carries the
temperature variant, so a cached reply from an earlier sampling setup is not
reused. The rows also record `subquery_quota`, so the gate refuses to compare a
quota-2 experiment with the quota-0 baseline. `--k` controls the retrieval cutoff
and `--sample` controls the judged sample. The sample is taken round-robin across
the answerable slices, so the default of 15 covers simple, named and multi-part.

A clean checkout cannot run the full eval: the corpus and Chroma index are host
data and stay out of git. The CI workflow will either run on a self-hosted runner
with `/data` mounted or restore a private index artifact; that decision is part of
#16 before `eval.yml` is written. Use `--latest <csv>` in CI so the gate scores
the artifact the job produced instead of whatever file sorts last. Until the CI
cache is pinned, a cold run can still move a stochastic metric inside its
one-item band; the bands are sized for that, and the re-pin procedure is a new
baseline run plus a new record.

## Result files

| Path | Committed | Purpose |
|---|---|---|
| `eval/results/<timestamp>.csv` | no | one run, gitignored |
| `eval/results/baseline.csv` | yes | the pinned comparison point |

The pinned V2 baseline is the D3 run `20261104T154503Z`, recorded as
`docs/runs/2026-11-04-v2-d3-retrieval.md`. Earlier D1 runs are kept as separate
records because their metric definitions and sampling changed. Rerun
`--write-baseline` only after a deliberate configuration change, and add a new
record instead of editing the old one.

## Run record

Every finished run gets a committed Markdown record under `docs/runs/`. The CSV
is the data; the record is the readable version for review and for showing how
the strategy moved between runs.

After the pipeline finishes, before closing the ticket:

1. Take the run id the script prints at the end (it is also the CSV filename).
2. Copy the template in `docs/runs/README.md` to
   `docs/runs/YYYY-MM-DD-<ticket>-<slug>.md`.
3. Fill in the configuration, retrieval, abstention and generation tables, then
   the reading notes. Paste the `render_run` output into the raw summary block,
   including its `wrote` lines; the final `next: write a run record` line is a
   reminder, not part of the summary.
4. Add a row to the Runs table in `docs/runs/README.md`.

One record per run id. Do not rewrite the metrics of a past run; a changed
configuration is a new record. Timestamped CSVs stay local, so the record must
stand alone without them.

## V2 D3 retrieval (2026-11-04)

The D1 baseline used for the before column is run `20261104T144856Z` (Hit@5
0.58). After the named filter, decomposition and the gold-label audit, run
`20261104T154503Z` measures:

| Slice | Hit@5 before | Hit@5 after | Recall@5 before | Recall@5 after |
|---|---|---|---|---|
| overall | 0.58 | 0.76 | 0.48 | 0.66 |
| named_reference | 0.38 | 1.00 | 0.38 | 1.00 |
| simple | 0.65 | 0.74 | 0.55 | 0.62 |
| multi_part | 0.50 | 0.62 | 0.31 | 0.50 |

Stage diagnostics for the same run: dense 0.77, sparse 0.68, pool 0.81, rerank
lift 0.86, loss 0.14. The reranker was not the bottleneck; pool recall was. The
named filter is the largest single change: explicit book/chapter references are
now applied to both legs, with an unfiltered fallback when the filtered pool
would be empty. Multi-part questions are split into at most three sub-queries,
the original question is kept as an extra leg, and the merged pool is reranked.

The before and after columns use different gold hashes. The audit corrected
wrong or incomplete evidence ids for `q08`, `q13`, `q16` and `m08`; `q03` was
reverted to a genuine miss after review. The named slice isolates the retrieval
change (0.38 to 1.00); the simple gain also includes relabelling, so do not read
it as a pure retrieval delta.

`multi_part` pool recall is 0.90, not 1.0. `m06` misses one of its three valid
ids (`b2-c16-0026`, the Basilisk entry) and `m07` misses `b3-c10-0020`; both are
outside the current candidates. That is a query-expansion or embedder problem,
not a fusion bug. The new numbers are in
`docs/runs/2026-11-04-v2-d3-retrieval.md`.

## Residual retrieval experiments

After the D3 baseline, four variants were measured and rejected:

| Variant | Hit@5 | Recall@5 | MRR | Note |
|---|---|---|---|---|
| baseline 0.6B, pool 50 | 0.76 | 0.66 | 0.50 | kept |
| 4B embedder, pool 50 | 0.76 | 0.65 | 0.49 | dense 0.83, rerank lift 0.84 |
| 0.6B, pool 100 | 0.68 | 0.57 | 0.48 | reranker dilution |
| 0.6B, pool 30 | 0.74 | 0.63 | 0.52 | named 0.88 |
| contextual index, 0.6B | 0.72 | 0.61 | 0.50 | sparse 0.73, dense 0.76 |

No variant improves overall Hit@5. The retained baseline is 0.6B, pool 50,
text-only. Details: `docs/runs/2026-11-05-v2-d3-retrieval-ablations.md` and
`docs/runs/2026-11-05-v2-d3-contextual-retrieval.md`.

## V1 mini-eval (historical)

Measured 2026-11-04 on the V1 20+5 gold set, with rerank on (default) and off.
These numbers are kept for history and are not comparable with the V2 gold set.

| Metric | Rerank on | Rerank off |
|---|---|---|
| Hit@5 | 0.70 | 0.60 |
| Recall@5 | 0.53 | 0.42 |
| MRR | 0.45 | 0.45 |
| Abstention on unanswerable | 1.00 (5/5) | 1.00 (5/5) |
| Judge correct | 9 / 10 | 7 / 10 |
| Judge partial | 0 / 10 | 1 / 10 |
| Judge wrong | 0 / 10 | 2 / 10 |
| Grounded | 9 / 10 | 8 / 10 |

## Configuration

| Role | Model |
|---|---|
| Generator | `qwen/qwen3-30b-a3b-instruct-2507` |
| Judge | `deepseek/deepseek-v4.1-flash-1017` |
| Reranker | `amazon.rerank-v1:0` (Bedrock), pool 50 |
| Embedder | `OWL_EMBEDDER_PROVIDER`: `local` (Ollama) or `bedrock` (Titan) |
| Chunking | size 500, overlap 75, min size 200 |
| Retrieval | hybrid (dense + BM25, RRF), `k = 5`, `rrf_k = 60`, candidates 50 |

## Judge

Pinned to `deepseek/deepseek-v4.1-flash-1017`, probed live before use
(`uv run python scripts/probe_openrouter.py --model deepseek/deepseek-v4.1-flash-1017`,
generate and stream PASS) and open-weight (MIT). A different family from the Qwen
generator, as AGENTS.md requires. The same model family drafted this harness,
which is a soft self-evaluation: a future run should repeat it with a judge
independent of the authoring agent.

## Faithfulness

Faithfulness is a second judge call with its own prompt. It ignores citations and
asks only whether every factual claim in the answer is supported by the retrieved
excerpts. This is independent of the mechanical citation-presence rule in
`ask()`, which only checks that some retrieved id is cited. Abstained answers are
excluded from the faithfulness denominator and reported separately.

## Notes and limitations

- EM/F1 compare the generated answer with a short reference answer. Inline
  citation markers are stripped first, so `[b1-c06-0001]` does not count as
  answer tokens. A correct but verbose answer still scores low on EM and
  partially on F1, so read them beside the judge buckets rather than alone.
- Judge replies that fail to parse are counted in `judge_parse_failures` and
  `faithful_parse_failures`; they are not silently treated as a wrong answer or
  an unfaithful one.
- The judge grades correctness against the retrieved excerpts, not a gold answer,
  so it partly measures retrieval. Faithfulness is the claim-support check.
- The `near_miss_unanswerable` slice is new in V2 D1. It tests whether a
  topically close question still abstains, not whether the retriever can find a
  plausible-looking chunk.
- Gold ids were each checked against the corpus to confirm the chunk answers the
  question. Questions with more than one valid answer chunk list them all, so
  `Hit@5` is fair rather than generous.
- Retrieval remains the weak stage on the V1 set (Hit@5 0.70 with rerank). The
  expected chunk is in the top-50 pool for 0.75 of answerable items, so a perfect
  reranker could reach 0.75 there. Closing the rest needs a stronger embedder and
  the retrieval work in V2 D3 and D6.
- The eval uses OpenRouter for the generator and judge (hosted models required);
  the embedder comes from `OWL_EMBEDDER_PROVIDER`. `CachedLlm` caches `generate()`
  only; `stream` is passed through.
- Rerank (V1, #6) is wired on by default (`amazon.rerank-v1:0`, pool 50); set
  `OWL_RERANK_PROVIDER=none` for the baseline column.

## D6 retrieval guardrails (#79)

### Sparse tokenizer

Ablation on the 61-item gold set, reranker on, same index:

| Tokenizer | Hit@5 | Recall@5 | MRR |
|---|---:|---:|---:|
| `regex-words` | 0.765 | 0.660 | 0.498 |
| Snowball stemming | 0.745 | 0.640 | 0.504 |
| Stopwords only | 0.706 | 0.591 | 0.467 |

Stemming changed sparse recall but Hit@5 went from 39/51 to 38/51 and recall
fell. That is one item, inside the
0.05 gate band, and MRR rose slightly; the rejection is about paying a
dependency for no measured gain, not about a large regression. The manifest pins
`retrieval.tokenizer = "regex-words"` and `tokenize()` fails loudly on an
unknown value.

### Rerank floor

Top rerank score per gold item, 61 items (51 answerable, 10 unanswerable):

| Slice | min | p10 | median | p90 | max |
|---|---:|---:|---:|---:|---:|
| answerable | 0.003 | 0.059 | 0.477 | 0.887 | 0.991 |
| unanswerable | 0.000 | 0.000 | 0.000 | 0.352 | 0.352 |

| Floor | Floor-driven false abstention (answerable) | Floor-driven abstention (unanswerable) |
|---:|---:|---:|
| 0.0 | 0/51 | 0/10 |
| 0.1 | 10/51 | 7/10 |
| 0.4 | 22/51 | 8/10 |

Two of the ten unanswerable items return no chunks at all, so `ask()` abstains
before any score is compared; the table counts floor-driven abstentions only.
The distributions overlap. Catching the remaining eight unanswerable items would
cost 22 of 51 answerable items, so the floor is pinned at `0.0`. The measurement
is `scripts/measure_rerank_floor.py`.

### Novel-entity signal

`eval/harness/novelty.py` flags capitalized answer tokens absent from the corpus
vocabulary. It catches invented names such as Herbrand; it does not catch a real
name used wrongly, a wrong count, or a misattributed object. Sentence-initial
capitals are skipped because they are grammar. Aliases the corpus uses are safe;
inflected forms the corpus lacks, and differently hyphenated names, can false
positive. Reported per run as `novel_entity_n`, `novel_entity_answers`,
`novel_entity_rate` and `novel_entity_tokens`.

### Deadline

`/ask` is bounded by `OWL_ASK_TIMEOUT_S` (default 30 s) and returns a typed 504
with the request id; `/ask/stream` is not bounded.

## Routing comparison

`scripts/compare_routing.py` compares practice/feedback across two models on
`eval/fixtures/practice_feedback.jsonl`. It runs the real graph, checks citations
deterministically, scores with the pinned judge (cached), and prints citations,
topic, grounding, answerability, boundary, band, named error on non-strong
answers, p50 latency, failures, parse failures and an estimated cost per 1k
generations. Caps are 512 output tokens for generation and 2048 for the judge,
because the judge's reasoning tokens otherwise consume the budget. A model list
and fixture can be passed with `--models` and `--fixture`. The script exits
non-zero when no verdict parses, so a broken run cannot look like a result.
