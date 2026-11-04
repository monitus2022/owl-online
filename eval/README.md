# Mini-eval

A deliberately small eval for V1 (ticket #51): retrieval scored on chunk ids,
and a judged sample of generated answers. The full harness as a CI gate is V2
(#9-#12).

## What it measures

- Retrieval: `Hit@k`, `Recall@k`, `MRR` on the chunk ids that answer each gold question.
- Abstention: how often `ask()` refuses on questions the corpus cannot answer.
- Generation: a sample of answers graded by a second model (correct / partial /
  wrong, and grounded / ungrounded).

## Gold set

`gold/questions.jsonl`: 20 answerable and 5 unanswerable items. Each item is an
original question plus the expected chunk ids. No corpus text is stored; ids only.

## Run

```
uv run python scripts/run_eval.py
```

Generation and judge outputs are cached under `eval/.cache/` by `(model, input)`,
so reruns are cheap and deterministic. `--k` and `--sample` control the retrieval
cutoff and the judged sample size.

## Results

Measured 2026-11-04, with rerank on (default) and off.

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

Configuration:

| Role | Model |
|---|---|
| Generator | `qwen/qwen3-30b-a3b-instruct-2507` |
| Judge | `deepseek/deepseek-v4.1-flash-1017` |
| Reranker | `amazon.rerank-v1:0` (Bedrock), pool 50 |
| Retrieval | hybrid (dense + BM25, RRF), `k = 5` |

## Judge

Pinned to `deepseek/deepseek-v4.1-flash-1017`, probed live before use
(`uv run python scripts/probe_openrouter.py --model deepseek/deepseek-v4.1-flash-1017`,
generate and stream PASS) and open-weight (MIT). A different family from the Qwen
generator, as AGENTS.md requires. The same model family drafted this harness,
which is a soft self-evaluation: a future run should repeat it with a judge
independent of the authoring agent.

## Notes and limitations

- Gold ids were each checked against the corpus to confirm the chunk answers the
  question. The set is small and hand-built; questions with more than one valid
  answer chunk list them all, so `Hit@5` is fair rather than generous.
- Judge correctness is graded against the retrieved excerpts, not a gold answer,
  so it partly measures retrieval and cannot catch an answer that matches wrong
  excerpts. Grounded is close to tautological: `ask()` already abstains when no
  retrieved id is cited.
- Of the 5 unanswerable items, 4 abstained at the retrieval-score floor and 1 via
  the uncited-answer path. The floor alone is a weak signal and is V2 work (#23).
- Retrieval is the weak stage (Hit@5 0.60). Rerank (#6) and a stronger embedder
  are the intended levers.
- The eval uses OpenRouter for the generator and judge (hosted models required);
  the embedder comes from `OWL_EMBEDDER_PROVIDER`. `CachedLlm` caches `generate()`
  only; `stream` is passed through.
- Rerank (V1, #6) is wired on by default (`amazon.rerank-v1:0`, pool 50); set
  `OWL_RERANK_PROVIDER=none` for the baseline column.
- Rerank ceiling: the expected chunk is in the top-50 pool for 0.75 of answerable
  items, so a perfect reranker can reach Hit@5 = 0.75 here. With rerank we measure
  0.70, up from 0.60 without it. Closing the rest of the gap needs a stronger
  embedder, not rerank alone.
