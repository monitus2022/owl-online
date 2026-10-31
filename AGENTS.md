# AGENTS.md

O.W.L. Online - a grounded, agentic RAG application. Read this before making changes.

## What this project is

A retrieval-augmented question-answering engine with three modes: revision chat, exam generation, and grading. The project's point is the evaluation discipline and the full-stack agent, not the corpus.

## Commands

Provisional until the code layout exists; update these as the project takes shape.

- Install: `uv sync`
- Run API: `uvicorn app.main:app --reload`
- Tests: `pytest`
- Eval gate: `pytest eval/`

## Verification (required)

- Run the eval gate before considering a change done.
- Do not regress retrieval or faithfulness beyond the noise band.
- Do not merge a change that fails the eval gate.

## Architecture

Target layout:

- `src/` - ingest, index, retrieve, rerank, generate
- `providers/` - model adapters (Bedrock, OpenRouter)
- `agent/` - LangGraph graph, nodes, state
- `api/` - FastAPI + SSE
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
