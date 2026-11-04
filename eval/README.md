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

First measured run, 2026-11-04.

| Metric | Value |
|---|---|
| Hit@5 | 0.60 |
| Recall@5 | 0.42 |
| MRR | 0.45 |
| Abstention on unanswerable | 1.00 (5/5) |
| Judge correct | 7 / 10 |
| Judge partial | 1 / 10 |
| Judge wrong | 2 / 10 |
| Grounded | 8 / 10 |

Configuration:

| Role | Model |
|---|---|
| Generator | `qwen/qwen3-30b-a3b-instruct-2507` |
| Judge | `deepseek/deepseek-v4.1-flash-1017` |
| Retrieval | hybrid (dense + BM25, RRF), `k = 5` |

## Notes and limitations

- The gold set is small and hand-built. Several questions have more than one
  valid answer chunk; those are listed, so `Hit@5` is a fair but not generous
  estimate.
- The judge is a different family from the generator, as AGENTS.md requires. It
  is the same model family that drafted this harness, which is a soft
  self-evaluation: a future run should repeat this with a judge independent of
  the authoring agent.
- Abstention here leans on the uncited-answer path as much as the retrieval-score
  floor; the retrieval floor alone is a weak signal and is V2 work (#23).
- Retrieval is the weak stage (Hit@5 0.60). Rerank (#6) and a stronger embedder
  are the intended levers.
