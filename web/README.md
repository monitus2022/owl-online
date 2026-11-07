# O.W.L. Online — frontend

The Ashcombe Academy site: the gate, the cloister of five doors, and the
study venues. React + Vite + TypeScript, deployed as a static site on
Cloudflare Pages. The API stays separate; `app/api/static/index.html` remains
the raw test page and is not part of this build.

## Layout

| Path | What it is |
|---|---|
| `src/data/subjects.ts` | The five departments: slug, professor, accent, crest, personaState, status. Stand-in for `GET /v1/subjects`. |
| `src/api/chat.ts` | Live client for `POST /ask/stream` (SSE: mode/token/reset/final/error). |
| `src/api/exams.ts` | `ExamClient` interface mirroring the planned `/v1/exams` contract, plus `MockExamClient` with a demo DADA bank. |
| `src/api/results.ts` | `ResultsStore` interface; the localStorage implementation is provisional until server-side attempt history exists. |
| `src/pages/` | Front gate, cloister (doors + noticeboard), venue (chat, exam room and your-papers tabs). |
| `src/components/` | Door, chat panel, professor silhouette, crest, colonnade backdrop, exam panel, band seal, results card, band strip, history panel, noticeboard, site footer. |
| `src/styles/base.css` | The theme: dark warm base, gold chrome, `--accent` per subject. |

## Run locally

    npm install
    npm run dev

The dev server is pinned to port 5500 because that is already in the API's
default CORS allowlist (`OWL_CORS_ORIGINS`). With `.env.development` pointing
at `http://localhost:8000`, run the API alongside:

    OWL_PROVIDER=openrouter uv run uvicorn app.main:app --reload

Chat hits the real API (start the dev server without `OWL_PERSONA` set for
plain answers, or with it for the professor). The exam room is the mock.

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
- The persona flag (`OWL_PERSONA`) is off on the served host, so every chat
  affordance addresses the professor while the copy never claims he authored
  a live reply; `personaState` in `subjects.ts` is the single switch for
  restoring the professor voice wording when the flag ships.
- Exam papers, marks and bands are a demo until the exam bank (#38, #42)
  ships; the UI labels them as such and must keep doing so, on every screen
  of the flow including the history and noticeboard.
- Best-so-far and paper history are device-local and provisional until auth
  (#35) and server history exist; unreadable storage says so instead of
  claiming the drawer is empty.
- Bands follow the canon two-tier split in colour: O/E/A pass, P/D/T fail.
- Model output renders as plain text, never HTML.
