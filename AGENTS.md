# AGENTS.md

O.W.L. Online — a grounded, agentic RAG application. Read this before making changes.

## Commands

- Install: `uv sync`
- Run API: `uvicorn app.main:app --reload`
- Tests: `pytest`
- Eval gate: `pytest eval/`

## Verification (required)

- Run the eval gate before considering a change done.
- Do not regress retrieval or faithfulness beyond the noise band.

## Architecture

- `src/` — ingest, index, retrieve, rerank, generate
- `providers/` — model adapters (Bedrock, OpenRouter)
- `agent/` — LangGraph graph, nodes, state
- `api/` — FastAPI + SSE
- `eval/` — harness, gold set, thresholds
- Every model call goes through an adapter; the provider is a config value.

## Conventions

- Pin model slugs, chunk params, `top_k`, `rrf_k` in the repro manifest.
- Cache embeddings, rerank, generation, and judge outputs by (model, input).
- The judge must be a different family from the generator.

## Do not

- Commit the copyrighted corpus — keep it out of git.
- Render model output as HTML.
- Put secrets in the image or config; use environment variables.
