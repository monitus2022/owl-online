# Run record: #97 persona eval wiring

- Date: 2026-11-08
- Run ids: `20261108T080558Z` (persona off, reproduction) and `20261108T080720Z`
  (persona on)
- Ticket: #97 (V2)
- Config: `pinned` and `pinned-persona` (reranker on; identical retrieval stack)
- Artifacts: `eval/results/baseline.csv` (pinned to `20261106T214850Z`),
  both run CSVs local and gitignored

## Configuration

Both runs use the pinned setup (generator `qwen/qwen3-30b-a3b-instruct-2507`,
judge `deepseek/deepseek-v4.1-flash-1017`, reranker `amazon.rerank-v1:0` pool
50, local `qwen3-embedding:0.6b`, k 5, quota 0, sample 15, gold hash
`fe1d82f5c1c8`, index text hash `aca4c57462d449f5`). The persona run passes
`--persona`: the shipped `PERSONA.answer_suffix()` and the runtime lore store
loaded from `data/lore` (the promoted 15-entry pack) into the same `ask()`
the product calls. This is the first measurement of the voice layer that
previously existed only behind the API flag and outside the harness.

## Retrieval

Identical in both runs (the persona layer cannot move it): overall Hit@5 0.76,
Recall@5 0.65, MRR 0.51; simple 0.74; multi_part 0.67; named_reference 1.00.

## Abstention (unanswerable side)

Identical in both runs: 10/10 refused, near_miss 5/5, off_topic 5/5.

## Generation (judged sample, persona on)

| Slice | n | Answered | Abstained | F1 | Judge correct | Faithful |
|---|---:|---:|---:|---:|---:|---:|
| overall | 15 | 14 | 1 | 0.29 | 12, 2 partial, 0 wrong | 12/14 (0.86) |
| simple | 5 | 5 | 0 | 0.27 | 5 correct | 5/5 (1.00) |
| named_reference | 5 | 5 | 0 | 0.25 | 5 correct | 5/5 (1.00) |
| multi_part | 5 | 4 | 1 | 0.34 | 2 correct, 2 partial | 2/4 (0.50) |

Persona-off reproduction (run `20261108T080558Z`): the off run reproduces the
pinned baseline exactly; `--check` reports 144 metric rows with every delta
`+0.0000`, `gate: PASS`. The harness plumbing changes nothing when the flag
is off.

## Reading

- Off-to-on movement, by row: one multi_part item that previously answered
  now abstains (in-world refusal, the conservative direction); of the
  remaining four, faithfulness and judge verdicts are 2+2 either way - the
  multi_part slice was the weakest slice in the baseline too (3/5 faithful).
- Faithfulness rate moves 0.867 -> 0.857 and judge correctness moves with it:
  a single item on n=15, inside the noise band; retrieval and unanswerable
  abstention are byte-identical, citation parse failures stay 0.
- F1 dips ~0.02 across slices from answer wording (persona register changes
  surface text; EM/F1 are string metrics and are reported, not gated, for
  this comparison).
- Decision: the persona path is shippable. #97's "voice layer tested for no
  regression" criterion is now met by measurement, not by absence of
  testing. Enabling `OWL_PERSONA` on the host additionally requires the
  runtime pack on the host at `OWL_LORE_PATH` and a smoke pass of the
  preset strings from #162.

## Reproduce

```
uv run python scripts/run_eval.py
uv run python scripts/run_eval.py --check
uv run python scripts/run_eval.py --persona
```

## Raw summary (persona on)

```text
gold: 61 items (51 answerable, 10 unanswerable)
config: pinned-persona
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
  overall                n=15  answered=14  abstained=1   EM=0.00 F1=0.29 faithful=12/14 (0.86) judge correct=12 partial=2 wrong=0 grounded=13 judge_parse=0 faithful_parse=0
  multi_part             n=5   answered=4   abstained=1   EM=0.00 F1=0.34 faithful=2/4 (0.50) judge correct=2 partial=2 wrong=0 grounded=3 judge_parse=0 faithful_parse=0
  named_reference        n=5   answered=5   abstained=0   EM=0.00 F1=0.25 faithful=5/5 (1.00) judge correct=5 partial=0 wrong=0 grounded=5 judge_parse=0 faithful_parse=0
  simple                 n=5   answered=5   abstained=0   EM=0.00 F1=0.27 faithful=5/5 (1.00) judge correct=5 partial=0 wrong=0 grounded=5 judge_parse=0 faithful_parse=0

novel entities: 0/14 answers (0.00), tokens: none

wrote /Users/tc/Documents/Github/owl-online/eval/results/20261108T080720Z.csv
```
