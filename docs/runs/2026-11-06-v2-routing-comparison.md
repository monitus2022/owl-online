# Run record: model routing comparison

- Date: 2026-11-06
- Ticket: #82 (routing follow-up)
- Kind: practice/feedback comparison, not the eval gate
- Fixture: `eval/fixtures/practice_feedback.jsonl` (20 items: 8 practice, 12 feedback)
- Judge: `deepseek/deepseek-v4.1-flash-1017`, cached, 2048 output cap
- Generators: `qwen/qwen3-30b-a3b-instruct-2507` and `mistralai/mistral-small-3.2-24b-instruct`, 512 output cap

## Result

| Model | Cites | Topic | Ground | Answer | Bound | Band | Error named | p50 | Fail | Parse | Cost/1k |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Qwen3 30B | 15/20 | 7/7 | 9/13 | 6/7 | 9/13 | 6/12 | 5/5 | 9915 ms | 0 | 7 | $0.11 |
| Mistral Small 3.2 | 13/20 | 8/8 | 9/17 | 7/8 | 13/17 | 7/12 | 2/6 | 5735 ms | 0 | 3 | $0.06 |

## Decision

Do not enable `OWL_ROUTING=intent`. The flag stays off.

Reasons:

- Citations dropped from 15/20 to 13/20.
- Specific error naming dropped from 5/5 to 2/6 on non-strong feedback. Naming the
  mistake is the core of formative feedback.
- Grounding is lower on the parsed answers (9/17 versus 9/13).
- Band agreement is slightly better for Mistral (7/12 versus 6/12), and the
  formative boundary is clearly better (13/17 versus 9/13).
- Mistral is about 45 percent cheaper and 42 percent faster on p50.

The cost and latency gains are real, but the quality loss is in the part users
act on: which mistake to fix.

## Caveat

Both runs have judge parse failures (7 for Qwen, 3 for Mistral) at a 2048-token
cap. The judge spends output on reasoning before the JSON, and some replies are
empty or truncated. The table counts an unparsed reply as a miss, so the absolute
rates are pessimistic for both models. The error-naming gap is large enough that
it survives the caveat, but a rerun with a 4096 cap or a shorter judge prompt
would make the comparison tighter.

## Reproduce

```text
uv run python scripts/compare_routing.py
```

## Raw output

```text
fixture: 20 items; judge: deepseek/deepseek-v4.1-flash-1017; caps: generator=512, judge=2048
model                                            cites topic ground answer bound  band  err  p50ms fail parse  cost/1k
qwen/qwen3-30b-a3b-instruct-2507                  15/20   7/7     9/13    6/7    9/13   6/12   5/5    9915    0     7 $   0.11
mistralai/mistral-small-3.2-24b-instruct          13/20   8/8     9/17    7/8   13/17   7/12   2/6    5735    0     3 $   0.06
```
