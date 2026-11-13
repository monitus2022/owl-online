# Run record: #251 lesson grounding first slice

- Date: 2026-11-13
- Run id: `20261113T082310Z` (measured), `20261113T082614Z` (baseline re-pin)
- Ticket: #251 (claim-level citation binding for chat and lesson)
- Config: `rag-eval` (persona on, lesson mode on, lesson fallback on, temperature 0)
- Baseline: `20261112T135058Z` (#248), with #249 merged
- Fixture: `eval/rag/fixtures/lesson.jsonl`, SHA-256 `de4e373b1acf`
- Artifacts: `eval/results/rag-20261113T082310Z.json` (local, gitignored)

## Configuration

| Field | Value |
|---|---|
| Generator | `openrouter/qwen/qwen3-30b-a3b-instruct-2507`, temperature 0.0 |
| Judge | `deepseek/deepseek-v4.1-flash-1017`, temperature 0.0 |
| Embedder | local `qwen3-embedding:0.6b` |
| Lesson fixture | `eval/rag/fixtures/lesson.jsonl`, SHA-256 `de4e373b1acf` |
| Multi-turn fixture | `eval/rag/fixtures/multiturn.jsonl`, SHA-256 `1a86ba5c554d` |
| Judged lesson sample | 30 |
| Expansion budget | `max(lesson_top_k, 5)`, round-robin across concepts |
| Paragraph gate | retry once, then serve the answerable draft |

The shipped slice has five parts:

- The in-pack, mixed and off-pack prompts state the evidence rule: every
  paragraph that makes a factual claim cites the note or excerpt it comes from,
  and an unsupported example, caution or check is omitted.
- The teaching shape is conditional and asks for under 220 words.
- After selection, the rest of each matched concept's reviewed group is added
  round-robin, up to a five-material budget (the top-k size when larger).
- `paragraphs_cited` checks the grounded answer. A draft with an uncited
  factual paragraph gets one paragraph-specific retry. A retry that still leaves
  a paragraph uncited but keeps its citation space is served with its citations;
  a retry that refuses or loses a required citation space restores the earlier
  answerable draft.
- The eval reports mean, maximum and at-or-over-limit word counts. The counts
  include citation tokens and are added, not gated.

The fixture also gained `b2-c14-0000` as an alternative expected chunk for
`lesson-dada-13`: that chunk states that Hagrid named the giant three-headed dog
Fluffy. The gold set was incomplete, and the gate requires a new baseline when
the fixture SHA changes. Running `uv run python scripts/build_rag_fixtures.py`
reproduces the committed fixture at SHA `de4e373b1acf`; the generator, not a
hand edit, is the source of truth.

## Before and after

| Metric | #248 baseline | #249 | #251 | Delta vs #249 |
|---|---:|---:|---:|---:|
| Lesson faithfulness | 2/30 (0.0667) | 2/30 | 4/30 (0.1333) | +2 items |
| Lesson citation recall | 0.9231 | 0.9231 | 0.9615 | +0.0385 |
| Lesson scope accuracy | 0.9839 | 0.9839 | 0.9839 | 0.0000 |
| Lesson false refusal | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Lesson selection precision@3 | 0.6405 | 0.6405 | 0.6405 | 0.0000 |
| Lesson selection recall@3 | 0.9660 | 0.9660 | 0.9660 | 0.0000 |
| Lesson citation validity | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| Lesson source hash | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| Lesson off-pack citation recall | 1.0000 | 1.0000 | 1.0000 | 0.0000 |
| Lesson mean words | n/a | n/a | 199 | n/a |
| Lesson max words | n/a | n/a | 291 | n/a |
| Lesson at or over 220 words | n/a | n/a | 11 of 52 | n/a |
| Multi-turn query accuracy | 0.9444 | 1.0000 | 1.0000 | 0.0000 |
| Multi-turn mode accuracy | 0.8611 | 0.8889 | 0.8889 | 0.0000 |
| Multi-turn citation accuracy | 0.5152 | 0.5455 | 0.5758 | +0.0303 |
| Multi-turn false refusal | 0.1515 | 0.0909 | 0.0909 | 0.0000 |
| Multi-turn comparison accuracy | 0.0833 | 0.0833 | 0.1667 | +0.0833 |
| Multi-turn referral accuracy | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Context contamination | 0 | 0 | 0 | 0 |

## Iterations

Every run below is a finished eval run. Runs `080422Z` onward share this
record; `072932Z` has its own record and `073645Z` is covered by this record.
This is the experiment-record exception in `docs/runs/README.md`: the runs
differ only in the lesson prompt or the gold set, and each id has a Runs-table
row.

| Run id | Change | Faithfulness | Citation | Scope | False refusal | Off-pack citation |
|---|---|---:|---:|---:|---:|---:|
| `20261113T072932Z` | hard paragraph gate | 5/30 | 0.9231 | 0.9516 | 0.0385 | 1.0000 |
| `20261113T073645Z` | retry-only paragraph gate | 4/30 | 0.9615 | 0.9839 | 0.0000 | 1.0000 |
| `20261113T080422Z` | round-robin expansion, grounded-answer check | 5/30 | 0.9423 | 0.9677 | 0.0192 | 0.0000 |
| `20261113T081233Z` | best-draft fallback | 5/30 | 0.9423 | 0.9839 | 0.0000 | 0.0000 |
| `20261113T082146Z` | example id removed from mixed/off-pack prompts | 3/30 | 0.9615 | 0.9839 | 0.0000 | 1.0000 |
| `20261113T082310Z` | examples restored, gold-set correction | 4/30 | 0.9615 | 0.9839 | 0.0000 | 1.0000 |
| `20261113T082614Z` | baseline re-pin, same code | 4/30 | 0.9615 | 0.9839 | 0.0000 | 1.0000 |
| `20261113T090915Z` | served-best guard extension, metrics unchanged | 4/30 | 0.9615 | 0.9839 | 0.0000 | 1.0000 |

The last run verifies that extending the served-best guard to a retry that
loses a required citation space does not change the measured metrics. It is
metric-for-metric identical to `20261113T082310Z`.

## Reading

- Faithfulness moved from 2/30 to 4/30. The judge and calibration are
  owner-adopted, so this is not a judge change; the adopted calibration run is
  `20261113T070629Z`, with exact and binary agreement 1.0000, adjacent agreement
  1.0000, refusal checks 2/2 and gate PASS. It is also two items at n=30, which
  is inside noise. The judge evidence set grew from the top-3 materials to the
  expanded group (up to five), so the movement conflates the prompt and
  paragraph rule with more evidence for the judge. It is directional, not a
  statistically distinguishable gain.
- Citation recall rose from 0.9231 to 0.9615, two items at 52. Both are real
  in-pack gains. The #251 off-pack item is 1.0 only because the gold set now
  includes `b2-c14-0000`; without the correction this run's off-pack item would
  score 0.0 and citation recall 0.9423, the level of `080422Z`. The #249 column
  is historical and already had off-pack at 1.0 under the old gold set. Scope
  is unchanged at 0.9839; the one miss is `lesson-charms-07`, which classifies
  as `mixed` because the coverage check leaves a term uncovered and the corpus
  leg then fires. That is #250/#252, not this slice.
- False refusal is 0 and off-pack citation recall is 1.0. The hard-gate variant
  (run `072932Z`) produced two false refusals, so the shipped gate retries and
  then serves. Its scope accuracy of 0.9516 is those two refusals plus the
  pre-existing `lesson-charms-07` miss, not a gate effect.
- The best-draft fallback matters: without it, a paragraph retry that refuses
  replaced an answerable first draft with the abstention line (run `080422Z`,
  `lesson-dada-13`). The retry can no longer replace an answerable draft with
  the abstention line.
- The fallback is a deliberate tradeoff. It serves the earlier answerable draft
  even though that draft failed the paragraph check, and it cannot tell a
  placement refusal from a refusal that judges the notes unsupported. It also
  fires when the retry loses a required citation space, not only on a refusal.
  The fallback rate and the served draft's uncited-paragraph count are traced
  but not aggregated, so the residual is unmeasured. Measuring both is part of
  the next slice.
- Removing the concrete chunk-id example from the mixed and off-pack prompts
  made faithfulness and multi-turn false refusal worse (run `082146Z`: 3/30,
  false refusal 0.1212), so the examples stay.
- Multi-turn citation accuracy moved 0.5455 to 0.5758 and comparison accuracy
  0.0833 to 0.1667. Both are one extra turn; treat them as directional. Query
  accuracy, mode accuracy and false refusal are #249's movement, not #251's.
- Length is reported but not gated: mean 199 words, max 291, 11 of 52 answers at
  220 or more. The hard-gate run used the older `> 220` count (9), so its table
  and this one are not directly comparable on length. The 220-word ask lives in
  the persona preamble, so a deployment with the persona off has no cap. The
  counts include citation tokens.
- The paragraph-citation rate is not an eval metric. The trace carries
  `retry_reason` and `uncited_paragraphs`, but the runner does not aggregate
  attempts or retries. That is a measurement gap for the next slice.
- The remaining faithfulness gap is generation, not retrieval: the evidence is
  present and cited more often, and the model still elaborates. The next slice
  is sentence-level support or a more extractive lesson mode. The chat half is
  untouched. The provenance residual is documented in
  `docs/routing-contracts.md` and remains unmeasured; #251 stays open.
- The persona conformance eval was not re-run. Its judge rubric and fixture
  anchors still describe the unconditional shape (one example, one caution),
  while the lesson prompt now makes both conditional. The conformance scenarios
  draw on reviewed materials that support an example and a caution, so the
  expected shape is still producible, but an answer that correctly omits an
  unsupported section could be scored down. Updating the rubric and anchors and
  re-running `scripts/run_persona_eval.py` is the next persona task; this record
  marks the gap rather than changing a pinned judge without recalibrating it.

## Baseline re-pin

The gold-set correction changes the lesson fixture SHA. `--check` fails on a
fixture mismatch by design, so the baseline was re-pinned with
`uv run python scripts/run_eval.py --rag --write-baseline --force-baseline` at
run `20261113T082614Z`. That run is metric-for-metric identical to
`20261113T082310Z`; only the fixture SHA and the off-pack gold set changed
between those two runs. The re-pin also moves the pinned reference from the #248
numbers onto the #251 state, so it absorbs #249's multi-turn movement as well;
the #248 and #249 records remain the historical comparison.

## Reproduce

```
uv run python scripts/run_rag_eval.py
uv run python scripts/run_eval.py --rag --check
```

## Raw summary

The printed summary below is the run output. The length label was later renamed
from `over-220` to `at-or-over-limit` and the threshold from `> 220` to
`>= LESSON_WORD_LIMIT`; the numbers are unchanged.

```text
run_id: 20261113T082310Z
config: rag-eval
generator: openrouter/qwen/qwen3-30b-a3b-instruct-2507
judge: deepseek/deepseek-v4.1-flash-1017
lesson fixture: de4e373b1acf (judged sample 30)
multi-turn fixture: 1a86ba5c554d

lesson
  total=62 answerable=52 unanswerable=10
  selection precision@3=0.6405 recall@3=0.9660
  scope accuracy=0.9839 citation recall=0.9615
  false refusal=0.0000 abstention accuracy=1.0000
  citation validity=1.0000 source hash=1.0000
  mixed n=1 scope=1.0000 citation=1.0000 false refusal=0.0000
  off-pack n=1 scope=1.0000 citation=1.0000 false refusal=0.0000
  mean words=199 max=291 over-220=11
  judged=30 faithfulness=0.1333

multi-turn
  conversations=17 turns=36
  query accuracy=1.0000 mode accuracy=0.8889
  citation accuracy=0.5758 false refusal=0.0909
  abstention accuracy=1.0000
  referral target accuracy=0.0000 comparison accuracy=0.1667
  context contamination=0

errors: 0
wrote /Users/tc/Documents/Github/owl-online/eval/results/rag-20261113T082310Z.json
```
