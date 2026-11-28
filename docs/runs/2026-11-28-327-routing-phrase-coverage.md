# #327 routing phrase coverage and residual classifier

Run id: `routing-20261128-327`

Date: 2026-11-28

Ticket: #327, feat(router): evidence-gated residual classifier for setting intent.

Branch: `327/routing-residual`, based on `ff21fec`.

## Question

Does fixing the deterministic phrase coverage close the measured setting-intent
residual, and does an evidence-gated small model on what is left earn its call?

## Configuration

| Item | Value |
|---|---|
| Deterministic baseline | `ff21fec`, before any #327 code |
| Fixtures | `eval/routing/fixtures/paraphrase.jsonl` (77), `must_not.jsonl` (40), `multiturn.jsonl` (22), frozen by SHA-256 in `eval/routing/test_paraphrase.py` |
| Lore pack | `eval/fixtures/lore`, 15 entries, the frozen review copy; aliases authored in #327 |
| Teaching terms | `data/subjects/dada`, the published pack, through the shared `eval/routing/terms.py` helper in both columns |
| Classifier model | `apac.amazon.nova-micro-v1:0` (Bedrock Converse, `ap-northeast-1`), temperature 0, 64 output tokens |
| Prompt | `intent-router-v4`, 5680 characters for `dada` |
| Timeout | 1.5 s read timeout, `max_attempts=0`, one long-lived classifier loop |
| Mode | `on` for the applied column; `shadow` changes no route |
| Replay | `resolve_followup` plus the `remember_node` entity update, `requested_mode=lesson` |

The model probe found no direct on-demand throughput for `amazon.nova-micro-v1:0`
in `ap-northeast-1`; the `apac.` inference profile is required. It also found
that Nova Micro rejects `outputConfig` JSON-schema output, so the classifier uses
prompt-only JSON with strict parsing. Five plain Converse calls took 310-440 ms,
with a 440 ms maximum; that is not enough calls for a p95, and the run below
reports its own p95 over 15 calls.

## Results

| Slice | Deterministic before | Deterministic after | Classifier `on` |
|---|---|---|---|
| `paraphrase` contract | 32/77 | 69/77 | 72/77 |
| `paraphrase` entry | 27/63 | 56/63 | 59/63 |
| `paraphrase` no-fact stretched | 5/6 | 5/6 | 5/6 |
| `must_not` false meta | 1/40 | 0/40 | 0/40 |
| `must_not` policy leak | 1/40 | 1/40 | 1/40 (deterministic; not a residual) |
| `multiturn` contract | 8/22 | 10/22 | 17/22 |
| `multiturn` entry | 4/14 | 5/14 | 10/14 |
| `multiturn` fragment leak | 16/22 | 16/22 | 14/22 |

Holdout only, deterministic after #327 vs classifier `on`:

| Holdout slice | Deterministic | Classifier `on` |
|---|---|---|
| `paraphrase` contract | 21/23 | 22/23 |
| `paraphrase` entry | 18/19 | 19/19 |
| `must_not` false meta | 0/10 | 0/10 |
| `multiturn` contract | 3/7 | 4/7 |
| `multiturn` entry | 2/5 | 3/5 |

One-field comparison on `multiturn`, same pack terms (the student's last turn
blanked):

| Input | Contract | Entry | Fragment leak |
|---|---|---|---|
| Standalone question only | 15/22 | 9/14 | 14/22 |
| Plus the previous student turn | 17/22 | 10/14 | 14/22 |

Classifier acceptance at the zero-false-meta operating point:

| Slice | Used | First choice | Second choice | Rejected |
|---|---:|---:|---:|---:|
| All three, `on` | 15 | 10 | 0 | 5 |
| Holdout, `on` | 6 | 2 | 0 | 4 |
| One-field `multiturn` | 15 | 7 | 1 | 7 |

Cost and latency:

| Measure | Value |
|---|---|
| Calls | 15 of 139 turns |
| p50 | 344-369 ms across runs |
| p95 | 438-498 ms over 15 calls |
| Wall time | about 6-7 s |
| Input | about 21k tokens over 15 calls (5680 characters each) |

## Reading notes

- The deterministic repair accounts for most of the paraphrase move: 32/77 to
  69/77. The classifier adds three contract and three entry points, because the
  real teaching gate routes four typo rows to `lesson` and the classifier only
  runs on `abstain`. The earlier 75/77 in review used a nine-term teaching stub
  and was not comparable; this record uses the published pack in both columns.
- `multiturn` is the classifier's case: 10/22 to 17/22 contract and 5/14 to
  10/14 entry. The two-field input is worth two contract and one entry point
  over the one-field prompt, and its acceptance count moves from 7 first choices
  to 10.
- The fragment-leak rate is 16/22 deterministic and 14/22 in both classifier
  columns. The two-field input improves the follow-up contract, not the leak
  metric; the ticket's Done-when wording claims the leak improves, and that
  claim is not met.
- The holdout gain is smaller: one paraphrase contract item and one multiturn
  conversation, on 7 held-out conversations. It is directionally positive, not a
  precise estimate.
- The classifier is used on 15 of 139 turns and accepts 10 first choices with
  zero false meta; five candidates fail the evidence gate. The second choice never wins on the
  two-field run; it is accepted once on the one-field run, so the second-choice
  path is implemented and lightly exercised.
- `must_not` false meta is 0 at the router contract level. The generate path is
  now guarded too: `lore.select` rejects a question that names Hogwarts, the
  books or a book character before the cue is considered, so "Who was headmaster
  before Snape?" and "What departments does Hogwarts have?" cannot inject the
  Ashcombe body into a book prompt. The guard is `lore.BOOK_CONTEXT`, imported
  by the router too, so the two layers cannot drift; tests cover those rows and
  the `must_not` school-of-witchcraft row.
- The remaining four `lore | lesson` paraphrase rows are typo or idiom turns the
  teaching gate still calls `lesson`. The ticket's decision rule also puts
  "lesson with no evidence" in the residual; this implementation only
  reclassifies `abstain`. That narrowing is a recorded deviation, not a silent
  one.
- `Do you have a library` abstains. It is not in the frozen slices and it is not
  answered or clarified. The in-world abstain is preferable to a clarify whose
  script asks about the subject versus the exam, but the Done-when clause is not
  met for that case.
- The six no-fact rows are deliberate stretches: five of six still select an
  entry. They are reported so the stretch stays visible rather than hidden in
  recall.
- The least constrained part of the gate is the weak-signal branch: when the
  selector has no entry or only a single-token hit, any existing, subject-matched
  entry the model names is accepted if the question points at the setting. The
  0/10 holdout on `must_not` supports it, but it is the place to watch in the
  shadow week.
- The classifier call is outside the chat limiter and cost accounting; the
  input estimate above is operator-side. Wiring it into `/v1/metrics` is a
  follow-up, not part of this ticket.
- The prompt is about 5680 characters, roughly 1400 tokens, above the ticket's
  600-800 token target. The measured p50 stays inside the latency budget; the
  overrun is recorded rather than hidden.
- A setting question and an assessment question in one turn now clarifies; the
  policy gate no longer swallows the setting half.

## Gates

- `scripts/measure_routing.py`: gate PASS, 0 policy leaks, 0 authority bleed, 0
  false abstain, 0 fact mismatch; `abs-019` remains the known teaching residual.
- `scripts/measure_subject_routing.py`: gate PASS, 0 policy leaks, 0 authority
  bleed, 0 false abstain, 0 fact mismatch, 0 abstain misroute, 0 fixture fact id
  errors.
- `scripts/run_eval.py --check`: gate PASS.
- `scripts/run_rag_eval.py --check`: gate PASS against `rag-baseline.json`; the
  routing change does not move retrieval, generation, faithfulness or
  abstention.
- `pytest tests`, `pytest eval/`, `ruff check .` and the persona authoring check
  pass.

## Decision

Admitted to shadow. The `none` label is recorded in `docs/routing-contracts.md`
as the only deviation from the 2026-11-10 label restriction. `on` is not the
deployment default yet: the #184 gate still requires a week of live shadow
comparisons on the router event (`classifier_label`, `classifier_entry`,
`classifier_second`, `classifier_ms`, `deterministic_label`) before cutover.

The broad-request path and the tier disclosure in prose stay out of this ticket.

Operational note: the live lore pack is the gitignored `data/lore` volume. The
same aliases were applied there for the host measurement, but the deploy must
copy the updated pack to `/data/lore`; the code alone cannot add them to the
running volume. The frozen `eval/fixtures/lore` copy is the reproducible one.

## Live shadow check (2026-11-28)

Deployed image `bed73a09` with `OWL_INTENT_CLASSIFIER=shadow` and copied the
aliases to `/data/lore`. The first residual call failed with
`AccessDeniedException`: the instance role policy `owl-online-bedrock` allowed
Titan and the reranker, not Nova Micro. The policy now grants
`bedrock:InvokeModel` on the account-scoped APAC inference-profile pattern and
on `amazon.nova-micro-v1:0` in the six APAC regions. A second residual call
recorded `classifier_label=lore`, `classifier_entry=school-001`,
`classifier_ms=437.7` and `deterministic_label=abstain`, and the response stayed
abstained, which is the shadow contract.

Live verification also found a cache bug: a failed call was stored as `None`,
so a transient provider failure poisoned that question for the process. The
follow-up caches only a usable label; a failure is retried on the next turn.

## Reproduction

```text
uv run python scripts/measure_paraphrase_routing.py
uv run python scripts/measure_paraphrase_routing.py --holdout
uv run python scripts/measure_paraphrase_routing.py --check
uv run python scripts/measure_intent_classifier.py --mode on
uv run python scripts/measure_intent_classifier.py --mode on --holdout
uv run python scripts/measure_intent_classifier.py --mode on --no-previous
```

## Printed summary

Deterministic before, `ff21fec` with the frozen slices:

```text
== deterministic baseline (#327)
lore pack: 15 entries from eval/fixtures/lore
teaching terms: present
paraphrase: 32/77 contract, 27/63 entry, 5/6 stretched, 35 no entry
must_not: 1/40 false meta, 1 policy leak
multiturn: 8/22 contract, 16/22 fragment leak, 4/14 entry

paraphrase matrix
| expected | actual | n |
|---|---|---:|
| lore | lore | 32 |
| lore | lesson | 14 |
| lore | abstain | 23 |
| clarify | policy | 8 |

multiturn matrix
| expected | actual | n |
|---|---|---:|
| lore | lore | 4 |
| lore | lesson | 3 |
| lore | abstain | 7 |
| clarify | policy | 1 |
| policy | policy | 2 |
| policy | abstain | 2 |
| persona | lesson | 1 |
| lesson | lesson | 2 |
```

Deterministic after #327:

```text
== deterministic baseline (#327)
lore pack: 15 entries from eval/fixtures/lore
teaching terms: present
paraphrase: 69/77 contract, 56/63 entry, 5/6 stretched, 7 no entry
must_not: 0/40 false meta, 1 policy leak
multiturn: 10/22 contract, 16/22 fragment leak, 5/14 entry

paraphrase matrix
| expected | actual | n |
|---|---|---:|
| lore | lore | 61 |
| lore | lesson | 4 |
| lore | abstain | 4 |
| clarify | clarify | 8 |

multiturn matrix
| expected | actual | n |
|---|---|---:|
| lore | lore | 5 |
| lore | lesson | 2 |
| lore | abstain | 7 |
| clarify | clarify | 1 |
| policy | policy | 2 |
| policy | abstain | 2 |
| persona | lesson | 1 |
| lesson | lesson | 2 |
```

Classifier `on`, two fields:

```text
model: bedrock/apac.amazon.nova-micro-v1:0
mode: on
prompt chars (dada): 5680
paraphrase: 72/77 contract, 59/63 entry, 5/6 stretched
must_not: 0/40 false meta
multiturn: 17/22 contract, 10/14 entry, 14/22 fragment leak
classifier calls: 15; wall 6.5s
classifier acceptance: used=15 first=10 second=0 rejected=5
latency ms: p50=351 p95=445 min=316 max=458

paraphrase matrix
| expected | actual | n |
|---|---|---:|
| lore | lore | 64 |
| lore | lesson | 4 |
| lore | abstain | 1 |
| clarify | clarify | 8 |

multiturn matrix
| expected | actual | n |
|---|---|---:|
| lore | lore | 10 |
| lore | lesson | 2 |
| lore | abstain | 2 |
| clarify | clarify | 1 |
| policy | policy | 4 |
| persona | lesson | 1 |
| lesson | lesson | 2 |
```

Classifier `on`, one field (the comparison):

```text
model: bedrock/apac.amazon.nova-micro-v1:0
mode: on
prompt chars (dada): 5680
paraphrase: 72/77 contract, 59/63 entry, 5/6 stretched
must_not: 0/40 false meta
multiturn: 15/22 contract, 9/14 entry, 14/22 fragment leak
classifier calls: 15; wall 6.5s
classifier acceptance: used=15 first=7 second=1 rejected=7
latency ms: p50=349 p95=438 min=297 max=571

paraphrase matrix
| expected | actual | n |
|---|---|---:|
| lore | lore | 64 |
| lore | lesson | 4 |
| lore | abstain | 1 |
| clarify | clarify | 8 |

multiturn matrix
| expected | actual | n |
|---|---|---:|
| lore | lore | 9 |
| lore | lesson | 2 |
| lore | abstain | 3 |
| clarify | clarify | 1 |
| policy | policy | 3 |
| policy | abstain | 1 |
| persona | lesson | 1 |
| lesson | lesson | 2 |
```
