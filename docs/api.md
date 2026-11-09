# API

The served surface is FastAPI. The current contract is unversioned except for
`GET /v1/subjects`; the remaining planned `/v1` aliases are listed below. The
academy frontend has already split into its own static build (`web/`, served on
Cloudflare Pages) and calls the unversioned chat routes today, relying on the
CORS origin regex and the session cookie; the versioned aliases gate the next
steps - the per-subject chat field, the exam endpoints, and any custom domain
that must pin its CORS origin.

Base URL: the deployment origin, for example `https://api.monitus.org`.

## Current endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | liveness; returns `{"status": "ok"}` |
| `GET` | `/` | the static chat page |
| `GET` | `/v1/subjects` | published subject packs plus the `lesson`, `lesson_subject`, `lesson_fallback` and `persona` flags |
| `POST` | `/ask` | one-shot grounded answer |
| `POST` | `/ask/stream` | chat over server-sent events |

### `POST /ask`

Request:

```json
{"question": "Who teaches Defense Against the Dark Arts in book 4?"}
```

`question` is trimmed, must be 1 to 1000 characters, and must not be blank.

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
  "mode": "auto",
  "student_answer": null
}
```

`mode` is `auto`, `answer`, `practice`, `feedback` or `lesson`. `student_answer`
is at most 6000 characters and is only valid with `auto` or `feedback`. When the
persona is on, the server may also route to `meta` or `personal`; those are not
accepted as request modes. `lesson` is explicit only, never inferred, and is
rejected with `400` unless `OWL_LESSON_MODE` is on and a published pack loaded.
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
built or stored. The subject is `OWL_LORE_SUBJECT` until the request `subject`
field ships. Lesson answers are never cached.

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
| `abstained` | Neither the pack nor the corpus has evidence, including a pack-only partial whose uncovered terms have no corpus evidence. |

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
  "lesson_fallback": true,
  "persona": true
}
```

`lesson` is true only when lesson mode is enabled, a selector loaded, and the
configured subject (`OWL_LORE_SUBJECT`) is among the selector's subjects.
`lesson_subject` names that subject when `lesson` is true, so the frontend can
scope the mode to the right venue. `lesson_fallback` mirrors
`OWL_LESSON_FALLBACK`, so the room copy can say whether outside-the-notes
questions are answered from the set texts or refused. `persona` mirrors
`OWL_PERSONA`, so the frontend can stop hardcoding whether the professor's voice
is live.

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
| `GET` | `/v1/exams` | planned | papers, filtered by subject and version |
| `GET` | `/v1/exams/{paper_id}` | planned | questions, no answers |
| `POST` | `/v1/exams/{paper_id}/attempts` | planned | start an attempt |
| `GET` | `/v1/attempts/{attempt_id}` | planned | attempt state |
| `POST` | `/v1/attempts/{attempt_id}/grade` | planned | deterministic objective scoring plus the pinned rubric judge |

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
