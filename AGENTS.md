# AGENTS.md

O.W.L. Online - a grounded, agentic RAG application. Read this before making changes.

## What this project is

A retrieval-augmented question-answering engine with two surfaces: a chat that
answers, sets practice and gives formative feedback, and a static exam bank with
offline generation and hybrid grading. All five O.W.L. packs are published at
1.0.0, and all five subject exam banks are published at 1.0.0; the professor
persona is live behind `OWL_PERSONA`; lesson mode is live behind `OWL_LESSON_MODE` with a
labelled corpus fallback when the pack is thin; hybrid grading is built, the bank
eval and judge calibration are recorded, and served papers are live; the
router applies policy, closed-fact and teaching gates before retrieval, and
answers carry typed `policy:script:`, `persona:`, `lore:` and `lesson:`
citations with a cross-type check; attempt history is session-scoped, and
per-user history waits on auth (#35). The
project's point is the evaluation discipline and the full-stack agent, not the
corpus.

## Commands

Run these from the repository root.

- Install: `uv sync` (installs the dev and ingest groups; LangGraph and SSE are base dependencies)
- Run API: `uvicorn app.main:app --reload`
- Frontend install: `npm --prefix web ci`
- Frontend build: `npm --prefix web run build` (type-checks too; matches the Pages build and the `web` CI job)
- Browser E2E: `npm --prefix e2e test` (after `npm ci --prefix web`, `npm ci --prefix e2e` and `npx --prefix e2e playwright install chromium`; runs the stub API and the Vite frontend)
- Tests: `pytest`
- Eval harness tests: `pytest eval/`
- Eval gate: `uv run python scripts/run_eval.py --check`

`ingest` (PDF parsing) is a dependency group, installed by default for dev.
LangGraph and sse-starlette are base dependencies because the served V2 API
imports them. The runtime image installs base only (`uv sync
--no-default-groups`).

## Verification (required)

- Run the eval gate before considering a change done.
- CI runs `uv run ruff check .`, `uv run pytest tests` and `uv run pytest eval/` on every pull request (`.github/workflows/eval.yml`). The `web` workflow runs `npm ci` and `npm run build` in `web/` on every pull request; pick its `build` check as required alongside `lint-and-tests` after the first green run. The `docker` workflow builds the API image on every pull request without pushing, so a broken Dockerfile cannot reach the deploy workflow. The live gate runs on the host before merge because the corpus is not in git.
- After any full run of `scripts/run_eval.py`, write a run record in `docs/runs/` before the change is done. `--check` gates an existing run and needs no record.
- Do not regress retrieval or faithfulness beyond the noise band.
- Do not merge a change that fails the eval gate.

## Run records

- Every finished eval run gets a committed Markdown record under `docs/runs/`.
- Copy the template from `docs/runs/README.md`; name the file `YYYY-MM-DD-<ticket>-<slug>.md`.
- Record the run id, configuration, retrieval, abstention and generation tables, the reading notes, and the printed summary verbatim.
- Add a row to the Runs table in `docs/runs/README.md` in the same commit.
- One record per run id. Timestamped CSVs stay local and gitignored; the record must stand alone without them.

## Architecture

Layout:

- `app/api/` - FastAPI HTTP surface (`/v1/chat`, `/v1/chat/stream` with deprecated `/ask` aliases, `/v1/subjects`, `/v1/metrics`, and the `/v1/exams` and `/v1/attempts` serving routes)
- `app/pipeline/` - ingest, index, retrieve (hybrid + rerank), generate; offline exam build is planned; `ingest/lexicon/` holds the hp-lexicon canon-index harvester (spike grammar and parsers plus the #126 discovery/fetch/harvest modules)
- `app/providers/` - model adapters (OpenRouter Llm; Bedrock reranker, embedder and Converse Llm)
- `app/agent/` - LangGraph chat graph, node functions, state (V2); the policy, closed-fact and teaching gates plus the typed citation routes; lesson mode is an explicit `mode=lesson` behind `OWL_LESSON_MODE`
- `app/knowledge/` - lore pack schema and selection; the canon-index resolver (`lexicon.py`, #127): agreement join, chunk-candidate resolution, integrity verification and review samples over the gitignored harvest artifacts; subject taxonomy, material packs and validation landed with #87 (PR #153); the DADA pack is published at 1.0.0 (25 materials, 21 concepts), Charms at 1.0.0 (50 materials, 49 concepts), Potions at 1.0.0 (34/34), Transfiguration at 1.0.0 (34/29) and Herbology at 1.0.0 (33/31); DADA feeds lesson mode through a derived in-memory material selector (#166); reference prefill and coverage maintenance remain on #128
- `app/storage/` - SQLite bank store (#189) plus attempt persistence, session ownership and grading records (#193/#206)
- `app/grading/` - built hybrid grader (#192): deterministic MCQ scoring, one-call LLM rubric judge for short answers, deterministic score bands; the bank eval and judge calibration are in `eval/exam/` (#191); served attempts are #193; the same grader serves all five banks (#213 pattern)
- `data/subjects/` - local subject packs; all five O.W.L. packs are published; source text stays out of git
- `app/schemas.py` - domain data (`Chunk`)
- `app/config.py` - settings (env-based, `OWL_` prefix)
- `app/logging.py` - logging setup: one formatter, level from settings, per-request id
- `docs/architecture.md` - living diagrams (contracts, module deps, chat flows, exam-bank boundary); update when a contract, an adapter, or the top-level flow changes
- `docs/workplan.md` - phase plan, ticket map, grading and memory decisions
- `docs/routing-contracts.md` - contract and authority routing plan (#216): policy, closed facts and teaching; gates, citation types and the residual measurement bar
- `docs/persona.md` and `docs/personas.md` - the DADA card and the four non-DADA cards; the TOML files under `config/` are the source of truth
- `docs/exams/` - bank blueprint, artifact rules, serving contract, published bank records, manifest snapshots and the DADA grading probe (#188-#193, #213)
- `docs/lexicon-canon-index.md` - plan of record for the hp-lexicon canon index (#125-#128); update it when a parse rule, an artifact contract or the source policy changes
- `docs/runs/` - one committed Markdown record per eval run, plus the template and index
- `eval/` - harness, gold set, thresholds; `eval/exam/` holds the DADA bank evaluation and judge calibration (#191)
- `web/` - React + Vite academy frontend, deployed separately on Cloudflare Pages (docs/deploy.md); it calls the versioned contract in `docs/api.md` and never imports Python code
- `e2e/` - Playwright browser suite against the stub API and the Vite frontend; axe checks and the student loop (#179)
- `docs/load/` - committed stream load reports; the check is manual/release-only

Every model call goes through an adapter; the provider is a config value.

Chat has three intents: answer, practice and feedback. Practice and feedback are
ephemeral and formative. The exam bank is a separate served surface: papers are
sampled from a bank that was generated offline, validated, versioned and stored.
Objective answers are scored deterministically; free-text answers are judged by a
pinned LLM against the stored rubric and evidence; totals and bands are
deterministic. Do not route formal exam generation or authoritative grading
through the chat graph.

Subject knowledge packs are the source of truth for exam generation and
pack-backed lesson content. Every material has source refs; every generated exam
question and pack-backed lesson section must cite a material and source ref. A
labelled off-pack lesson section cites set-text chunk ids instead. Exam
generation and authoritative grading never consume the off-pack fallback. Do not
generate exam or pack-backed lesson content from free model memory or from an
unvalidated pack.

Chat controls (#88) enforce per-session and per-IP minute, day and concurrency
caps through a signed session cookie, an exact cache for corpus-only answers, and
a daily token budget that degrades chat before it can exhaust the spend. The
counters live in the one API process and reset on restart.

## Model access

Only open-weight and Amazon models are callable (Bedrock in-region; OpenRouter).
The deployment region bans OpenAI, Anthropic and Google models outright, so
their open-weight releases (gpt-oss, Gemma) and proprietary models (Claude) are excluded too, even when
hosted on Bedrock or OpenRouter. The vendor is what matters, not the host. Every
model is checked by app/providers/policy.py before use. Verify each model with a
probe before building on it.

## Conventions

- Pin model slugs, chunk params, `top_k`, `rrf_k` in the repro manifest.
- Cache embeddings, rerank, generation, and judge outputs by (model, input).
- The judge must be a different family from the generator.
- Reference the issue number in branch names, commits, and pull requests.
- Satisfy the ticket's `Done when:` criteria before closing it.

## Docs style

- Markdown uses headings, lists, tables, and code only. No bold or italic.

## Do not

- Commit the copyrighted corpus - keep it out of git. Same for Lexicon pages
  and harvested rows (`data/lexicon/`): structure only, no site prose, ever.
- Render model output as HTML.
- Put secrets in the image or config; use environment variables.

## Review workflow

- Each ticket is reviewed by the read-only `reviewer` subagent before it is done.
- See `.opencode/agents/reviewer.md`.

## AI usage records

- When a ticket includes AI-drafted code, say so in the PR description (what was agent-written, what was human-written, and that the human reviewed it).
- Keep `README.md` "AI usage" accurate as agent involvement grows.
