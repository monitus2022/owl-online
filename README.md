# O.W.L. Online

A grounded, agentic RAG application - a revision tool that answers questions, runs conversational practice, and serves pre-generated exams with hybrid grading.

> Status: grounded chat, all five O.W.L. knowledge packs published at 1.0.0, the DADA, Charms, Potions, Transfiguration and Herbology exam banks published at 1.0.0, lesson mode live behind `OWL_LESSON_MODE`, and the professor persona live behind `OWL_PERSONA`. The academy frontend ships from `web/` on Cloudflare Pages, and the API is at https://api.monitus.org. Lesson answers cite reviewed materials and their book source refs; questions outside the pack fall back to labelled set-text answers. Each bank holds 25 MCQ and 25 short-answer items, hybrid grading is built, the DADA and Charms judge calibrations are recorded, the other three banks have published validation records, and served papers are live; result history is session-scoped until auth (#35). The router applies the policy, closed-fact and teaching gates before retrieval; answers carry typed `policy:script:`, `persona:`, `lore:` and `lesson:` citations with a deterministic cross-type check (#216-#220). Short-term conversation memory is live behind an opt-in `thread_id` (#30), with a bounded conversation block in the chat prompt (except the experimental multi-book path); the next product surface is accounts (#35). See [`docs/workplan.md`](docs/workplan.md), [`docs/api.md`](docs/api.md), [`web/README.md`](web/README.md) and the milestones.

---

## What it is

O.W.L. Online has two product surfaces on one retrieval core:

| Surface | What it does | State |
|---|---|---|
| Chat answer | Grounded Q&A with citations | live |
| Chat practice | On-demand grounded practice question | live |
| Chat feedback | Formative feedback and a provisional mark | live |
| Subject packs | Reviewed, source-grounded knowledge packs that feed lesson mode and exam generation | DADA, Charms, Potions, Transfiguration and Herbology 1.0.0 published |
| Exam bank | 25 MCQ + 25 short-answer banks sampled into 6 MCQ + 4 short-answer papers and graded by a hybrid scorer | all five subject banks 1.0.0 published; served attempts and hybrid grading built (#190-#193, #213, #228, #230, #231); session history built (#206); cross-device history after #35 |
| Lesson mode | Pack-grounded teaching answers with material and book citations, plus a labelled corpus fallback | live behind `OWL_LESSON_MODE` |
| Routing contracts | Policy, closed-fact and teaching gates, typed citations and the cross-type authority checker | live (#216-#220) |

Chat practice and feedback are ephemeral and formative. The exam bank is the
authoritative surface: papers are generated offline, validated, versioned and
stored. Objective answers are scored deterministically; free-text answers are
judged by a pinned LLM against the stored rubric and evidence snapshot; totals
and score bands are deterministic.

See [`docs/workplan.md`](docs/workplan.md) for the phase plan, ticket map and
grading decisions.

The exam bank is not a request-time generator. The bank is authored offline,
validated against the pack and the corpus, and stored with an evidence snapshot
on every item. A served attempt samples 6 MCQ and 4 short answers for 50 marks:
the server keeps the MCQ key, the client gets the correct option plus three
distractors, MCQ answers are scored by code, short answers go to a pinned judge
with the rubric and evidence, and the judge never writes the final total or band.
The exam room takes a served paper through `POST /v1/exams/{paper_id}/attempts`
and submits it for grading; result history is session-scoped until auth (#35).
Questions test the subject, not the plot; the scope rule is in
[`docs/exams/README.md`](docs/exams/README.md).

Exam generation reads from versioned subject knowledge packs: one grounded
material store per O.W.L. subject, with every material linked to a book chunk,
quote and text hash. A generated exam question or pack-backed lesson section
that cannot cite a pack material is rejected before publication. A labelled
off-pack lesson section cites set-text chunk ids instead; exam generation and
authoritative grading never consume that fallback. External references such as
the Harry Potter Lexicon are stored as attributed links for discovery and
cross-checking; they are not copied into the packs and are not the canonical
source.

Core exam content uses the seven novels. Rowling companion books and interviews
are optional further reading, not exam-gradable in the first version. Films,
games and fan works are excluded from the set texts.

Chat is the variable-cost surface. Messages are capped per session and per IP,
with a concurrency limit, an exact cache for repeated questions, per-request
usage and cost logs, and a daily token budget that degrades chat before it can
exhaust the spend.

The corpus is a single well-known work of fiction. The source text is not included (see Disclaimer). The point of the project is not the corpus - it is the evaluation discipline and the full-stack agent around it.

---

## Why it exists

A portfolio project that does the two hard things, then wraps them in a served application:

1. A retrieval core that works - hybrid (dense + BM25, fused with RRF) then rerank.
2. An evaluation harness that separates failures - retrieval scored on chunk ids, generation scored by a judge, plus a closed-book control and perturbation probes.

---

## Architecture

```mermaid
flowchart TD
  C["Client"] --> API["FastAPI + SSE"]
  API --> R["Router"]
  subgraph G["Chat agent"]
    R --> A["Answer"]
    R --> P["Practice"]
    R --> F["Feedback"]
    R --> L["Lesson"]
  end
  A --> RET["Retrieve"]
  P --> RET
  F --> RET
  L --> MAT[("Pack materials")]
  RET --> RR["Rerank"]
  RET --> VEC[("Vector store")]
  RET --> BM[("BM25")]
  RR --> RER["Rerank adapter"]
  A --> LLM["LLM adapter"]
  P --> LLM
  F --> LLM
  L --> LLM
  B["Offline exam builder"] --> RET
  B --> DB[("Exam DB")]
  API --> DB
  API --> SUB["/v1/subjects"]
  R -. trace .-> OBS["Observability"]
```

Every model call goes through an adapter, so the provider is a config value, not an architecture.

See [`docs/architecture.md`](docs/architecture.md) for the current contracts, module dependencies, and the `/ask` and `/ask/stream` request flows. The exam-bank pipeline is documented there as a separate served boundary, not as a chat intent.

---

## Run

```
uv sync
uv run python scripts/build_index.py                 # once: build the vector index
OWL_PROVIDER=openrouter uv run uvicorn app.main:app --reload
# or the Bedrock Converse path, using an in-region open-weight model:
OWL_PROVIDER=bedrock OWL_BEDROCK_LLM_MODEL=qwen.qwen3-32b-v1:0 \
  uv run uvicorn app.main:app --reload
```

Needs an `OWL_OPENROUTER_API_KEY` and an Ollama daemon for embeddings; for cloud,
set `OWL_EMBEDDER_PROVIDER=bedrock` (Amazon Titan) instead, so no daemon is
needed, and build the index with that embedder. Reranking uses Bedrock
`amazon.rerank-v1:0` and needs AWS credentials; set `OWL_RERANK_PROVIDER=none` to
run without AWS. `OWL_PROVIDER=bedrock` uses `BedrockLlm` over the Converse API;
probe the configured model once with
`uv run python scripts/probe_bedrock.py`. Copy `.env.example` to `.env` and fill
it in. For containers and hosting, see [`docs/deploy.md`](docs/deploy.md).

The academy frontend, or a direct client, uses `POST /ask/stream`. To watch the
raw SSE events:

```
curl -N -X POST http://localhost:8000/ask/stream \
  -H 'Content-Type: application/json' \
  -d '{"question":"Who is the Head of Gryffindor House?"}'
```

---

## Evaluation

The harness scores each stage separately, so a failure can be attributed to retrieval or generation.

| Layer | Metric | Gate |
|---|---|---|
| Retrieval | `Hit@k` / `Recall@k` / `MRR` | no regression |
| Generation | judge correctness, faithfulness | thresholds |
| Grounding | citation validity | `= 1.0` |
| Abstention | refusal on `unanswerable` | high |
| Leakage | closed-book gap | augmented >> closed-book |

First measured run (V1 mini-eval #51, reranker #6; details in `eval/README.md`):

| Metric | With rerank | No rerank |
|---|---|---|
| Hit@5 | 0.70 | 0.60 |
| Recall@5 | 0.53 | 0.42 |
| MRR | 0.45 | 0.45 |
| Abstention on unanswerable | 1.00 | 1.00 |
| Judge correct / partial / wrong | 9 / 0 / 0 of 10 | 7 / 1 / 2 of 10 |
| Grounded | 9 / 10 | 8 / 10 |

Current pinned baseline (`20261106T214850Z`, quota 0; canonical record: `docs/runs/2026-11-07-113-ingest-rebaseline.md`):

| Metric | Value |
|---|---:|
| Hit@5 overall | 0.76 |
| Hit@5 multi-part | 0.67 |
| Hit@5 named reference | 1.00 |
| Judge correct | 13/15 |
| Faithful | 13/15 |
| Abstention on unanswerable | 10/10 |

The aggregation fixture adds cross-book coverage: book coverage 0.46, entity completeness 0.45, full coverage 0.00. The routed per-book prototype reaches 0.79 coverage and 0.76 completeness at equal k=7, but citation validity is 0.56 and it is not wired into chat yet. The router separates all 10 multi-book items from the 5 near-misses on the fixture, in-sample.

Generator `qwen/qwen3-30b-a3b-instruct-2507`; judge `deepseek/deepseek-v4.1-flash-1017` (different family); reranker `amazon.rerank-v1:0`. The pinned configuration (model slugs, chunking, `top_k`, `rrf_k`, pool) is in [`config/manifest.toml`](config/manifest.toml). The eval reads the judge slug from it, and `eval/test_manifest.py` asserts the code's pinned defaults agree, so the gate fails on drift.

Every finished eval run also gets a committed Markdown record under [`docs/runs/`](docs/runs/README.md): run id, configuration, per-slice tables, reading notes, and the raw summary. The record is the strategy history; timestamped CSVs stay local.

### Exam-bank evaluation

The exam bank has a separate evaluation surface in `eval/exam/`, run with
`uv run python scripts/run_exam_eval.py`. It is not a second RAG retrieval
benchmark: it does not add a Hit@k or generation slice. It checks the published
bank and the short-answer judge:

- deterministic bank checks: grounding, MCQ options, trivial and negative stems,
  answer positions, short-answer length and rubrics, duplicates, coverage and an
  option-length gate;
- independent model checks: a second model solves each MCQ without the key,
  judges every option, and checks every short-answer golden answer;
- judge calibration: 24 committed student-style answers over 8 short questions
  with AI-proposed marks that the owner adopts via the PR; exact and adjacent
  agreement, mean absolute error, per-criterion agreement, retry rate and length
  bias.

The DADA record is `docs/runs/2026-11-09-191-dada-bank-eval.md`: 25/25 MCQ
keys, 0 ambiguities, 25/25 golden answers, adjacent agreement 0.9167, mean
absolute error 0.5000 and gate PASS. The Charms calibration record is
`docs/runs/2026-11-13-261-charms-judge-calibration.md`: 24 cases, exact 0.6250,
adjacent 1.0000, MAE 0.3750 and gate PASS. The bank and corpus are host data, so
the live exam eval runs on the host; CI runs its offline tests. The chat RAG
baseline above remains the retrieval evaluation.

---

## Roadmap

The full vision (bottom-up): a packaged pipeline, an eval harness and local gate,
a streaming API, grounding guardrails, an agentic loop, observability and deploy,
and a static exam bank. The deterministic PR CI gate is in place; the live gate
runs on the host because the corpus is not in git.

Execution is phased:

| Phase | Scope | Status |
|---|---|---|
| V1 - Shippable | grounded RAG end-to-end: ingest, hybrid retrieval + rerank, cited generation with abstention, API, mini-eval, deployed | shipped (https://api.monitus.org) |
| V2 - Deepening | guardrails, chat intents (LangGraph), Bedrock Llm adapter, cost controls, local eval gate, retrieval foundation, multi-book answer path, professor persona | chat foundation, retrieval foundation, held-out set, CI gate, persona, the stateless lesson slice and the lesson voice delivered (#176); #105 flag-off and time-boxed |
| V2.5 - Subject packs | taxonomy, material packs, source refs, validation, lesson mode | all five O.W.L. packs 1.0.0 published |
| V3 - Exam bank and continuity | exam bank, hybrid grading, memory, threads, lesson continuity, progress | exam bank 1.0.0 published; grading, calibration and serving built (#191-#193); continuity after |
| V4 - Identity (optional) | Google auth, per-user chat and exam history, progress tracking, long-term memory | last, if needed |

---

## Tech

`Python` - `FastAPI` - `LangGraph` - hybrid retrieval (vector + BM25 + RRF) + rerank - LLM adapters - eval harness and local gate; deterministic PR CI gate - `React + Vite` static frontend (`web/`) on Cloudflare Pages

---

## Agent workflow

This repository is developed with AI coding agents under human review.

- `AGENTS.md` gives coding agents project guidance: build, test, conventions, verification.
- A read-only reviewer subagent (`.opencode/agents/reviewer.md`) reviews each ticket against its acceptance criteria before it is done.
- The GitHub MCP server is used to read issues and post review findings back to the ticket.

---

## AI usage

This project is developed with AI coding agents under human review, and that usage is recorded per ticket.

- AI drafted most implementation code and tests: provider adapters and probes, retrieval and reranking, generation and verification, the API and SSE surface, the agent graph and router, the persona and lore layer, the persona lesson voice and conformance eval (#176), ingest and index, the eval harness and CI gate, the deploy files, and the entire frontend (`web/`, tickets #132, #134-#137, #141, #143, #145), including a read-only reviewer agent that checked each frontend ticket against its acceptance criteria before merge. It also drafted the DADA, Charms, Potions, Transfiguration and Herbology subject-pack materials and the lesson-table audit that produced the five packs at 1.0.0, the five exam banks 1.0.0 (25 MCQ + 25 short answers each), which an independent Mistral Small verifier checked, the hybrid grading path (#192), the bank evaluation and judge calibration (#191, #261), the served exam API and frontend swap (#193), and short-term chat memory with its deterministic follow-up resolver, bounded conversation context and thread tests (#30).
- The human set the contracts, provider abstraction, eval discipline and scope boundaries; chose the defaults, degradation policies and flag states; froze the held-out sets; approved the DADA prose and lesson-table scope on 2026-11-08; and reviewed and owns every line.
- AI assisted with documentation, issue text and run records; the human reviewed the published text.

Per-ticket records live in the commit history (`(#N)` suffixes) and pull request descriptions. Each agent-drafted PR says what was agent-written, what was human-written, and that the human reviewed it.

---

## Sources

- Corpus: the seven Harry Potter novels. The source text is not included (see
  Disclaimer) and stays the only canonical source for answers, packs and exams.
- Canon index: [The Harry Potter Lexicon](https://www.hp-lexicon.org/) is used
  as a secondary, attributed reference to map key items - spells, potions,
  creatures, objects, places, characters and events - to the novel chapters the
  books cite them in (for example `GF6` = Goblet of Fire chapter 6). The
  project harvests citation codes and links only; no Lexicon prose is copied
  into the corpus, the packs or the index, and every pack reference credits the
  Lexicon with a link and an access date. Film citations (for example `CG48` or
  any `/f` code) are recorded and tagged out of scope. The pipeline plan is in
  [`docs/lexicon-canon-index.md`](docs/lexicon-canon-index.md).

---

## Disclaimer

The source corpus is copyrighted and is not included in this repository. Only original code, questions, and metrics are published. This is a personal, non-commercial study project.
