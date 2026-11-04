# Run records

One Markdown record per eval run. The CSV is the data; the record is the readable
history of how the RAG strategy moved over the sprint.

## Rules

- Every finished run of `scripts/run_eval.py` gets a record. A run without a
  record does not count as done.
- Write it after the run finishes, before closing the ticket.
- One record per run id. Do not rewrite the metrics of a past run; a changed
  configuration is a new record.
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
| 2026-11-04 | #78 (V2 D3) | `20261104T154503Z` | `pinned` | 0.76 | 0.32 | 12/15 | [V2 D3 baseline](2026-11-04-v2-d3-retrieval.md) |
| 2026-11-05 | #78 (V2 D3) | `20261104T185945Z` | `context` | 0.72 | 0.31 | 12/15 | [Contextual retrieval, rejected](2026-11-05-v2-d3-contextual-retrieval.md) |
| 2026-11-05 | #78 (V2 D3) | `20261104T214110Z` | `4b` | 0.76 | 0.32 | 12/15 | [Retrieval ablations](2026-11-05-v2-d3-retrieval-ablations.md) |

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
