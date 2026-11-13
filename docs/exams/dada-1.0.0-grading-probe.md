# Grading probe: DADA 1.0.0

- Date: 2026-11-09
- Bank: `dada` 1.0.0
- Judge: `mistralai/mistral-small-3.2-24b-instruct`
- Provider: `openrouter`
- Temperature: 0.0
- Max tokens: 2000
- Prompt: `dada-bank-judge-v2`
- Items: `dada-short-001`, `dada-short-002`, `dada-short-014`, `dada-short-017`
- Calls: one
- Result: valid JSON, no retry, no needs_review, 32/32, band O
- `judge_output_sha256`: `9961fce489b5a0a037a8aed50bee3b1dfd0462e019013430c473164c7d8a033d`
- Per-question `judge_response_sha256`: all four items share the one output hash
- Calibration: `docs/runs/2026-11-09-191-dada-bank-eval.md`. This is a smoke
  test, not the human-marked calibration set; exact and adjacent agreement,
  mean absolute error and per-criterion agreement are reported there.

The four answers were original probe answers. This record contains no prompts,
golden answers or evidence quotes.
