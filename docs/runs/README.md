# Run records

One Markdown record per eval run. The CSV is the data; the record is the readable
history of how the RAG strategy moved over the sprint.

## Rules

- Every finished run of `scripts/run_eval.py` gets a record. A run without a
  record does not count as done.
- `run_eval.py --check` produces no run id and needs no record. It gates a run
  that already has one.
- Write it after the run finishes, before closing the ticket.
- One record per run id. Do not rewrite the metrics of a past run; a changed
  configuration is a new record.
- An experiment record may cover several run ids when it compares
  configurations; list every id in the table and link the same record.
- Record files are committed. Timestamped CSVs stay local and gitignored, so the
  record must stand on its own without the CSV.
- Add a row to the Runs table below in the same commit.
- Repo docs style applies: headings, lists, tables and code only. No bold, no
  italic.

## Naming

```
docs/runs/YYYY-MM-DD-<ticket>-<slug>.md
```

Example: `docs/runs/2026-11-04-v2-d1-baseline.md`. When the same ticket produces
another baseline, keep the old record and add a suffix: `-r2.md`, `-r3.md`, and
so on.

## Runs

| Date | Ticket | Run id | Config | Overall Hit@5 | Overall F1 | Faithful | Record |
|---|---|---|---|---|---|---|---|
| 2026-11-04 | #76 (V2 D1) | `20261104T131118Z` | `pinned` | 0.58 | 0.22 | 11/15 | [V2 D1 baseline](2026-11-04-v2-d1-baseline.md) |
| 2026-11-04 | #76 (V2 D1) | `20261104T134619Z` | `pinned` | 0.58 | 0.26 | 11/15 | [V2 D1 baseline r2](2026-11-04-v2-d1-baseline-r2.md) |
| 2026-11-04 | #76 (V2 D1) | `20261104T143343Z` | `pinned` | 0.58 | 0.30 | 11/15 | [V2 D1 baseline r3](2026-11-04-v2-d1-baseline-r3.md) |
| 2026-11-04 | #76 (V2 D1) | `20261104T144856Z` | `pinned` | 0.58 | 0.28 | 11/15 | [V2 D1 baseline r4](2026-11-04-v2-d1-baseline-r4.md) |
| 2026-11-04 | #78 (V2 D3) | `20261104T152008Z` | `pinned` | 0.58 | 0.28 | 11/15 | [V2 D3 diagnostics](2026-11-04-v2-d3-retrieval-diagnostics.md) |
| 2026-11-04 | #78 (V2 D3) | `20261104T220147Z` | `pinned` | 0.76 | 0.32 | 12/15 | [V2 D3 baseline](2026-11-04-v2-d3-retrieval.md) |
| 2026-11-05 | #78 (V2 D3) | `20261104T185945Z` | `context` | 0.72 | 0.31 | 12/15 | [Contextual retrieval, rejected](2026-11-05-v2-d3-contextual-retrieval.md) |
| 2026-11-05 | #78 (V2 D3) | `20261104T214110Z` | `4b` | 0.76 | 0.32 | 12/15 | [Retrieval ablations](2026-11-05-v2-d3-retrieval-ablations.md) |
| 2026-11-05 | #78 (V2 D3) | `20261104T214334Z` | `pool-100` | 0.68 | 0.32 | 12/15 | [Retrieval ablations](2026-11-05-v2-d3-retrieval-ablations.md) |
| 2026-11-05 | #78 (V2 D3) | `20261104T214458Z` | `pool-30` | 0.74 | 0.32 | 12/15 | [Retrieval ablations](2026-11-05-v2-d3-retrieval-ablations.md) |
| 2026-11-05 | #80 (V2 D4) | `20261105T093948Z` | `pinned` | 0.76 | 0.32 | 12/15 | [V2 D4 regression check](2026-11-05-v2-d4-agent-foundation.md) |
| 2026-11-05 | #81 (V2 D5) | `20261105T145942Z` | `pinned` | 0.76 | 0.32 | 12/15 | [V2 D5 verify and retry](2026-11-05-v2-d5-verify.md) |
| 2026-11-05 | #81 (V2 D5) | `20261105T150931Z` | `pinned` | 0.76 | 0.32 | 12/15 | [V2 D5 verify and retry r2](2026-11-05-v2-d5-verify-r2.md) |
| 2026-11-05 | #79 (V2 D6) | `20261105T154916Z` | `pinned` | 0.76 | 0.32 | 12/15 | [V2 D6 retrieval guardrails](2026-11-05-v2-d6-retrieval-guardrails.md) |
| 2026-11-05 | #79 (V2 D6) | `20261105T154940Z` | `pinned` | 0.76 | 0.32 | 12/15 | [V2 D6 retrieval guardrails](2026-11-05-v2-d6-retrieval-guardrails.md) |
| 2026-11-06 | #79 (V2 D6) | `20261105T160001Z` | `pinned` | 0.76 | 0.30 | 12/14 | [V2 D6 r2](2026-11-06-v2-d6-retrieval-guardrails-r2.md) |
| 2026-11-06 | #79 (V2 D6) | `20261105T160032Z` | `pinned` | 0.76 | 0.30 | 12/14 | [V2 D6 r2](2026-11-06-v2-d6-retrieval-guardrails-r2.md) |
| 2026-11-06 | #82 (V2 D7) | `20261105T171800Z` | `pinned` | 0.76 | 0.30 | 13/14 | [V2 D7 tracing and injection](2026-11-06-v2-d7-observability.md) |
| 2026-11-06 | #82 routing | `comparison` | `routing` | n/a | n/a | n/a | [Model routing comparison](2026-11-06-v2-routing-comparison.md) |
| 2026-11-06 | #96 | `20261105T204517Z` | `pinned` (quota 2) | 0.78 | 0.29 | 14/14 | [Sub-query quota experiment](2026-11-06-v2-subquery-quota.md) |
| 2026-11-06 | #96 | `20261106T060233Z` | `pinned` | 0.76 | 0.30 | 13/14 | [Quota follow-up gate](2026-11-06-v2-quota-followup.md) |
| 2026-11-06 | #96 | `20261106T060737Z` | `pinned` | 0.76 | 0.30 | 13/14 | [Quota-aware baseline](2026-11-06-v2-quota-baseline.md) |
| 2026-11-06 | #96 | `20261106T060813Z` | `pinned` | 0.76 | 0.30 | 13/14 | [Quota-aware baseline gate](2026-11-06-v2-quota-baseline-gate.md) |
| 2026-11-06 | #96 | `20261106T060914Z` | `pinned` (quota 2) | 0.78 | 0.29 | 14/14 | [Sub-query quota r2](2026-11-06-v2-subquery-quota-r2.md) |
| 2026-11-06 | #96 | `20261106T100459Z` | `aggregation` | n/a | n/a | n/a | [Aggregation fixture baseline](2026-11-06-v2-aggregation-baseline.md) |
| 2026-11-06 | #96 | `20261106T104138Z` | `aggregation` (router) | n/a | n/a | n/a | [Router on the aggregation fixture](2026-11-06-v2-router-fixture.md) |
| 2026-11-06 | #96 | `20261106T105801Z` | `aggregation` (single-hop k=7) | n/a | n/a | n/a | [Single-hop k=7 comparison](2026-11-06-v2-multibook-baseline-k7.md) |
| 2026-11-06 | #96 | `20261106T105819Z` | `aggregation` (routed per-book k=7) | n/a | n/a | n/a | [Per-book retrieval prototype](2026-11-06-v2-multibook-retrieval.md) |
| 2026-11-06 | #106 | `20261106T121322Z` | `aggregation_holdout` (single-hop k=7) | n/a | n/a | n/a | [Held-out single-hop k=7](2026-11-06-v2-holdout-single-k7.md) |
| 2026-11-06 | #106 | `20261106T121335Z` | `aggregation_holdout` (routed per-book k=7) | n/a | n/a | n/a | [Held-out routed k=7](2026-11-06-v2-holdout-routed-k7.md) |
| 2026-11-06 | #105 | `20261106T110000Z` | `aggregation_holdout` (multi-book generation, k=15 / top-k 7) | n/a | n/a | 11/15 | [Multi-book generation](2026-11-06-105-multibook-generation.md) |
| 2026-11-07 | #118 | `20261106T203024Z` | `pinned` | 0.76 | 0.30 | 13/14 | [Lore answers gate](2026-11-07-118-lore-answers.md) |
| 2026-11-07 | #113 | `20261106T214850Z` | `pinned` | 0.76 | 0.31 | 13/15 | [Ingest re-baseline](2026-11-07-113-ingest-rebaseline.md) |
| 2026-11-07 | #113 | `20261106T214917Z` | `pinned` | 0.76 | 0.31 | 13/15 | [Ingest gate](2026-11-07-113-ingest-gate.md) |
| 2026-11-07 | #105 | `20261106T224550Z` | `aggregation` (retrieval diagnostic) | n/a | n/a | n/a | [Multi-book diagnostic](2026-11-07-105-multibook-diagnostic.md) |

## Template

Copy this into the new file and replace every value. Keep the raw summary block
verbatim: it is the `render_run()` output, including its `wrote` lines, but not
the final `next: write a run record` reminder.

````markdown
# Run record: <ticket> <short name>

- Date: <YYYY-MM-DD>
- Run id: `<run_id from the CSV filename>`
- Ticket: #<n> (V2 D<n>)
- Config: `<config>` (<reranker on or off>)
- Artifacts: `eval/results/baseline.csv` (committed or unchanged), `eval/results/<run_id>.csv` (local, gitignored)

## Configuration

| Field | Value |
|---|---|
| Generator | `<model slug>` |
| Judge | `<model slug>` |
| Reranker | `<model>` or none, pool <n> |
| Embedder | `<provider>` / `<model>`, <n> dims |
| Chunking | size <n>, overlap <n>, min size <n> |
| Retrieval | hybrid (dense + BM25, RRF), `k = <n>`, `rrf_k = <n>`, candidates <n> |
| Sub-query quota | <n> per retrieval leg, or 0 for global fusion |
| Gold set | <n> items: <n> answerable, <n> unanswerable |
| Judged sample | <n>, round-robin across the answerable slices |

## Retrieval

| Slice | n | Hit@5 | Recall@5 | MRR |
|---|---|---|---|---|
| overall | | | | |
| simple | | | | |
| multi_part | | | | |
| named_reference | | | | |

## Abstention

| Slice | Refused | Rate |
|---|---|---|
| overall | | |
| near_miss_unanswerable | | |
| off_topic | | |

## Generation (judged sample)

| Slice | n | EM | F1 | Judge correct | Faithful |
|---|---|---|---|---|---|
| overall | | | | | |
| simple | | | | | |
| named_reference | | | | | |
| multi_part | | | | | |

Judge buckets: <n> correct, <n> partial, <n> wrong. Grounded <n>/<n>. <n> answers
in the sample abstained.

## Reading

- <What moved, by slice, and what did not.>
- <What this changes for the next ticket.>
- <Anything that makes the numbers unsafe to compare with a previous run.>

## Reproduce

```
uv run python scripts/run_eval.py
uv run python scripts/run_eval.py --check
```

Pin with `--write-baseline` only when replacing the baseline. A check immediately
after pinning compares the baseline to its own copied run and is refused.

## Raw summary

```text
<paste the summary printed at the end of the run>
```
````
