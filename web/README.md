# O.W.L. Online — frontend

The Ashcombe Academy site: the gate, the cloister of five doors, and the
study venues. React + Vite + TypeScript, deployed as a static site on
Cloudflare Pages. The API stays separate; `app/api/static/index.html` remains
the raw test page and is not part of this build.

## Layout

| Path | What it is |
|---|---|
| `src/data/subjects.ts` | The five departments: URL slug, API subject key, professor, accent, crest, status. The static status is the product open/soon decision; the pack version and lesson/persona flags come from `GET /v1/subjects`. |
| `src/api/subjects.ts` | Live client for `GET /v1/subjects`; the venue merges the response into the static presentation metadata. |
| `src/api/chat.ts` | Live client for `POST /ask/stream` (SSE: mode/token/reset/final/error); sends `mode=lesson` for the DADA venue when the API reports it. |
| `src/api/exams.ts` | Live client for the served exam bank: paper descriptors, attempt creation and grading; the API can return the same persisted attempt by id. The browser never sees the MCQ key before the grade response. |
| `src/api/results.ts` | `ResultsStore` interface; the localStorage implementation is provisional until server-side attempt history exists. |
| `src/pages/` | Front gate, about page, cloister (doors + noticeboard), venue (chat, exam room and your-papers tabs). |
| `src/components/` | Door, chat panel, professor silhouette, crest, colonnade backdrop, exam panel, band seal, results card, band strip, history panel, noticeboard, site footer. |
| `src/styles/base.css` | The theme: dark warm base, gold chrome, `--accent` per subject. |

## Run locally

    npm install
    npm run dev

The dev server is pinned to port 5500 because that is already in the API's
default CORS allowlist (`OWL_CORS_ORIGINS`). With `.env.development` pointing
at `http://localhost:8000`, run the API alongside:

    OWL_PROVIDER=openrouter OWL_LESSON_MODE=true OWL_PERSONA=true \
      uv run uvicorn app.main:app --reload

The venue fetches `GET /v1/subjects`; with `OWL_LESSON_MODE=true` the DADA room
sends `mode=lesson`, and with `OWL_PERSONA=true` the professor copy goes live.
Without the flags the venue falls back to corpus answers and rehearsal copy. The
exam room uses the served bank at `/v1/exams`; it needs the imported
`data/exams/exams.db` (`uv run python scripts/import_exam_bank.py --subject dada`)
and records results on this device until auth (#35).

## Deploy (Cloudflare Pages)

- Node 18 or newer (Vite 6 requirement); Pages defaults to a compatible runtime.
- Build command: `npm --prefix web run build` (root) or `npm run build` with
  root directory set to `web`.
- Output directory: `web/dist`.
- Environment variable: `VITE_OWL_API_BASE=https://api.monitus.org`.
- SPA fallback: `public/_redirects` serves `index.html` for deep links.
- CORS: the API already allows any `https://*.pages.dev` origin (including
  deploy previews) with credentials, via `OWL_CORS_ORIGIN_REGEX`.

## Status and honesty rules

- One subject is real (Defence Against the Dark Arts, chat only). The other
  four doors lead to "classroom being furnished" — no invented professors or
  content.
- The static subject list decides which departments are open. The persona flag
  (`OWL_PERSONA`) and lesson flag (`OWL_LESSON_MODE`) are read from
  `GET /v1/subjects`; a statically open department with no pack stays on corpus
  chat with a note, and a statically "soon" department stays furnished. With the
  flags off the copy addresses the professor without claiming he authored a live
  reply.
- Exam papers come from the published bank. The server samples the paper,
  keeps the MCQ key, scores objective answers by code and judges short answers
  against the stored rubric. Marks are a practice result, not an official
  O.W.L. record; the UI labels them as such on every screen of the flow,
  including the history and noticeboard.
- Best-so-far and paper history are device-local and provisional until auth
  (#35) and server history exist; unreadable storage says so instead of
  claiming the drawer is empty.
- Bands follow the canon two-tier split in colour: O/E/A pass, P/D/T fail.
- Model output renders as plain text, never HTML.
