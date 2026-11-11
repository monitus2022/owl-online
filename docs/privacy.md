# Privacy and retention

This is the product privacy and retention note (#180). It describes what the
served application stores, for how long, which providers see a request, and
what a user can do before accounts land (#35). It is not formal legal advice
and not a data processing agreement.

## What is stored

| Data | Where | Contents | Prompt or answer text |
|---|---|---|---|
| Chat transcript | Browser tab only | The messages in the open tab | Yes, in the browser; not persisted as a chat record |
| Chat thread | Process memory (LangGraph checkpointer) | Recent messages, rolling summary, last entity/person/place, last mode and pending clarify for an opt-in anonymous `thread_id` | Yes, question and answer text in process memory; no account, no disk write, cleared on restart |
| Answer cache | Process memory | Corpus-only answers, keyed by question, model and index scope; default 256 entries and 1 hour TTL (configurable), cleared on restart | The cached answer text is in memory; it is not a chat record and is not session-keyed |
| Usage log | Process log | Session id, intent, model, cache flag, token counts, cost, latency | No |
| Trace | Process log and optional capped file | Request id, span names, timings, counts, retrieved chunk and lore ids, prompt hash and length | No |
| Exam attempt | SQLite `attempts` and `attempt_questions` | Paper, questions served, answers, grade, session id, timestamps | The attempt stores the served question prompts and the student's answers; it does not store chat prompts |
| Judge cache | `data/exam_judge_cache.jsonl` (optional) | Bank/item/rubric/judge pins, answer hash, raw response hash, grade and feedback | The raw answer is not stored; the feedback may quote it |
| Session cookie | Browser | `owl_session`, a signed random id | No |

A chat thread is keyed only by the client-supplied `thread_id`. It is a bearer
key, not an identity: anyone who knows the id can continue that thread while the
API process lives. The frontend keeps the id in `sessionStorage` and never puts
it in a URL.

The trace sink caps its optional file at 20 MB and keeps one rotated file. The
usage log line is the one in `app/main.py`; it never includes the question or
the answer. The trace emits prompt hashes and lengths and, on the router span,
`question_chars`; not the text. The exact answer cache is in process memory and
disappears on restart; it is not a chat record and has no per-session key. When
memory is enabled, a request with a `thread_id` is not cached, because the same
question can mean different things after different turns; with
`OWL_MEMORY_ENABLED=false` the request is stateless and cacheable. The judge
cache is an operator-managed file keyed by bank, item and answer hash; it
does not store the raw answer, but its feedback may quote it.

## Retention

| Data | Retention |
|---|---|
| Chat transcript | Until the tab closes or the page reloads; the API keeps no chat record |
| Chat thread | Process memory only; until the API restarts. A new thread id starts a separate thread |
| Answer cache | Up to 1 hour (TTL) or 256 entries, whichever comes first; cleared on restart |
| Judge cache | Operator-managed; delete `data/exam_judge_cache.jsonl` and restart the API to clear the in-process copy |
| Session cookie | 24 hours (`max_age=86400`); the next request gets a new session id |
| Usage log | Host log rotation |
| Trace | Process log rotation; the optional file caps at 20 MB with one rotation |
| Exam attempt | Until the session deletes it or the operator prunes it; the documented manual window is 90 days |

The anonymous delete path is `DELETE /v1/attempts`, which deletes every attempt
owned by the current session. It does not clear the in-memory answer cache, the
process-local chat threads or the operator-managed judge cache; all three are
process/operator scoped. A thread remains in process memory until the API
restarts; a client that stops using its id simply stops adding turns. There is
no read or delete route because the server keeps no durable chat record. The
operator retention path is:

```text
uv run python scripts/prune_attempts.py --days 90 --dry-run
uv run python scripts/prune_attempts.py --days 90
```

The script deletes attempts whose `created_at` is older than the window and
relies on the `attempt_questions` foreign-key cascade. It never touches bank
items or published banks. Clearing cookies starts a new session; it does not
delete the old attempts, so a user who wants them gone should call the delete
route first.

## Model providers

Prompts and the retrieved excerpts go to the configured provider:

- OpenRouter for the open-weight models;
- Amazon Bedrock in the deployed region for the Bedrock adapter.

The deployment region bans OpenAI, Anthropic and Google models, and
`app/providers/policy.py` checks every slug before use. The project does not
train models on request data. The provider processes the request under its own
terms; a formal no-training guarantee needs the provider's agreement, not this
note.

## Cookies, CORS and CSRF

The only cookie is `owl_session`. The middleware sets it with:

- `httponly=True`;
- `samesite="none"` with `secure=True` when the request is HTTPS (the Pages
  frontend is cross-origin), otherwise `samesite="lax"` and `secure=False` in
  local HTTP development;
- `max_age=86400`.

CORS allows the configured origins and the project's Pages origin with its
preview subdomains (`owl-online.pages.dev`), with credentials; an unrelated
`*.pages.dev` origin is rejected. The state-changing endpoints are JSON
`POST`/`DELETE` calls, which trigger a CORS preflight; a browser from an origin
outside the allowlist cannot read the response or send the credentialed request.
Attempt ids are random and session-owned (`owned_attempt` returns 404 for
another session), so a forged grade request cannot target an attempt it does not
own. The chat endpoints are unauthenticated by design but rate-limited per
session and per IP.

Residual CSRF risk: the cookie is `SameSite=None` on HTTPS, so a cross-site
request can carry it. The JSON preflight and the scoped origin allowlist are the
barrier, and the attempt ids are unguessable. A dedicated CSRF token is not
needed for the current anonymous surface; revisit it when accounts and
state-changing account routes land in #35.

## User rights before accounts

- Export: `GET /v1/attempts` returns the graded attempts for the current
  session, newest first.
- Delete: `DELETE /v1/attempts` deletes the current session's attempts.
- Access and correction: session-scoped; there is no account to inspect or
  correct until #35.
- A per-user delete/export path, cross-device history and account deletion are
  defined with auth in #35.

## Verification

`tests/test_privacy.py` runs a request with a unique prompt and answer, captures
the log and trace output, and asserts the text does not appear. It also checks
the cookie attributes and the session-scoped delete/prune behaviour.

## Follow-ups

- #35: accounts, per-user history, account deletion and export.
- #33: dashboards must not add prompt or answer text to the metrics surface.
- #181: the versioned API contract must keep the same delete/export semantics.

## Out of scope

- formal legal advice or a full data processing agreement;
- account deletion UI before #35;
- data residency changes.
