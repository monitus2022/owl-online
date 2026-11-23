# Persona authoring

This is the brief-driven pipeline for professor persona cards (#297). The
runtime still reads committed TOML cards; the model only drafts them offline.

## Principles

- A human writes the brief with the non-negotiable facts and the voice
  direction.
- A pinned prompt and an approved model draft the copy.
- Deterministic validators and the app's own persona loader check the draft.
- A human reviews the diff, the brief and the persona probes before publishing.
- No model runs when a student chats. The card is static at request time.

Charms is the first migrated card (#303) and Potions the second (#312): each
has a brief, a published card and provenance. Herbology and Transfiguration
are legacy for this pipeline: they have no brief or provenance yet. DADA is the
standalone seed card and is never published through this pipeline.
`python scripts/author_persona.py check` reports the unmigrated cards as a
warning and passes. DADA is outside the pipeline by design, so it is not a
migration candidate and does not block `--strict`; strict turns the Herbology
and Transfiguration warnings into a failure once those briefs are ready.

## Layout

| Path | What it is |
|---|---|
| `config/personas/spine.toml` | The shared school facts, boundaries, exam refusals and scripted base copy |
| `config/personas/briefs/<subject>.toml` | Human-authored seed for one persona |
| `config/personas/<subject>.toml` | The live card, a delta merged over the spine |
| `config/personas/provenance/<subject>.json` | Brief/card hashes, model, prompt version and reviewer |
| `config/personas/drafts/<subject>.toml` | A generated draft, never loaded by the app |
| `config/personas/examples/charms.toml` | A complete example brief. `check` validates its brief contract but does not pair it with a card or provenance; a migration brief must describe the existing reviewed card and use its live professor, not this illustrative name. |
| `app/agent/persona_authoring.py` | Brief schema, prompt, JSON parser, TOML renderer, validators, provenance |
| `scripts/author_persona.py` | The generate, validate, check and publish CLI |
| `tests/test_persona_authoring.py` | Contract and validator tests |

The DADA card is `config/persona.toml` and remains the standalone seed. The
merged pipeline does not publish DADA; that would need a full-card mode.

## Brief fields

A brief fixes the facts; the model writes the voice. See the example for a
complete file.

| Field | Meaning |
|---|---|
| `subject` | The taxonomy key, for example `charms` |
| `name`, `address`, `role`, `subject_title` | The fixed identity; copied into the card |
| `background` | Three to five original facts about the professor |
| `voice` | Voice direction for the generated meta lines; personal, abstain and greeting are copied from the spine |
| `stance` | The fixed teaching stance; copied into the card |
| `teaching` | How the professor teaches, corrects and sets practice |
| `relationships` | Original relationships to the other founders |
| `examples` | Two to six example lines that show the voice |
| `avoid` | Things the generated copy must not do |
| `facts` | Fixed fact ids and values; the model copies them |
| `templates` | Fixed templates; every placeholder must resolve to a fact |

A brief that names a canon staff member, omits facts or templates, or points a
template at a missing fact is rejected before generation. The shared spine also
contributes a `subject_scope` template, so a merged card's facts must include
`subject` and `subject_scope` (the live cards do) as well as the professor's own
facts.

## Commands

Print the pinned prompt without a model call:

```text
uv run python scripts/author_persona.py generate \
  --subject charms \
  --brief config/personas/examples/charms.toml \
  --dry-run
```

Generate a draft (requires the configured provider and model access):

```text
uv run python scripts/author_persona.py generate --subject charms
```

The default draft and sidecar are `config/personas/drafts/charms.toml` and
`config/personas/drafts/charms.json`. `--out` must stay under
`config/personas/drafts/` and end in `.toml`; the command cannot write a live
card, the spine or another repository file.

Validate a draft or a live card against its brief:

```text
uv run python scripts/author_persona.py validate --subject charms \
  --card config/personas/drafts/charms.toml
```

Check every brief/card/provenance set (CI):

```text
uv run python scripts/author_persona.py check
uv run python scripts/author_persona.py check --strict
```

Publish a reviewed draft:

```text
uv run python scripts/author_persona.py publish --subject charms \
  --reviewer "Owner Name"
```

`publish` uses the canonical `config/personas/briefs/<subject>.toml`; a
`--brief` path outside `briefs/` is refused, so an illustrative example cannot
replace a live professor. If the live card already belongs to a different
professor, the command refuses unless `--replace-identity` is passed. It
validates the merged card and provenance, verifies the recorded prompt and
spine hashes, writes the live card and records the reviewer and the final card
hash. The human still reads the diff and commits it. The command refuses
`dada`.

## The generated JSON

The model returns one object:

- `identity`: exactly `name`, `address`, `role`, `subject`, copied from the brief.
- `register`: exactly `stance`, copied from the brief.
- `meta`: exactly `identity`, `scope`, `subject`, `professor`, `boundaries` and
  `greeting`. `identity`, `scope`, `subject` and `professor` carry three to
  five variants; `boundaries` keeps exactly the three reviewed shapes and
  `greeting` is copied from the spine.
  The shared exam, syllabus, grading, school and auror topics come from the
  spine.
- `personal` and `abstain`: copied from the spine unchanged.
- `facts` and `templates`: copied from the brief.

The draft delta never carries the top-level `[boundaries]` policy, school, tone
or pacing; those stay in the spine. It does carry the required `meta.boundaries`
subject guidance. It carries `meta.greeting`, `personal.response` and
`abstain.response` as copies of the spine, and the validator rejects a
paraphrase; the other shared meta topics are not generated.

## Validation

`generate` checks the draft before writing it. `validate` and `check` load the
merged card through `app/agent/persona.py`, so the same rules that protect
startup protect the review.

The checks include:

- required identity, stance, facts and templates match the brief exactly;
- the card delta does not add the spine sections or keys: no top-level
  `[boundaries]`, no `identity.school`, no `register.tone` or `pacing`, and no
  shared meta topic;
- shared spine facts and templates are unchanged; only `professor.background`
  is overridable;
- every generated meta topic has the required count, and personal, abstain and
  greeting match the spine;
- every background line's proper nouns reach `meta.professor`, so the Ministry
  scheme or the Auror Office cannot be dropped;
- every `meta.scope` variant leaves the other four departments to colleagues,
  and no `meta.subject` variant says who teaches the subject;
- no empty or duplicate variants;
- variant length bounds;
- no placeholders, HTML, URLs, model or provider wording, or canon names in
  the prose, address, role, facts or templates;
- the loader's own required boundaries, meta topics, facts and templates;
- the brief and card hashes, the recorded prompt version/hash, the spine hash
  and a non-empty reviewer in provenance.

The model does not decide the facts. A changed name, address, role, subject,
stance, fact or template is a validation failure, not a prompt suggestion.

`generate` retries when a draft fails, feeding the exact problems back to the
model; a draft that still fails is never written. The retry is a convenience,
not a weaker gate: the same checks run in `validate`, `publish` and `check`.

## Persona review

Before publishing a card, run:

```text
uv run pytest tests/test_persona_authoring.py tests/test_personas.py tests/test_persona.py tests/test_persona_graph.py
uv run pytest eval/
uv run python scripts/author_persona.py check
```

`eval/persona/` holds the persona conformance suite that CI runs; every card
copy change needs it, not only a change to the answer prompt. A full RAG eval
run needs a record under `docs/runs/`; a `--check` gate does not.

Review checklist:

- The brief's facts are original and consistent with the subject.
- Every variant says the same thing; no new facts, advice or exam details.
- The voice fits the professor and differs from the other cards.
- The shared boundaries and school facts are unchanged.
- The generated copy and the fixed address, role, facts and templates do not
  name a canon figure.
- The persona probes pass for identity, scope, school, exam, boundaries,
  greeting, personal, abstain and off-subject questions.
- The diff is small enough to read; the provenance names the reviewer.
- The docs card (`docs/personas.md`) is updated in the same change.

## Migration and future subjects

Charms is the worked example. Do not regenerate the remaining cards all at
once: write one brief that describes the reviewed card, generate, compare the
diff, review and publish. Then repeat.

A new subject still needs the product wiring: the subject key in the taxonomy,
`PERSONA_SUBJECTS`, the venue entry and the frontend copy. The authoring
pipeline writes the card, but it does not make a new subject loadable. That is
a follow-up.

## Notices

The abstain and off-pack notices can be generated from the same brief as
reviewed variants. Choose one owner: the persona card or a frontend copy module.
Do not keep a persona line in the card and a different generic line in the UI.
The runtime selection should be deterministic or randomly chosen from the
reviewed set, never generated per request.
