# Run record: #176 persona lesson voice

- Date: 2026-11-09
- Run id: `20261109T162833Z`
- Ticket: #176
- Config: `persona-conformance` (baseline pre-#176 prompt vs persona-first candidate)
- Artifacts: `eval/results/persona-20261109T162833Z.json` (local, gitignored)

## Configuration

| Field | Value |
|---|---|
| Generator | `openrouter/qwen/qwen3-30b-a3b-instruct-2507`, temperature 0.7 |
| Judge | `deepseek/deepseek-v4.1-flash-1017`, temperature 0.0 |
| Embedder | local Ollama `qwen3-embedding:0.6b` |
| Lesson selection | top-k 3, cosine floor 0.58, corpus fallback on |
| Fixture | `eval/persona/fixtures/conformance.jsonl`, 29 scenarios |
| Samples | 3 per scenario per condition |
| Calibration | `eval/persona/fixtures/calibration.jsonl`, 10 cases |
| Corpus gate | `eval/results/20261108T080558Z.csv`, `gate: PASS` |

## Conformance

| Metric | Baseline | Candidate |
|---|---:|---:|
| route accuracy | 1.0000 | 1.0000 |
| topic accuracy | 1.0000 | 1.0000 |
| scope accuracy | 1.0000 | 1.0000 |
| citation retention | 1.0000 | 1.0000 |
| abstention accuracy | 1.0000 | 1.0000 |
| boundary violations | 0 | 0 |
| style violations | 0 | 0 |
| length violations | 8 | 0 |
| persona pass rate | 0.0000 | 0.5200 |
| persona Wilson LB | 0.0000 | 0.3851 |
| mean voice score | 0.7917 | 1.5200 |
| score variance | 0.0833 | 0.1307 |
| judged samples | 48 | 50 |
| judge parse failures | 0 | 0 |
| errors | 0 | 0 |

The baseline is the pre-#176 composition: grounding rules first, then the
reviewed tone suffix. The candidate is the shipped persona-first composition:
identity, register and stance, the teaching shape, the grounding rules, and a
final voice reminder. Both use the same selector, retriever and generator. The
judge never sees the condition.

Both conditions use the same note rendering, with the inline book chunk ids
hidden. The comparison therefore isolates the system-prompt composition and the
voice instructions, not the note format. The baseline already retained its
citations at 1.0000, so the shared rendering does not explain the voice gain.

## Calibration

| Case | Human | Judge | Delta |
|---|---:|---:|---:|
| `cal-01` | 2 | 2 | 0 |
| `cal-02` | 2 | 2 | 0 |
| `cal-03` | 2 | 2 | 0 |
| `cal-04` | 1 | 1 | 0 |
| `cal-05` | 1 | 1 | 0 |
| `cal-06` | 0 | 0 | 0 |
| `cal-07` | 0 | 0 | 0 |
| `cal-08` | 0 | 0 | 0 |
| `cal-09` | 0 | 1 | 1 |
| `cal-10` | 0 | 0 | 0 |

Exact agreement 0.9000, adjacent agreement 1.0000, MAE 0.1000, no parse
failures. The labels are AI-proposed from the rubric and still need owner
adoption in review, the same pattern the exam calibration fixture uses.

## Reading

- Voice moved: the persona pass rate rose from 0.0000 to 0.5200, and the Wilson
  lower bound rose from 0.0000 to 0.3851. The mean voice score rose from 0.7917
  to 1.5200. The candidate is above the noise band on the gate.
- Grounding held: citation retention stayed at 1.0000. The candidate cites the
  material id in every in-pack answer; stripping the inline book chunk ids from
  the rendered note removed the main cause of uncited abstentions.
- Abstention is 1.0000 in both conditions. The fixture accepts the in-world
  line for a mixed question when the model cannot cite both spaces, so the
  dual-citation contract is measured without counting a correct refusal as a
  miss.
- Boundaries and style are clean: zero exam disclosures, private-knowledge
  claims, out-of-role advice, slang, emojis or time pressure. The candidate also
  has zero length violations against eight for the baseline.
- Variance is 0.1307 for the candidate against 0.0833 for the baseline. The
  voice is not deterministic across samples, which is why the gate uses the
  Wilson lower bound rather than a single pass rate.
- The measured corpus path did not move: the pinned `--check` run is `gate:
  PASS`. The corpus path is persona-off; the lesson prompt is behind
  `OWL_LESSON_MODE` and `OWL_PERSONA`.
- The candidate still produces third-person openings in some samples. The
  fixture records that as a 1, not a 0; a future prompt change can be compared
  on the same fixture.

## Reproduce

```
uv run python scripts/run_persona_eval.py
uv run python scripts/run_eval.py --check
```

## Raw summary

```text
run_id: 20261109T162833Z
persona conformance eval

scenarios=29 samples_per_scenario=3
generator=openrouter/qwen/qwen3-30b-a3b-instruct-2507
judge=deepseek/deepseek-v4.1-flash-1017 temperature=0.0
fixture_sha=c0687f80a762

| Metric | Baseline | Candidate |
|---|---:|---:|
| route accuracy | 1.0000 | 1.0000 |
| topic accuracy | 1.0000 | 1.0000 |
| scope accuracy | 1.0000 | 1.0000 |
| citation retention | 1.0000 | 1.0000 |
| abstention accuracy | 1.0000 | 1.0000 |
| boundary violations | 0 | 0 |
| style violations | 0 | 0 |
| length violations | 8 | 0 |
| persona pass rate | 0.0000 | 0.5200 |
| persona Wilson LB | 0.0000 | 0.3851 |
| mean voice score | 0.7917 | 1.5200 |
| score variance | 0.0833 | 0.1307 |
| judged samples | 48 | 50 |
| judge parse failures | 0 | 0 |
| errors | 0 | 0 |

Calibration:
  n=10 exact=0.9000 adjacent=1.0000 MAE=0.1000 parse_failures=0
  cal-01: human=2 judge=2 delta=0
  cal-02: human=2 judge=2 delta=0
  cal-03: human=2 judge=2 delta=0
  cal-04: human=1 judge=1 delta=0
  cal-05: human=1 judge=1 delta=0
  cal-06: human=0 judge=0 delta=0
  cal-07: human=0 judge=0 delta=0
  cal-08: human=0 judge=0 delta=0
  cal-09: human=0 judge=1 delta=1
  cal-10: human=0 judge=0 delta=0

gate: PASS
wrote /Users/tc/Documents/Github/owl-online/eval/results/persona-20261109T162833Z.json
```
