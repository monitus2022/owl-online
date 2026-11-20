# O.W.L. Online — frontend

The Ashcombe Academy site: the gate, the cloister of five doors, and the
study venues. React + Vite + TypeScript, deployed as a static site on
Cloudflare Pages. The API stays separate; the API host serves only the API and
`GET /` is a small JSON descriptor, not a chat page.

## Layout

| Path | What it is |
|---|---|
| `src/data/subjects.ts` | The five departments: URL slug, API subject key, professor, accent, crest, status, and the curated starter prompts. The static status is the product open/soon decision; the pack version and lesson/persona flags come from `GET /v1/subjects`. |
| `src/data/student.ts` | The student's display name: `owl.student.name` in `localStorage`, validation matching the API field, and the `useSyncExternalStore` hook that the welcome, chat and footer share. |
| `src/data/sources.ts` | Citation presentation: strips inline citation brackets from the answer prose, builds the readable `Sources` row (material breadcrumb, `Book N, Chapter M`, lore, persona note, policy), and groups the exact ids for the `Source details` disclosure. |
| `src/api/subjects.ts` | Live client for `GET /v1/subjects`; the venue merges the response into the static presentation metadata. |
| `src/api/chat.ts` | Live client for `POST /v1/chat/stream` (SSE: mode/token/reset/final/error); sends `mode=lesson` for a venue whose subject is in `lesson_subjects` when the API reports it, and sends the venue's anonymous `thread_id` and the student's name. Citation rendering lives in `src/components/SourcePanel.tsx` and `src/data/sources.ts`. |
| `src/api/materials.ts` | Live client for `GET /v1/materials/{subject}/{material_id}`; returns the reviewed pack note and book locators behind a lesson source, never the corpus text. |
| `src/api/exams.ts` | Live client for the served exam bank: paper descriptors, attempt creation, grading and discarding an ungraded attempt; the API can return the same persisted attempt by id. The browser never sees the MCQ key before the grade response. |
| `src/api/results.ts` | `ResultsStore` interface; `HttpResultsStore` reads the session-scoped `GET /v1/attempts` history and clears the session's attempts. The server is the source of truth; records are provisional until #35. |
| `src/pages/` | The front gate (also the Keeper's first-run name gate), about page, cloister (doors + noticeboard), venue (chat, exam room and your-papers tabs). |
| `src/components/` | Academy front and facade, door, chat panel, source panel, professor silhouette, crest, colonnade backdrop, exam panel, band seal, results card, band strip, history panel, noticeboard, site footer. |
| `src/styles/base.css` | The theme: dark warm base, gold chrome, `--accent` per subject. |

## Run locally

    npm install
    npm run dev

The dev server is pinned to port 5500 because that is already in the API's
default CORS allowlist (`OWL_CORS_ORIGINS`). With `.env.development` pointing
at `http://localhost:8000`, run the API alongside:

    OWL_PROVIDER=openrouter OWL_LESSON_MODE=true OWL_PERSONA=true \
      uv run uvicorn app.main:app --reload

The chat offers curated starter chips on the first turn. The list is
`startersFor` in `src/data/subjects.ts`; the off state omits the identity and
exam prompts, and `tests/test_presets.py` pins the strings and their routes.

Each venue keeps one anonymous conversation per browser tab. `ChatPanel` creates
a `thread_id` on first use, stores it under `owl-thread-<subject>` in
`sessionStorage`, and sends it on every stream request. A reload keeps the
thread; closing the tab starts a new one. No account is involved, and the API
holds the thread in process memory only. Threaded prompts include a bounded
recent-conversation block so the model can resolve follow-ups and comparisons
(except the experimental multi-book path).

The first visit is the front gate itself: the facade, the school name and the
promise, with the Keeper's ledger as the name form (#288, #299). The name is
required, validated in `src/data/student.ts` (letters, spaces, apostrophes,
hyphens and full stops, 40 characters at most), and kept in `localStorage` under
`owl.student.name`; `/about` and `/privacy` remain reachable before naming. The
name is sent as `student_name` on every chat request so the professor can
address the student, and the API includes it in the answer-cache scope. The
footer's "Change the name" control clears the value and returns to the gate.
The API never stores the name.

Chat answers keep the grounding visible without showing machine ids in the
prose. Inline citation brackets are stripped at render time, the `Sources` row
uses the material breadcrumb (for example `Dark creatures · Boggarts ·
Counter`) and one chip per cited chapter (`Book 3, Chapter 7`), and the exact
material ids, book chunk ids and typed citations stay under a collapsed
`Source details` disclosure. A material chip is a button that fetches the
reviewed pack note from `GET /v1/materials/{subject}/{material_id}` and shows
its authored text with the inline grounding refs removed and the same refs as
book locators plus exact chunk ids; a book chip stays a locator and never
opens novel text. The API payload, verification and typed-citation contract are
unchanged (#290, #294, #301).

The venue fetches `GET /v1/subjects`; with `OWL_LESSON_MODE=true` each open room
whose subject is in `lesson_subjects` sends `mode=lesson`, and with
`OWL_PERSONA=true` each subject in `persona_subjects` uses its own professor
copy. A room outside those lists keeps rehearsal or neutral copy.
Without the flags the venue falls back to corpus answers and rehearsal copy. The
exam room uses the served bank at `/v1/exams`; it needs the imported
`data/exams/exams.db` (`uv run python scripts/import_exam_bank.py --subject <subject>`
for each of `dada`, `charms`, `potions`, `transfiguration` and `herbology`) and records results in the signed browser session until
auth (#35). Each venue requests its own subject, so the Charms room serves
`charms-1.0.0` without changing the API default.

## Deploy (Cloudflare Pages)

- Node 18 or newer (Vite 6 requirement); Pages defaults to a compatible runtime.
- Build command: `npm --prefix web run build` (root) or `npm run build` with
  root directory set to `web`.
- Output directory: `web/dist`.
- Environment variable: `VITE_OWL_API_BASE=https://api.monitus.org`.
- Operator evidence: run the API with `OWL_DEV_EVIDENCE=true` next to the Vite
  dev server, and a chat answer carries a collapsed "Evidence inspector" with
  the retrieved chunks, scores, prompt fingerprint and verification state. The
  production build strips it, and CI fails if the inspector string appears in
  `dist/`. Never enable the flag in deployment.
- SPA fallback: `public/_redirects` serves `index.html` for deep links.
- CORS: the API already allows any `https://*.pages.dev` origin (including
  deploy previews) with credentials, via `OWL_CORS_ORIGIN_REGEX`.

## Status and honesty rules

- All five subjects are real rooms: Defence Against the Dark Arts, Charms,
  Potions, Transfiguration and Herbology each have a published pack, exam bank
  and live professor card.
- The static subject list decides which departments are open. The persona flag
  (`OWL_PERSONA`) and lesson flag (`OWL_LESSON_MODE`) are read from
  `GET /v1/subjects`; a statically open department with no pack stays on corpus
  chat with a note, and a statically "soon" department stays furnished. With the
  flags off the copy addresses the professor without claiming he authored a live
  reply.
- A lesson answer labels its evidence: `in_pack` and `mixed` answers say they are
  composed and carry the source caveat: the listed sources locate the notes,
  they are not a sentence-level check. `off_pack` answers label the set-text
  tier. The measured support rate stays published instead of being implied.
- Exam papers come from the published bank. The server samples the paper,
  keeps the MCQ key, scores objective answers by code and judges short answers
  against the stored rubric. Marks are a practice result, not an official
  O.W.L. record; the UI labels them as such on every screen of the flow,
  including the history and noticeboard.
- Best-so-far and paper history are session-scoped and provisional until auth
  (#35); unreadable history says so instead of claiming the drawer is empty.
- Existing local-storage result records are not migrated; the session history
  starts from the server.
- Bands follow the canon two-tier split in colour: O/E/A pass, P/D/T fail.
- Model output renders as plain text, never HTML.
