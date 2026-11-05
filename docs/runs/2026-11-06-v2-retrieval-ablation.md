# Run record: retrieval selection ablation

- Date: 2026-11-06
- Ticket: #96
- Kind: retrieval-only ablation, not the eval gate
- Gold set: 61 items (51 answerable, 10 unanswerable), `k = 5`
- Variants: baseline, per-sub-query quota 2, top-k 8 for decomposed questions

## Result

| Variant | Slice | n | Hit@5 | Recall@5 | MRR |
|---|---|---:|---:|---:|---:|
| baseline | overall | 51 | 0.765 | 0.660 | 0.498 |
| baseline | multi_part | 9 | 0.667 | 0.519 | 0.407 |
| baseline | named_reference | 8 | 1.000 | 1.000 | 0.775 |
| baseline | simple | 34 | 0.735 | 0.617 | 0.457 |
| quota-2 | overall | 51 | 0.784 | 0.660 | 0.498 |
| quota-2 | multi_part | 9 | 0.778 | 0.519 | 0.407 |
| quota-2 | named_reference | 8 | 1.000 | 1.000 | 0.775 |
| quota-2 | simple | 34 | 0.735 | 0.617 | 0.457 |
| topk-8 | overall | 51 | 0.765 | 0.660 | 0.498 |
| topk-8 | multi_part | 9 | 0.667 | 0.519 | 0.407 |

## Decision

Per-sub-query quota 2 is the candidate. It moves multi-part from 6/9 to 7/9
and overall from 39/51 to 40/51, with no change to simple, named, recall or MRR.
Top-k 8 is a no-op because the reranker already orders the first five the same
way.

This is a one-item gain on a nine-item slice, so it needs the full eval before it
ships. The next step is to implement the quota in `HybridRetriever` behind a
setting, run the full eval and record it.

## Caveat

The quota variant unions the top two fused candidates from each sub-query before
reranking. It reduces the reranker's candidate set, so it also cuts rerank cost.
The reranker rejects `numberOfResults` greater than the source count, which the
script now guards.

## Reproduce

```text
uv run python scripts/retrieval_ablation.py
```
