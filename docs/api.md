# API

The served surface is FastAPI. Chat is unversioned today; `GET /v1/subjects`
and the exam serving routes are versioned. The remaining planned `/v1` aliases
are listed below. The academy frontend has already split into its own static
build (`web/`, served on Cloudflare Pages) and calls the chat routes and the
served exam bank, relying on the CORS origin regex and the session cookie. The
remaining versioned aliases are listed below. The chat request already carries
an optional subject so the request uses that department's persona card.

Base URL: the deployment origin, for example `https://api.monitus.org`.

## Current endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | liveness; returns `{"status": "ok"}` |
| `GET` | `/` | JSON service descriptor; the API host does not serve a chat page |
| `GET` | `/v1/subjects` | published subject packs plus the `lesson`, `lesson_subjects`, `lesson_fallback`, `persona` and `persona_subjects` flags |
| `POST` | `/ask` | one-shot grounded answer |
| `POST` | `/ask/stream` | chat over server-sent events |
| `GET` | `/v1/exams` | published paper descriptors, filtered by subject and version |
| `POST` | `/v1/exams/{paper_id}/attempts` | sample and persist a paper attempt |
| `GET` | `/v1/attempts` | graded attempts for the current session, newest first |
| `GET` | `/v1/attempts/{attempt_id}` | the persisted pre-submission attempt |
| `POST` | `/v1/attempts/{attempt_id}/grade` | deterministic MCQ scoring plus the pinned rubric judge |

The API host serves only the API. The academy frontend is the Cloudflare Pages
build; `GET /` is a small JSON descriptor, not a chat page. The old single-file
chat page was removed so the API origin cannot be used as a second chat surface.

### `GET /`

A stable service descriptor. It is a liveness alias for `/health` and a pointer
to the subject index; it is not a chat surface.

Response `200`:

```json
{
  "service": "owl-online-api",
  "status": "ok",
  "health": "/health",
  "subjects": "/v1/subjects"
}
```

### `POST /ask`

Request:

```json
{"question": "Who teaches Defense Against the Dark Arts in book 4?", "subject": "dada"}
```

`question` is trimmed, must be 1 to 1000 characters, and must not be blank.
`subject` is the department key; empty means `OWL_PERSONA_SUBJECT`. The
registered card for that subject is active, so a Charms request uses Professor
Raman and a DADA request uses Professor Crane. An off-taxonomy key is a `422`;
a valid department without a card answers persona-off.

Response `200`:

```json
{
  "answer": "Alastor Moody ... [b4-c25-0075]",
  "citations": ["b4-c25-0075"],
  "abstained": false,
  "lore_citations": [],
  "material_citations": []
}
```

`citations` are book chunk ids. `lore_citations` are setting-entry ids in the
`[lore:<id>]` space. `material_citations` are lesson-material ids; it is always
empty on `/ask`, which stays corpus-only, and lesson answers are stream-only.
The citation spaces are validated separately; an unknown id of any kind is
stripped from the text. `abstained` is true when there is no book or lore
evidence, the draft cites nothing, or the model refuses. The answer text is
always returned; an abstention is a `200`, not an error.

### `POST /ask/stream`

Request:

```json
{
  "question": "Who teaches Defense Against the Dark Arts in book 4?",
  "subject": "dada",
  "mode": "auto",
  "student_answer": null
}
```

`subject` follows the same rule as `/ask`: the registered card for that subject
is active, and omitted means `OWL_PERSONA_SUBJECT`. An unknown subject is a
`422`. `mode` is `auto`, `answer`, `practice`, `feedback` or `lesson`. `student_answer`
is at most 6000 characters and is only valid with `auto` or `feedback`. When the
persona is on, the server may also route to `meta`, `personal`, `fact` or
`clarify`; those are not accepted as request modes. `lesson` is explicit only, never inferred, and is
rejected with `400` unless `OWL_LESSON_MODE` is on and the request subject has a
published pack loaded.
It is a preference for the answer path, not an absolute route: practice,
feedback, meta and personal keep their normal handling, so a venue that defaults
to lesson still greets and tests correctly.

The response is `text/event-stream`. Events:

| Event | Data | When |
|---|---|---|
| `mode` | `{"mode": "answer"}` | after the router; can be `answer`, `practice`, `feedback`, `meta`, `personal` or `lesson` |
| `token` | `{"text": "..."}` | each streamed token |
| `reset` | `{}` or `{"reason": "retry"}` / `{"reason": "fallback"}` | clear the draft before a retry, a fallback, an error, or an abstained final |
| `final` | `answer`, `citations`, `lore_citations`, `material_citations`, `scope`, `abstained`, `needs_input`, `attempts`, `mode` | once, authoritative |
| `error` | `{"detail": "..."}` | terminal; always preceded by `reset` |

`final` is the authoritative payload. A client should replace the draft on
`reset` and render `final` when it arrives. Once the stream has started, a
provider failure is an `error` event, not an HTTP status.

### Lesson mode

With `OWL_LESSON_MODE=true` and a published pack loaded, a request with
`"mode": "lesson"` answers from reviewed pack materials first. When the pack is
thin it adds a labelled corpus tier instead of refusing:

```json
{
  "answer": "Moody showed the curses two years early ... [mat:dada-countering-countercurse-doctrine]",
  "citations": ["b4-c14-0006", "b4-c14-0009"],
  "lore_citations": [],
  "material_citations": ["dada-countering-countercurse-doctrine"],
  "scope": "in_pack",
  "abstained": false
}
```

`material_citations` are `[mat:<material_id>]` ids, validated against the
materials selected for that answer. For a pack-backed answer, `citations` are the
book chunk ids those materials resolve to through their `source_refs`. A mixed or
off-pack answer also cites the retrieved set-text chunks; `off_pack` has empty
`material_citations`. The selector is
derived at startup by embedding the material texts in memory; no second index is
built or stored. `subject` is the request field; omitted means
`OWL_PERSONA_SUBJECT`. Lesson answers are never cached.

The embedding selector's best-match cosine must clear `OWL_LESSON_MIN_SCORE`
(default 0.58, calibrated for the local `qwen3-embedding:0.6b`: related
questions 0.598-0.791, off-topic 0.160-0.549). A curated concept-title or alias
match can still add a material when a comparison question embeds weakly, so
"Compare Expelliarmus with Avifors" keeps the Disarming Charm note.

`scope` says where the evidence came from:

| `scope` | Meaning |
|---|---|
| `in_pack` | The selected materials and their concept titles/aliases cover the question; the answer cites `[mat:]` and the materials' source refs. |
| `mixed` | The materials cover part and the corpus covers the rest; the answer cites both `[mat:]` and book chunk ids, and labels the set-text part. |
| `off_pack` | No material is selected; the corpus answers, the answer starts "This is not in the department's notes", and `material_citations` is empty. |
| `abstained` | Neither tier has evidence, the draft refused, or a required citation space is missing; includes a pack-only partial with no corpus evidence. |

With `OWL_LESSON_FALLBACK=true` (default), a question the pack does not cover
retrieves the corpus as a labelled second tier instead of abstaining. Set
`OWL_LESSON_FALLBACK=false` to restore pack-only lesson mode. The fallback is
lesson-only: exam generation and authoritative grading must use pack materials
and their source refs, never the lesson fallback. `scope` is `null` on the
corpus answer path.

The lesson prompt has two labelled sections: "Lesson notes (this department)"
and "Set-text excerpts (outside this department)". A mixed answer must cite at
least one material and at least one book chunk; a pack-only or corpus-only
answer must cite its own space.

### `GET /v1/subjects`

Returns the published subject packs the server can serve. A draft, broken or
unreadable pack is skipped, never served; a host with no packs returns an empty
list. The server loads and validates packs once at startup, so this route is a
read of the in-process summary and does not touch the corpus. Subjects are
returned sorted by subject key.

Response `200`:

```json
{
  "subjects": [
    {
      "subject": "dada",
      "title": "Defence Against the Dark Arts",
      "tier": "owl",
      "version": "1.0.0",
      "status": "published",
      "built_at": "2026-11-08T14:48:30Z",
      "fingerprint": "e7139cbcc23eaa5c",
      "topics": ["dark-arts", "dark-creatures", "defensive-magic", "dueling"],
      "concepts": 21,
      "materials": 25
    }
  ],
  "lesson": true,
  "lesson_subject": "dada",
  "lesson_subjects": ["charms", "dada"],
  "lesson_fallback": true,
  "persona": true,
  "persona_subject": "dada",
  "persona_subjects": ["charms", "dada", "herbology", "potions", "transfiguration"]
}
```

`lesson` is true only when lesson mode is enabled, a selector loaded, and the
default API subject (`OWL_PERSONA_SUBJECT`) is among the selector's subjects.
`lesson_subject` names that subject when `lesson` is true, so the frontend can
scope the mode to the right venue. `lesson_subjects` lists every subject with a
loaded pack, so a venue can ask whether its own lesson mode is live.
`lesson_fallback` mirrors
`OWL_LESSON_FALLBACK`, so the room copy can say whether outside-the-notes
questions are answered from the set texts or refused. `persona` mirrors
`OWL_PERSONA`, so the frontend can stop hardcoding whether the professor's voice
is live. `persona_subject` names the default subject (`OWL_PERSONA_SUBJECT`) when
`persona` is true. `persona_subjects` lists every registered card; a room for a
subject in that list uses its own professor, and a room outside it shows the
rehearsal copy instead of claiming a live professor.

### Exam serving

The exam room reads the published bank through four routes. A paper id is
`<subject>-<version>`, for example `dada-1.0.0` or `charms-1.0.0`. Nothing is
generated at request time: the server samples a stored bank, persists the
attempt, and grades it later. The banks are independent, so the Charms venue
requests `subject=charms` explicitly; the default remains `OWL_EXAM_SUBJECT`.

`GET /v1/exams?subject=dada&version=1.0.0` returns the published paper
descriptors. `subject` defaults to `OWL_EXAM_SUBJECT` and `version` to the
latest published bank; an unknown or unpublished bank returns an empty list.
Response `200`:

```json
[
  {
    "paper_id": "dada-1.0.0",
    "subject": "dada",
    "version": "1.0.0",
    "title": "Defence Against the Dark Arts",
    "question_count": 10,
    "mcq_count": 6,
    "short_answer_count": 4,
    "marks": 50,
    "duration_minutes": 60
  }
]
```

`POST /v1/exams/{paper_id}/attempts` samples six MCQ and four short answers,
shuffles the order, and persists the result. Each served MCQ carries the correct
option plus three random distractors in a shuffled order. Response `201` is the
attempt view; it never contains `correct_option_id`, the golden answer, the
rubric or evidence ids:

```json
{
  "attempt_id": "V1StGXR8_Z5jdHi6B-myT",
  "paper_id": "dada-1.0.0",
  "subject": "dada",
  "version": "1.0.0",
  "created_at": "2026-11-09T12:00:00Z",
  "marks": 50,
  "questions": [
    {
      "position": 0,
      "item_id": "dada-mcq-001",
      "kind": "mcq",
      "prompt": "Which counter-jinx ...?",
      "marks": 3,
      "options": [
        {"option_id": "a", "text": "..."},
        {"option_id": "b", "text": "..."},
        {"option_id": "c", "text": "..."},
        {"option_id": "d", "text": "..."}
      ]
    },
    {
      "position": 6,
      "item_id": "dada-short-001",
      "kind": "short_answer",
      "prompt": "Explain ...",
      "marks": 8,
      "options": []
    }
  ]
}
```

`GET /v1/attempts/{attempt_id}` returns the same persisted view, so a reload
does not reshuffle the options. An unknown attempt is `404`; an unknown or
unpublished paper is `404`; a host with no exam store returns `503` on the
attempt routes and an empty list from `GET /v1/exams`.

The attempt routes are scoped to the signed `owl_session` cookie. Another
session cannot fetch or grade an attempt even with its id: both routes return
`404` rather than confirming that it exists. Attempts created before #206 have
an empty session id and are `404` for every session. The cookie is issued when
absent, lasts 24 hours, and is not refreshed on every request, so the session
history window runs from first issue. Set `OWL_SESSION_SECRET` in production;
without it an API restart invalidates every anonymous session.

`GET /v1/attempts?subject=dada&limit=20` returns the graded attempts for the
current session, newest first, capped at 50. `subject` defaults to
`OWL_EXAM_SUBJECT`; `limit` is 1 to 50. The summary carries no answers, option
keys, golden answers, rubric or evidence:

```json
[
  {
    "attempt_id": "V1StGXR8_Z5jdHi6B-myT",
    "paper_id": "dada-1.0.0",
    "subject": "dada",
    "version": "1.0.0",
    "created_at": "2026-11-09T12:00:00Z",
    "graded_at": "2026-11-09T12:05:00Z",
    "total": 38,
    "max_marks": 50,
    "band": "A",
    "needs_review": false
  }
]
```

Ungraded attempts are excluded from the list; they remain available by id until
graded. A `needs_review` attempt appears with a null total and band. The frontend
history and noticeboard read this route, not localStorage.

`POST /v1/attempts/{attempt_id}/grade` submits the answers. Omitted questions
are left blank. An MCQ answer is an `option_id` from the served four; a short
answer is `answer_text`:

```json
{
  "answers": [
    {"item_id": "dada-mcq-001", "option_id": "b"},
    {"item_id": "dada-short-001", "answer_text": "The counter-jinx ..."}
  ]
}
```

MCQ marks are deterministic. All short answers in the attempt are judged in one
pinned-model call against the stored golden answer, rubric and evidence. The
response is `200`:

```json
{
  "attempt_id": "V1StGXR8_Z5jdHi6B-myT",
  "paper_id": "dada-1.0.0",
  "total": 38,
  "max_marks": 50,
  "band": "A",
  "needs_review": false,
  "graded_at": "2026-11-09T12:05:00Z",
  "questions": [
    {
      "item_id": "dada-mcq-001",
      "kind": "mcq",
      "marks_awarded": 3,
      "max_marks": 3,
      "correct": true,
      "correct_option_id": "b",
      "model_answer": "The text of the correct option",
      "criteria": [],
      "feedback": "Correct.",
      "evidence_ids": ["b4-c14-0006"]
    },
    {
      "item_id": "dada-short-001",
      "kind": "short_answer",
      "marks_awarded": 7,
      "max_marks": 8,
      "correct": null,
      "correct_option_id": null,
      "model_answer": "The counter-jinx ...",
      "criteria": [
        {"criterion_id": "correctness", "awarded": 4, "max_marks": 4, "reason": "..."},
        {"criterion_id": "completeness", "awarded": 3, "max_marks": 4, "reason": "..."}
      ],
      "feedback": "...",
      "evidence_ids": ["b4-c14-0006"]
    }
  ]
}
```

A repeated submission returns the stored grade and makes no second judge call.
An answer for an item outside the attempt, a duplicate item, an option id that
was not served, or the wrong answer shape for the question kind is `400`. A
malformed or incomplete judge response after its one retry sets
`needs_review` on the affected questions and leaves the total and band null; it
is never a silent zero. A missing judge configuration is `503`; a provider
failure is `502`.

Attempt limits are per session: three per day anonymous, five per day
signed-in, plus a separate nine-per-day per-IP cap. Over a cap is `429` with
`Retry-After`. The signed-in path is reserved for auth (#35); the route
currently admits everyone as anonymous. The exam limiter is separate from the
chat limiter, so a chat budget or chat rate limit does not take exam serving
down.

## Errors

| Status | Shape | When |
|---|---|---|
| `422` | FastAPI validation detail | malformed request |
| `400` | `{"detail": "lesson mode is not enabled"}` | `mode=lesson` while `OWL_LESSON_MODE` is off or no pack loaded |
| `429` | `{"error": "rate limited", "reason": "...", "retry_after": n}` | minute, day or concurrency limit |
| `503` | `{"error": "chat temporarily unavailable", "reason": "..."}` | daily token budget or degraded mode |
| `502` | `{"detail": "model provider unavailable"}` | normalized provider failure on `/ask` |
| `504` | `{"error": "deadline exceeded", "request_id": "..."}` | `/ask` exceeded `OWL_ASK_TIMEOUT_S` |

`429` and `503` carry `Retry-After`. Every response carries `X-Request-ID`.

`/ask` has a deadline (`OWL_ASK_TIMEOUT_S`, default 30s). `/ask/stream` is not
bounded, because a legitimate stream can outlive the deadline.

## Session, CORS and limits

- The API issues a signed `owl_session` cookie: HttpOnly, `SameSite=None` when
  secure and `Lax` otherwise, 24 hours.
- CORS allows the configured origins and the configured origin regex, with
  credentials. It allows `GET` and `POST` and exposes `X-Request-ID` and
  `Retry-After`.
- Default chat limits: 10 messages per minute, 100 per day, 2 concurrent, plus a
  100/day per-IP cap and a 200k daily token budget. The counters live in the one
  API process and reset on restart.
- Exam attempts have their own per-session daily cap: 3 anonymous, 5 signed-in
  (reserved for #35), plus a 9/day per-IP cap. They are counted by the exam
  limiter, not the chat limiter.
- Corpus-only answers use an exact answer cache. Practice, feedback, meta,
  personal and lesson are never cached. The cache scope includes the lore pack
  version and, when lesson mode is on, the pack fingerprints, selector settings
  and the lesson fallback setting.
- The lore pack is loaded from `OWL_LORE_PATH` (a Markdown directory or a JSONL
  file). Absent means the answer path stays book-only.

## Planned versioned surface

These routes are not built yet. The shape is the contract for the next frontend steps: the doors, the exam
room and the records.

| Method | Path | Status | Purpose |
|---|---|---|---|
| `GET` | `/v1/persona` | planned | persona summary: name, subject, school, boundaries |
| `POST` | `/v1/chat` | planned alias of `/ask` | one-shot grounded answer |
| `POST` | `/v1/chat/stream` | planned alias of `/ask/stream` | SSE chat |

The earlier planned `GET /v1/exams/{paper_id}` shape is superseded: a served
paper is now an attempt, sampled and persisted by
`POST /v1/exams/{paper_id}/attempts`, so the client never receives the whole
bank or the MCQ key.

The chat request gains a `subject` field, default `"dada"`, validated against the
subject taxonomy. An unsupported subject returns `422`. The cache scope includes
the subject and pack version.

## Design rules

- Split by purpose, not by subject. A subject is request data; the exam bank and
  grading are separate resources.
- Keep chat intents internal. `mode` is a request hint, not a route.
- Split by transport: JSON one-shot and SSE stream.
- Give exams and grading their own limits and auth. They are not chat.
- Version before per-subject chat and exam attempts ship. Keep `/ask` as an
  alias for one release, then deprecate it.

## Versioning and migration

1. Add `/v1/chat` and `/v1/chat/stream` as aliases of the current handlers.
2. Add the `subject` field with a `"dada"` default.
3. Announce `/ask` and `/ask/stream` as deprecated.
4. Remove the unversioned routes after the academy frontend points at `/v1`.
