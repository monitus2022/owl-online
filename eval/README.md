# Mini-eval

A deliberately small eval for V1 (ticket #51): retrieval scored on chunk ids,
and a judged sample of generated answers. The full harness as a CI gate is V2
(#9-#12).

## Layout

| Path | Contents |
|---|---|
| `eval/harness/gold.py` | `GoldItem`, `load_gold` |
| `eval/harness/retrieval.py` | Hit@k, Recall@k, MRR |
| `eval/harness/abstention.py` | refusal counts and rate |
| `eval/harness/generation.py` | EM, F1, judge buckets, aggregates |
| `eval/harness/judging.py` | judge prompts, reply parsers, sample selection |
| `eval/harness/cache.py` | `CachedLlm` |
| `eval/results.py` | result CSV, baseline copy and diff |
| `eval/thresholds.toml` | gate bands per metric, with slice overrides |
| `eval/test_harness.py` | harness tests, no network |
| `eval/test_results.py` | result CSV tests, no network |
| `eval/runner.py` | one run: compose, score, write the CSV |
| `eval/report.py` | result rows and printed summary |
| `eval/check.py` | baseline diff and gate for `--check` |
| `eval/test_check.py` | gate tests, no network |
| `eval/test_report.py` | row and rendering tests, no network |
| `scripts/run_eval.py` | CLI params and dispatch |

`eval/harness/__init__.py` re-exports the public names, so callers keep
importing from `eval.harness`.

```text
gold/questions.jsonl (60 items)
        |
        +-- retrieval pass --> Hit@k, Recall@k, MRR        (50 answerable)
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

## Gold set

`gold/questions.jsonl`: 50 answerable and 10 unanswerable items. Each item is an
original question plus the expected chunk ids and a short reference answer. No
corpus text is stored; ids and short answers only.

| Slice | Items | Purpose |
|---|---|---|
| `simple` | 34 | single-fact questions across all seven books |
| `named_reference` | 8 | the question names a book and chapter |
| `multi_part` | 8 | the question asks two things, and both must be retrieved |
| `near_miss_unanswerable` | 5 | topically close to the corpus but not answerable from it |
| `off_topic` | 5 | clearly outside the corpus |

Unanswerable items carry a `reason` instead of evidence ids. Answerable items
carry locatable evidence ids, checked against the corpus before they were added.

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
drops further. It also refuses to diff two runs whose recorded manifest values
differ (models, chunking, retrieval settings or judged sample), because those
deltas would not be comparable. The CI workflow that runs this on pull requests
is still open in #77.

Bands are absolute. Overall metrics use `[bands]`; named slices use
`[slice_bands]` because one gold item is 0.125 on the 8-item retrieval slices and
0.20 on the 5-item generation slices. Count metrics (`retrieval_n`,
`generation_n`, `abstention_n`) have a zero band, so a gold-set or sample change
fails instead of hiding inside an average.

Generation and judge outputs are cached under `eval/.cache/` by `(model, input)`,
so reruns are cheap and deterministic. `--k` controls the retrieval cutoff and
`--sample` controls the judged sample. The sample is taken round-robin across
the answerable slices, so the default of 15 covers simple, named and multi-part.

## Result files

| Path | Committed | Purpose |
|---|---|---|
| `eval/results/<timestamp>.csv` | no | one run, gitignored |
| `eval/results/baseline.csv` | yes | the pinned comparison point |

The V2 baseline is written by the first `--write-baseline` run against the pinned
manifest. This file does not invent a baseline; rerun the command after a
deliberate configuration change and review the diff.

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