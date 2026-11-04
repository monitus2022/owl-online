# AGENTS.md

O.W.L. Online - a grounded, agentic RAG application. Read this before making changes.

## What this project is

A retrieval-augmented question-answering engine with three modes: revision chat, exam generation, and grading. The project's point is the evaluation discipline and the full-stack agent, not the corpus.

## Commands

Provisional until the code layout exists; update these as the project takes shape.

- Install: `uv sync` (installs the dev, ingest and agent groups)
- Run API: `uvicorn app.main:app --reload`
- Tests: `pytest`
- Eval gate: `pytest eval/`

Dependencies are split by environment. `[project] dependencies` is what the
served API needs; `ingest` (PDF parsing) and `agent` (V2 LangGraph, SSE) are
dependency groups, installed by default for dev. The runtime image installs base
only (`uv sync --no-default-groups`). chromadb's unused `kubernetes` and
`onnxruntime` are excluded in `[tool.uv]`, so they are absent in every
environment, dev included.

## Verification (required)

- Run the eval gate before considering a change done.
- After any run of `scripts/run_eval.py`, write a run record in `docs/runs/` before the change is done.
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

- `app/api/` - FastAPI HTTP surface (single-shot `/ask`; streaming is V2)
- `app/pipeline/` - ingest, index, retrieve (hybrid + rerank), generate
- `app/providers/` - model adapters (OpenRouter Llm; Bedrock reranker now; Bedrock Llm is V2)
- `app/agent/` - LangGraph graph, nodes, state (V2)
- `app/schemas.py` - domain data (`Chunk`)
- `app/config.py` - settings (env-based, `OWL_` prefix)
- `app/logging.py` - logging setup: one formatter, level from settings, per-request id
- `docs/architecture.md` - living diagrams (contracts, module deps, `/ask` flow); update when a contract, an adapter, or the top-level flow changes
- `docs/runs/` - one committed Markdown record per eval run, plus the template and index
- `eval/` - harness, gold set, thresholds

Every model call goes through an adapter; the provider is a config value.

## Model access

Only open-weight and Amazon models are callable (Bedrock in-region; OpenRouter). Do not propose OpenAI, Anthropic, or Google models. Verify each model with a probe before building on it.

## Conventions

- Pin model slugs, chunk params, `top_k`, `rrf_k` in the repro manifest.
- Cache embeddings, rerank, generation, and judge outputs by (model, input).
- The judge must be a different family from the generator.
- Reference the issue number in branch names, commits, and pull requests.
- Satisfy the ticket's `Done when:` criteria before closing it.

## Docs style

- Markdown uses headings, lists, tables, and code only. No bold or italic.

## Do not

- Commit the copyrighted corpus - keep it out of git.
- Render model output as HTML.
- Put secrets in the image or config; use environment variables.

## Review workflow

- Each ticket is reviewed by the read-only `reviewer` subagent before it is done.
- See `.opencode/agents/reviewer.md`.

## AI usage records

- When a ticket includes AI-drafted code, say so in the PR description (what was agent-written, what was human-written, and that the human reviewed it).
- Keep `README.md` "AI usage" accurate as agent involvement grows.
