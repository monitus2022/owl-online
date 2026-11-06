# API

The served surface is FastAPI. The current contract is unversioned; the planned
`/v1` aliases are listed below and will become the stable surface before the
frontend splits into its own repository.

Base URL: the deployment origin, for example `https://api.monitus.org`.

## Current endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | liveness; returns `{"status": "ok"}` |
| `GET` | `/` | the static chat page |
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
  "lore_citations": []
}
```

`citations` are book chunk ids. `lore_citations` are setting-entry ids in the
`[lore:<id>]` space. The two spaces are validated separately; an unknown id of
either kind is stripped from the text. `abstained` is true when there is no book
or lore evidence, the draft cites nothing, or the model refuses. The answer text
is always returned; an abstention is a `200`, not an error.

### `POST /ask/stream`

Request:

```json
{
  "question": "Who teaches Defense Against the Dark Arts in book 4?",
  "mode": "auto",
  "student_answer": null
}
```

`mode` is `auto`, `answer`, `practice` or `feedback`. `student_answer` is at most
6000 characters and is only valid with `auto` or `feedback`. When the persona is
on, the server may also route to `meta` or `personal`; those are not accepted as
request modes.

The response is `text/event-stream`. Events:

| Event | Data | When |
|---|---|---|
| `mode` | `{"mode": "answer"}` | after the router; can be `answer`, `practice`, `feedback`, `meta` or `personal` |
| `token` | `{"text": "..."}` | each streamed token |
| `reset` | `{}` or `{"reason": "retry"}` / `{"reason": "fallback"}` | clear the draft before a retry, a fallback, an error, or an abstained final |
| `final` | `answer`, `citations`, `lore_citations`, `abstained`, `needs_input`, `attempts`, `mode` | once, authoritative |
| `error` | `{"detail": "..."}` | terminal; always preceded by `reset` |

`final` is the authoritative payload. A client should replace the draft on
`reset` and render `final` when it arrives. Once the stream has started, a
provider failure is an `error` event, not an HTTP status.

## Errors

| Status | Shape | When |
|---|---|---|
| `422` | FastAPI validation detail | malformed request |
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
- Corpus-only answers use an exact answer cache. Practice, feedback, meta and
  personal are never cached. The cache scope includes the lore pack version.
- The lore pack is loaded from `OWL_LORE_PATH` (a Markdown directory or a JSONL
  file). Absent means the answer path stays book-only.

## Planned versioned surface

These routes are not built yet. The shape is the contract for the frontend split.

| Method | Path | Status | Purpose |
|---|---|---|---|
| `GET` | `/v1/persona` | planned | persona summary: name, subject, school, boundaries |
| `GET` | `/v1/subjects` | planned | available subjects and packs |
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
- Version before the frontend moves to its own repository. Keep `/ask` as an
  alias for one release, then deprecate it.

## Versioning and migration

1. Add `/v1/chat` and `/v1/chat/stream` as aliases of the current handlers.
2. Add the `subject` field with a `"dada"` default.
3. Announce `/ask` and `/ask/stream` as deprecated.
4. Remove the unversioned routes after the frontend has moved.
