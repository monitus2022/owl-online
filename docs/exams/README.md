# Exam bank artifacts

The exam bank is the offline pool a paper is sampled from. It is separate from
the paper and attempt records in #38.

## Layout

```text
data/exams/<subject>/
    manifest.toml   bank version, pack pins, generator and judge config, counts
    bank.jsonl      one BankItem per line

data/exams/exams.db SQLite serving copy imported from the validated JSONL

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
| `BankManifest` | subject, tier, version, status, built_at, pack version and fingerprint, index text hash, generator model and prompt version, judge model and prompt version, MCQ and short-answer counts |
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

## Status flow

| Status | Meaning |
|---|---|
| `draft` | records may be incomplete; the importer refuses it unless `--allow-draft` is passed |
| `validated` | the deterministic validator passes; the importer accepts it |
| `published` | every item is reviewed, every pin matches, and the bank may be served |

A published bank must have a built_at value, a generator model and prompt
version and a judge model and prompt version. An unreviewed item in a published
bank is an error. A published version is immutable in the serving store unless
the importer is run with `--force`; a paper or attempt may already point at its
item ids.

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
counts, ids and coverage, never prompts, golden answers or evidence quotes. The
25 + 25 count target and the topic quotas are authoring gates in #190; this
schema validator reports coverage but does not hardcode the DADA target.

## Source policy

- Only primary, books-scoped canon is exam-gradable.
- Every item cites a published subject material and at least one book source ref.
- Evidence snapshots are stored with the item so a later index rebuild is
  detectable.
- The Lexicon is discovery only; it is never a source ref and its prose is
  never copied.

Related tickets: #187 (epic), #188 (blueprint), #189 (schema), #190 (this
bank), #191 (quality), #192 (grading), #193 (serving).
