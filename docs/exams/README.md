# Exam bank artifacts

The exam bank is the offline pool a paper is sampled from. The paper and attempt
records are served from the same SQLite store (#193), not from #38.

## Layout

```text
data/exams/<subject>/
    manifest.toml   bank version, pack pins, generator and judge config, counts
    bank.jsonl      one BankItem per line

data/exams/exams.db SQLite serving copy imported from the validated JSONL,
    plus the attempts and attempt_questions tables written at serve time

docs/exams/<subject>-<version>.md
    structure-only record: counts, ids, coverage and validation summary
docs/exams/<subject>-<version>.manifest.toml
    committed snapshot of the published manifest (no prose)
```

The JSONL is the authoring source. The SQLite store is a deterministic import,
not a second source of truth. Both live under `/data`; question prose and
evidence quotes are not committed. The published snapshot under `docs/exams/`
is structure only.

## Records

| Record | Purpose |
|---|---|
| `BankManifest` | subject, tier, version, status, built_at, reviewed_at, pack version and fingerprint, index text hash, generator model, temperature and prompt version, judge model, temperature and prompt version, MCQ and short-answer counts |
| `BankItem` | one question: id, kind, prompt, topic, concepts, material id, source refs, evidence snapshot, difficulty, marks, rubric, required points, model answer, options and correct option id for MCQ, rationale, review status, prompt version |
| `McqOption` | one stored option: option id and text |
| `RubricCriterion` | criterion id, description and maximum marks |
| `ShortAnswerKey` | golden answer, 2-3 required points and the rubric for one short answer |
| `EvidenceSnapshot` | chunk id, book, chapter, quote, text hash and index text hash captured at generation time |

MCQ items store at least six options and exactly one correct option. A second
correct option is structurally impossible because the item stores one
`correct_option_id` and option ids are unique. A paper view serves four options:
the correct option plus three random distractors. The client never receives the
correct option id or the other two options.

Short-answer items store a 2-3 sentence, 25-80 word golden answer, 2-3 required
points and a rubric that sums to 8 marks. The rubric must include `correctness`
and `completeness` criteria. The judge compares the student answer with the
golden answer and the rubric.

## Question scope

Questions test the subject, not the plot. They ask about spells, creatures,
defences, mechanisms, limits, comparisons and application: what a spell does,
when it works, what it cannot do, and what danger it protects against. They do
not ask about plot events, character biography or classroom anecdotes. A scene
can supply the evidence for a concept question, but the question must stand on
the subject concept and the evidence, not on knowing the story.

Neither the prompt nor the golden answer may name a character, house, book or
scene, and a student must not need story knowledge to answer. Write "a caster",
"a target" or "a learner" instead of a named person. Evidence may quote a scene;
the item restates the concept in general terms. An item that only makes sense
after reading the cited scene is rejected, however well grounded its evidence.

Exam administration and classroom pedagogy are not bank content. Items do not
ask about papers, practicals, lessons, teachers, revision or school rules: the
student is already sitting the assessment, so those items test the setting
rather than the subject. They ask about the underlying charm concept instead.
The authoring script enforces both rules with a character, scene and pedagogy
denylist.

## Grading

MCQ answers are scored deterministically by option id; no model call. Short
answers are judged in one call per attempt against the stored golden answer,
rubric and evidence. The judge is pinned by the bank manifest: model,
temperature 0, prompt version and per-item rubric version. It must be a
different family from the generator.

The judge returns a `results` object keyed by item id. Every criterion must
appear once, `0 <= awarded <= max_marks`, the total must be the sum, and
evidence ids must be a subset of the item's source refs. A malformed or
incomplete response gets one retry for the affected questions; a second failure
sets `needs_review` and never a silent zero.

Totals and bands are computed by code. The bands are percentage-based:
O at least 90 percent, E at least 80, A at least 70, P at least 50, D at least
30, and T below 30. Grading results are cached by bank version, item id, answer
hash, rubric content and judge configuration under
`data/exam_judge_cache.jsonl` (gitignored).

The published bank's live probe is
`docs/exams/dada-1.0.0-grading-probe.md`. The bank eval and judge calibration
are `eval/exam/` (#191), run with
`uv run python scripts/run_exam_eval.py`; the record is
`docs/runs/2026-11-09-191-dada-bank-eval.md`.

## Serving

The serving routes read the published bank from `data/exams/exams.db`, never the
JSONL:

| Route | Behaviour |
|---|---|
| `GET /v1/exams` | paper descriptor: 10 questions, 6 MCQ, 4 short answers, 50 marks, 60 minutes |
| `POST /v1/exams/{paper_id}/attempts` | sample 6 MCQ and 4 short answers, persist them, return the attempt view |
| `GET /v1/attempts` | graded attempts for the current session, newest first, no question detail |
| `GET /v1/attempts/{attempt_id}` | the same persisted view on a reload |
| `POST /v1/attempts/{attempt_id}/grade` | deterministic MCQ plus one judge call, then the deterministic band |

The paper id is `<subject>-<version>`, so the served DADA paper is
`dada-1.0.0`. A sampled MCQ serves the correct option and three random
distractors in a shuffled order; the correct option id stays on the persisted
attempt and is never in the pre-submission view. The attempt view contains no
golden answer, rubric or evidence either.

The attempt is persisted before it is returned, so a reload is stable and a
repeated grade returns the stored result without a second judge call. Grading
also stores the submitted answers with the grade so a result can be audited.
The grade response carries the MCQ key, per-question marks, model answer,
feedback, criteria and the band. An unresolved judge result sets
`needs_review` and leaves the total and band null.

Attempts are scoped to the signed anonymous session cookie. The list route
returns only the current session's graded attempts, and fetching or grading
another session's attempt is a `404`. The cookie lasts 24 hours from first
issue, so the history is browser-session history, not cross-device history;
auth (#35) later claims these rows and moves the limit to a user id. The
frontend reads the list route instead of localStorage.

Attempts are capped per session at three per day anonymous and five per day
signed-in, with a separate nine-per-day per-IP cap; over a cap is `429` with
`Retry-After`. The signed-in path is reserved for auth (#35), so the route
currently admits everyone as anonymous. The exam limiter is separate from the
chat limiter. The exam judge is built when a published bank exists; a missing
judge configuration is caught at startup, so papers still serve and grading
returns `503`. A provider failure during grading is `502`.

Serving settings: `OWL_EXAM_STORE_PATH` (default `data/exams/exams.db`),
`OWL_EXAM_SUBJECT` (default `dada`), `OWL_EXAM_MCQ_COUNT` (6),
`OWL_EXAM_SHORT_COUNT` (4), `OWL_EXAM_DURATION_MINUTES` (60),
`OWL_EXAM_ATTEMPTS_PER_DAY_ANONYMOUS` (3),
`OWL_EXAM_ATTEMPTS_PER_DAY_SIGNED_IN` (5) and
`OWL_EXAM_ATTEMPTS_PER_DAY_IP` (9).

## Bank 1.0.0 quality notes

The bank eval gates the share of MCQs whose correct option is strictly the
longest at 90 percent and reports the mean length gap. DADA 1.0.0 is at 80
percent with a 1.28-word mean gap, so it passes at the cap and is scheduled for
option-length levelling in the next bank revision. The independent solver
selects the stored key on every MCQ and finds no second defensible option.

The eval also gates a strict one-MCQ and one-short-answer per material; the
1.0.0 bank has no recorded slot swaps. The calibration gate treats any
needs_review as a failure because a reviewed state is not modelled yet; the
1.0.0 run has no needs_review.

## Status flow

| Status | Meaning |
|---|---|
| `draft` | records may be incomplete; the importer refuses it unless `--allow-draft` is passed |
| `validated` | the deterministic validator passes; the importer accepts it |
| `published` | every item is reviewed, every pin matches, and the bank may be served |

A published bank must have `built_at` and `reviewed_at` values, a generator
model, temperature and prompt version and a judge model, temperature and prompt
version. An unreviewed item in a published bank is an error. A published version
is immutable in the serving store unless the importer is run with `--force`; a
paper or attempt may already point at its item ids.

## Validation

```text
uv run python scripts/validate_exam_bank.py --subject dada --record docs/exams/dada-1.0.0.md
uv run python scripts/import_exam_bank.py --subject dada
```

The validator checks:

- the source pack is published;
- the manifest subject, tier, pack version, pack fingerprint and index hash
  match the published pack and the current corpus;
- every item resolves to a published pack topic and concept and a reviewed material;
- the item topic matches the material topic and the material's concept is in
  the item's concept set;
- every source ref belongs to the cited material and resolves to a current
  chunk with a matching text hash, quote, book and chapter;
- the evidence snapshot matches one source ref;
- MCQ option count, option uniqueness, correct-option membership, all-of-the-
  above and none-of-the-above rejection, and stored answer-position reporting;
- short-answer golden answer length, correctness and completeness criteria,
  required points, mark total and lexical grounding;
- exact duplicate prompts;
- published status requires reviewed items, built_at and a complete generator
  and judge pin.

The validator reports every problem it can see, not just the first one. The
`--record` output is written only after a successful validation; it contains
counts, ids, topic, concept and difficulty coverage, the review date and the
validation summary, never prompts, golden answers or evidence quotes. The
near-duplicate, independent-verification and review sections are run-specific
and are appended after the command. The 25 + 25 count target and the topic
quotas are authoring gates in #190; this schema validator reports coverage but
does not hardcode the DADA target.

## Source policy

- Only primary, books-scoped canon is exam-gradable.
- Every item cites a published subject material and at least one book source ref.
- Evidence snapshots are stored with the item so a later index rebuild is
  detectable.
- The Lexicon is discovery only; it is never a source ref and its prose is
  never copied.

Related tickets: #187 (epic), #188 (blueprint), #189 (schema), #190 (this
bank), #191 (quality), #192 (grading), #193 (serving).
