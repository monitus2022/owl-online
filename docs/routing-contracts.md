# Routing contracts and knowledge authority

This is the plan of record for the persona, lore and lesson routing boundary
(#216). It replaces the assumption that a router miss is a lesson question.

The current lesson venue sends `mode=lesson`, and `classify()` promotes any
`answer` fallthrough to `lesson`. That is the bug: unclassified traffic enters
the lesson path and abstains when the fact lives in the persona card or the lore
pack. A router miss is unclassified, not a teaching question.

## Three contracts

| Contract | Authority | What the user is asking | Allowed output | Never allowed |
|---|---|---|---|---|
| Policy | Reviewed scripts only | Exam contents, grading, mark scheme, syllabus as an assessment key, persona override | Exact script, or a scripted clarify if the ask is ambiguous | Any composer, corpus span or paraphrase of the refusal |
| Closed fact | Persona card or lore pack, stable fact IDs | Identity, biography, school, subject scope as setting, world facts with a canonical span | Retrieved fact IDs, then at most light verbalization that passes containment | Lesson citations, new claims, card/lore facts cited as book chunks |
| Teaching | Lesson corpus only | Explain, apply, compare, work an example from the materials | Persona-first composition, every claim entailed by a lesson span, lesson citations only | Card/lore facts laundered as book citations, policy content |

"What is included in DADA?" is ambiguous before retrieval: it can mean the lore
scope fact `lore:dada-001` or the assessment policy
`policy:assessment.dada`. The gate clarifies. A direct scope question such as
"What topics does DADA cover?" is the lore fact; a direct assessment question is
policy. Distinguish the relation before any retriever runs.

"Where did you study when you are young" is a closed persona fact with a typo.
It never reaches the corpus.

Composition is justified only when the gold answer cannot be a short reviewed
span: the student wants explanation, elaboration or application, and the claims
are checkable against lesson spans. If a reviewer could write the answer as one
card or lore sentence, retrieve it.

## Gates, in order, before any model and before the lesson retriever

1. Policy gate, fail closed. High-precision cues for exam, grade, mark scheme,
   "what is on the test", syllabus-as-key and jailbreaks. A hit returns the
   script and stops. A near-hit clarifies or returns the script. It does not
   fall through. False negatives here are the only routing errors that matter
   more than a false abstain.
2. Closed-fact gate over a lexicon, not a phrase list. Normalize first:
   lowercase, light typo correction against a closed lexicon of persona names,
   schools, subjects and relation words (study, young, included, covers). Match
   slots, not full utterances:
   - `(subject=DADA, relation=scope)`
   - `(entity=self, relation=education, time=youth)`
   - `(entity=Ashcombe, relation=location|founding)`
   A slot match returns fact IDs. No fact IDs means the gate does not fire. It
   does not mean "send to lessons".
3. Teaching gate. Only when the first two miss, the utterance looks like an
   explanatory request, and the lesson retriever returns spans that entail an
   answer. Otherwise clarify or abstain. Abstain is a successful policy outcome.
   Citing a book chunk for a setting fact is not.

The lesson path is opt-in. Residual traffic is not RAG.

## Citation authority

| Type | Source | Used by |
|---|---|---|
| `policy:script:<id>` | Reviewed script | Policy |
| `persona:<fact_id>` | Persona card | Closed fact |
| `lore:<fact_id>` | Lore pack | Closed fact |
| `lesson:<doc_id>#<span>` | Lesson corpus | Teaching |

A setting answer with no `persona:` or `lore:` cite is invalid. A setting answer
with a `lesson:` cite is invalid even if the book mentions the same noun. A
teaching answer that cites `lore:` for a curricular claim is invalid. The corpus
`answer` path may carry a setting or a lesson authority, but not both, and never
policy; a `needs_input` feedback request has nothing to cite yet. This is an
authority check, not a prompt instruction.

The API now carries the typed field as `typed_citations` alongside the legacy
`citations`, `lore_citations` and `material_citations`; `app/knowledge/citations.py`
holds the parser and the cross-type checker, and the final payload reports
`citation_errors`. The frontend renders the typed chips when present and falls
back to the legacy fields otherwise. The cross-type fixture is
`eval/routing/fixtures/citations.jsonl`; `eval/routing/test_citations.py` runs
the checker over every row.

The fixture uses fact IDs; the emitted cite IDs are a small mapping:

| Fact ID | Emitted cite |
|---|---|
| `policy:assessment.dada` | `policy:script:assessment.dada` |
| `persona:professor.education` | `persona:professor.education` |
| `lore:dada-001` | `lore:dada-001` |
| `lesson:dada-dueling-disarming-charm` | `lesson:dada-dueling-disarming-charm#<span>` |

## DADA is the sharp case

Store two facts when both are true, and route on the relation, not the entity:

- `lore:dada-001` - what the department covers, as setting. Answerable.
- `policy:assessment.dada` - what the sitting will test, how it is graded, the
  syllabus as a key. Scripted refusal.

If the utterance does not disambiguate, clarify. Do not let the book retriever
break the tie.

## Authority assignment

Pick one authority per fact, even when the card and the lore pack overlap:

- `lore:school-001` owns school location, founding, student count, houses and
  departments. The card's `school` reply is a scripted variant, not the fixture
  authority.
- `lore:dada-001` owns subject scope; `lore:dada.scope` is its stable alias.
  `persona:subject` owns the role and definition ("what is your subject",
  "what is DADA"). `persona:professor.education` is a template join over the
  card's `study_place` and `youth_period` facts.
- `lore:auror-001` owns the Auror pathway. `persona:professor.background` owns
  Crane's own service.
- `lore:teaching-record` owns the set-texts policy.
- `lore:public-record-people`, `lore:public-record-war` and
  `lore:public-record-limits` own the public-history boundaries.

A fact that genuinely has two readings is a clarify, not a guess.

## Composer

A constrained meta composer is reasonable only inside the closed-fact contract,
after fact IDs are already retrieved.

- Input is the condensed pack for those IDs, not the corpus and not the raw card
  dump.
- Output is verbalization, not retrieval. It may not add a fact, hedge a fact
  into a new claim, or pull in a lesson span.
- Deterministic containment: split the draft into atomic claims; each claim must
  be entailed by a provided fact ID; every fact ID used must appear as a cite of
  the matching type; unused IDs are fine; unknown IDs fail.
- On failure, fall back to the scripted fact text or abstain. Never fall back to
  free generation or to the lesson path.

Do not put the composer on exam, syllabus or grading. Keep pure single-fact
answers scripted if the reviewed sentence already exists. Composition earns its
keep only when two or three fact IDs must be joined into one spoken turn. If
containment cannot be implemented as a real entailment check, do not ship the
composer. A regex that checks that a bracketed id appears will bless fluent
inventions.

Refuse the composer when the route is policy, the fact IDs came from a
low-confidence classifier, the pack is empty, the draft uses a lesson span, the
same utterance tripped a policy near-hit, or a sentence cannot be attributed to
a fact ID in shadow eval.

## Measurement

The policy and closed-fact gates are subject-parameterized through the persona
registry (#222). The DADA fixture is
`eval/routing/fixtures/contracts.jsonl`, frozen before cue tuning; the SHA-256 is
pinned in `eval/routing/test_fixtures.py`. It has 207 items across policy,
persona, lore, lesson, abstain and clarify, with 14 held-out policy, persona,
lesson, abstain and clarify items that are not for cue tuning. Policy is the
largest stratum (51 of 207).

The five-card companion is `eval/routing/fixtures/subjects.jsonl`: 11 items per
subject (55 total), one held-out policy paraphrase per subject, and a required
`What is included in <Subject>?` clarify item. Its SHA-256 is pinned in
`eval/routing/test_subjects.py`. `scripts/measure_subject_routing.py` loads the
published pack for each subject, computes the teaching terms, and reports the
same matrix and gate per subject.

Each item records:

- utterance;
- gold contract;
- gold fact IDs;
- fact-present flag;
- category and note;
- holdout flag.

Metrics, in gate order:

- Policy leak: non-script answer on a policy item. Target effectively zero on
  the holdout. This alone can block a model.
- Authority bleed: a `lesson:` cite on a persona/lore item, or a `lore:` or
  `persona:` cite used to support a teaching claim. Target zero.
- False abstain given fact present: the card or lore contains the gold fact ID
  and the system abstained or went to lessons. Track this separately from
  ordinary out-of-scope abstains. Clarify items are excluded; a clarify is not
  a false abstain.
- Unsupported claim rate on composed answers, judged against the provided pack
  or lesson spans.
- Clarify precision: clarifications that were genuinely ambiguous.

Report a confusion matrix over contracts, not a single accuracy. A system that
routes everything to abstain scores well on policy leak and fails the product. A
system that routes residual to lessons does the opposite.

## Gate baseline

The 2026-11-10 measurement on the frozen fixture (207 items, DADA subject)
reports:

- policy leaks: 0
- authority bleed: 0
- false abstain given fact present: 0
- fact mismatch: 0
- over-clarify: 0
- matrix: policy 51/51; persona 37/37; lore 37/37; lesson 40/40; clarify 18/18;
  abstain 23/24.

The one abstain-to-lesson residual is the hex-versus-jinx distinction: the
terms match the pack but no material entails the distinction. The lesson node
still abstains at runtime when no span is found, and it reports `mode=abstain`
in the final payload. The script is `scripts/measure_routing.py`; it exits
non-zero on a policy leak, authority bleed, false abstain, fact mismatch or
any abstain item routed away from abstain except the hex-versus-jinx residual.

## Residual and classifier

Measure the residual after the deterministic layer, including typo
normalization and slot cues, not before. Split misses into:

- typo or normalization;
- paraphrase of a known slot;
- multi-intent;
- true ambiguity, which needs a clarify;
- no such fact, which must stay abstain;
- teaching wrongly caught by a fact cue.

Only the paraphrase bucket is a candidate for a classifier. Typos are a lexicon
problem. Ambiguity is a clarify script. "No such fact" stays abstain.

Add a residual classifier only if all of these hold on the untouched holdout:

- policy leak stays at the scripted-system rate;
- the paraphrase residual is material, on the order of several percent of real
  sessions after normalization and slot cues;
- another round of cues would be open-ended synonym lists rather than a closed
  lexicon;
- the classifier cannot emit `lesson`; its labels are `policy`, `persona`,
  `lore`, `clarify`, `abstain`;
- high-risk labels require a high threshold, and below threshold they clarify or
  abstain;
- shadow mode on live traffic for a week before cutover.

#184 carries the residual measurement and classifier decision.

## Decision (2026-11-10)

The deterministic layer leaves one residual on the 207-item DADA fixture and
zero on the 55-item five-subject fixture. The one residual is `abs-019`, the
hex-versus-jinx distinction: the teaching terms match the pack but no material
entails the distinction, and the lesson node abstains at runtime. That is a
lesson-gap, not a paraphrase residual, and a classifier cannot fix it.

The residual is not material: 1 item in 207, with zero policy leaks, authority
bleed, false abstain and fact mismatch. No classifier is added. The fixture and
the two measurements stay as the regression guard. Revisit only if a new
fixture slice produces a material paraphrase residual after normalization and
slot cues, or if a policy or authority miss appears; the conditions above still
apply.

## Current state against the target

| Target | State |
|---|---|
| Policy, closed-fact and teaching gates; a miss clarifies or abstains | Implemented in #219 |
| Closed-fact gate over a normalized lexicon and relation slots | Implemented in #219 and #220 |
| Lexicon plus slots, no full-utterance matching | Implemented in #219 |
| Lesson citations only after the teaching gate | Implemented in #219 and #218 |
| Typed citation authority and a cross-type checker | Implemented in #218 |
| Stable `persona:` fact IDs and templates | Implemented in #220 |

## Migration order

1. #217: this note and the frozen fixture. Done.
2. #222: the multi-subject persona registry and policy for all five departments. Done.
3. #219: the three gates and the unclassified default, parameterized by the registry. Done.
4. #218: typed citations and the authority checker. Done.
5. #220: persona and lore fact IDs, plus templates for the five cards. Done.
6. #184: residual measurement, then the classifier decision. Done: no classifier.

## Non-goals

- No classifier before the fixture and the deterministic residual are measured.
- No composer on exam, syllabus or grading.
- No fact pack injected into the lesson prompt as a shortcut.
- No model allowed to emit `lesson`.
- No lesson citation for a setting fact.

Refs #97, #176, #177, #184, #216.
