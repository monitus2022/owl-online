# Architecture

One page, three views of the engine: the layers, the provider contracts, and the
request flows. It describes the chat surface built today and the exam-bank
boundary that is planned. The README diagram is the full V1-V3 vision.

Keep this in sync when the contracts or the top-level flow change. The diagrams
are Mermaid code, so they render on GitHub and diff in review like any other file.

## Layers

| Layer | Path | Responsibility |
|---|---|---|
| HTTP | `app/api/`, `app/main.py` | routes, CORS, request/response schemas, composition root |
| Agent | `app/agent/` | LangGraph state, chat-intent router, answer / practice / feedback nodes |
| Knowledge | `app/knowledge/` | planned subject taxonomy, material packs, source refs and pack validation |
| Pipeline | `app/pipeline/` | ingest, index, retrieve (hybrid + rerank), generate |
| Providers | `app/providers/` | model adapters behind contracts (openai, boto3); the vector store SDK lives in the index builder |
| Config | `app/config.py` | environment settings (`OWL_` prefix) |
| Logging | `app/logging.py` | one formatter, level from settings, a per-request id |
| Domain | `app/schemas.py` | `Chunk` and its metadata |

Pipeline stages, in order:

| Stage | Module | Entry point |
|---|---|---|
| Ingest | `app/pipeline/ingest/` | `ingest_corpus`, `make_chunks`, `parse_chapters` |
| Index | `app/pipeline/index/` | `build_index`, `build_lexical_index` (uses `Chunk.context` when present) |
| Retrieve | `app/pipeline/retrieve/` | `compose_retriever`, `HybridRetriever.retrieve` (filter + decompose + hybrid + rerank), `diagnose` |
| Generate | `app/pipeline/generate/` | `ask`, `build_prompt`, `ground_answer`, `verify_draft` |
| Agent | `app/agent/` | `build_graph`, `route`, `answer_node`, `practice_node`, `feedback_node` |

Planned exam-bank stages, not built yet:

| Stage | Module | Responsibility |
|---|---|---|
| Subject packs | `app/knowledge/` | subject taxonomy, material records, source refs, pack build and validation |
| Exam build | `app/pipeline/exam/` | offline plan, retrieve, generate, validate, persist |
| Exam store | `app/storage/` | SQLite models and repository for exams, questions, attempts |
| Grading | `app/grading/` | hybrid: deterministic objective scoring, LLM rubric judge for free text, deterministic totals and bands |

## Contracts and adapters

The four Protocols in `app/providers/contracts.py` are the architecture. Adapters
satisfy them structurally (duck typing), so the arrows below are "implements",
not class inheritance. The factory is the only place a provider name becomes an
object, and it is called once at startup.

```mermaid
classDiagram
  direction LR

  class Llm {
    <<Protocol>>
    +generate(system, prompt, context) str
    +stream(system, prompt, context) AsyncIterator~str~
  }
  class Embedder {
    <<Protocol>>
    +name str
    +embed(texts) list
  }
  class Reranker {
    <<Protocol>>
    +rerank(query, chunks, top_k) list~Chunk~
  }
  class Retriever {
    <<Protocol>>
    +retrieve(query, top_k) list~Chunk~
  }

  class OpenRouterLlm {
    +name str
    +aclose()
  }
  class BedrockLlm {
    +name str
    +aclose()
  }
  class OllamaEmbedder {
    +name str
    +aclose()
  }
  class BedrockEmbedder {
    +name str
  }
  class HybridRetriever {
    +min_score float
    +diagnose(query, top_k)
    +aclose()
  }
  class BedrockReranker {
    +name str
  }
  class FakeLlm
  class FakeEmbedder
  class FakeReranker
  class FakeRetriever

  Llm <|.. OpenRouterLlm
  Llm <|.. BedrockLlm
  Llm <|.. FakeLlm
  Embedder <|.. OllamaEmbedder
  Embedder <|.. BedrockEmbedder
  Embedder <|.. FakeEmbedder
  Reranker <|.. BedrockReranker
  Reranker <|.. FakeReranker
  Retriever <|.. HybridRetriever
  Retriever <|.. FakeRetriever

  class factory {
    <<module>>
    make_llm(provider, model, temperature)
    make_embedder(provider)
    make_reranker(provider)
    make_retriever(provider)
  }
  factory ..> Llm : builds
  factory ..> Embedder : builds
  factory ..> Reranker : builds
  factory ..> Retriever : builds
```

Bedrock hosts the reranker (`amazon.rerank-v1:0`), the cloud embedder
(`amazon.titan-embed-text-v2:0`) and the V2 Llm (`BedrockLlm` over the Converse
API, default `qwen.qwen3-32b-v1:0`). OpenRouter remains the pinned eval and V1
path; `OWL_PROVIDER` selects the Llm at composition time. Ollama serves
embeddings for local dev. When a reranker is attached, `HybridRetriever`
retrieves a wide pool and reranks it down to `top_k`, and the abstention floor
becomes the rerank relevance floor.

## Module dependencies

Dependencies point inward. Vendor SDKs (`openai`, `boto3`, `httpx`, `chromadb`) are
imported only inside `app/providers` and the index builder, never by the API or the agent.

```mermaid
flowchart TD
  main[app/main.py] --> api[app/api]
  main --> agent[app/agent]
  main --> knowledge[app/knowledge]
  main --> pipeline[app/pipeline]
  main --> providers[app/providers]
  main --> config[app/config.py]
  main --> log[app/logging.py]
  api --> agent
  api --> pipeline
  api --> providers
  agent --> pipeline
  agent --> providers
  agent --> schemas
  knowledge --> pipeline
  knowledge --> schemas
  pipeline --> providers
  pipeline --> schemas[app/schemas.py]
  providers --> schemas
  providers --> sdk[[openai, boto3, httpx, chromadb]]
```

## Request flow: POST /ask

```mermaid
sequenceDiagram
  participant C as Client
  participant API as ask_endpoint
  participant R as Runtime
  participant A as ask()
  participant RET as HybridRetriever
  participant RR as Reranker
  participant LLM as OpenRouterLlm

  C->>API: POST /ask {question}
  API->>API: cache.get (hit -> return)
  API->>API: session cookie, limiter.admit (429 / 503)
  API->>R: get_retriever / get_llm
  API->>A: ask(question, retriever, llm)
  A->>RET: retrieve(question, top_k)
  RET->>RET: parse book/chapter reference
  RET->>RET: split into up to three sub-queries + original
  RET->>RET: dense (optional where) + BM25 legs, fuse with RRF
  alt reranker attached and the lexical gate passes
    RET->>RR: rerank(merged pool, top_k)
    RR-->>RET: top_k by relevance
  end
  RET-->>A: list[Chunk] (relevance or RRF scores, or empty)
  alt empty or top score below min_score
    A-->>API: AskResult(abstain)
  else evidence available
    A->>LLM: generate(system, prompt)
    LLM-->>A: answer citing [chunk-id]
    alt draft is empty or uncited and retries remain
      A->>A: verify_draft -> retry
      A->>LLM: generate(retry prompt, same excerpts)
      LLM-->>A: answer citing [chunk-id]
    end
    alt verification passed
      A-->>API: AskResult(answer, citations, attempts)
    else refusal or still uncited
      A-->>API: AskResult(abstain, abstain_reason, attempts)
    end
  end
  API-->>C: AskResponse {answer, citations, abstained}
```

One deadline covers the whole request: `OWL_ASK_TIMEOUT_S` (default 30 s) wraps
retrieve plus generate. On expiry `/ask` returns 504 with `{error, request_id}`
and logs the stage that was running; `/ask/stream` is not bounded, because a
legitimate stream can outlive it. The deadline frees the response, not the
worker: a provider call already running in a thread is not cancellable, so a
timed-out request can keep its thread busy until the client's own timeout.

`verify_draft` is deterministic: an empty draft or one that cites no retrieved
chunk fails. A grounded draft passes; a deliberate refusal is final and is never
retried, so abstention keeps its meaning. A paraphrase refusal is final when it
cites nothing, trails into a further refusal, or has nothing but the refusal
clause; a cited partial answer that moves on to a new or contrastive clause is
kept. The retry budget is `OWL_RETRY_BUDGET` (default 1, so at most two drafts).

## Request flow: POST /ask/stream

```mermaid
sequenceDiagram
  participant C as Client
  participant API as ask_stream_endpoint
  participant G as LangGraph agent
  participant R as HybridRetriever
  participant RR as Reranker
  participant LLM as Llm adapter

  C->>API: POST /ask/stream {question, mode, student_answer}
  API->>API: cache.get when the intent is answer
  API->>API: limiter.admit (429 / 503)
  API->>G: astream(state)
  G->>G: router -> answer | practice | feedback
  G-->>API: mode update
  API-->>C: event: mode
  G->>R: retrieve(question, top_k)
  R->>RR: rerank when configured
  R-->>G: list[Chunk]
  G->>LLM: stream(system, prompt)
  LLM-->>G: token
  G-->>API: custom {type: token}
  API-->>C: event: token
  alt draft is empty or uncited and retries remain
    G-->>API: custom {type: reset}
    API-->>C: event: reset
    G->>LLM: stream(retry prompt, same excerpts)
    LLM-->>G: token
    G-->>API: custom {type: token}
    API-->>C: event: token
  end
  G-->>API: final state
  API-->>C: event: reset when abstained
  API-->>C: event: final {answer, citations, abstained, needs_input, attempts, mode}
```

SSE events:

| Event | Payload | When |
|---|---|---|
| `mode` | `{"mode": "answer"}` | after the router update |
| `token` | `{"text": "..."}` | for each streamed token |
| `reset` | `{"reason": "retry"}` before a retry draft; `{}` before `error` and before `final` when `abstained` | clears the draft; a no-op when nothing was streamed |
| `final` | `answer`, `citations`, `abstained`, `needs_input`, `attempts`, `mode` | once, authoritative |
| `error` | `{"detail": "..."}` | provider or internal failure after headers, always preceded by `reset` |

`/ask/stream` uses the compiled graph from `app/agent/`. The router is
deterministic: an explicit mode wins, a supplied student answer is a feedback
request, a practice request is a question or short set of questions, and
everything else is answer. Tokens are a draft. Citation validation runs on the
complete answer, so an ungrounded stream emits `reset` before the authoritative
`final` event. A failed deterministic verification emits `reset` and streams one
retry when the budget allows; the client drops the rejected draft on the same
event. Provider failures arrive as an `error` event because HTTP headers are
already sent.

## Model routing

Routing is a deterministic intent split, off by default. With
`OWL_ROUTING=intent`, practice and feedback use `OWL_SMALL_MODEL` (default
Mistral Small 3.2 via OpenRouter); answers stay on the main model. A provider
error on the small model falls back to the main model once. The route and any
fallback are trace spans, and the model is on the usage line. No model call is
used to decide the route.

A vendor policy check runs before an adapter is built. OpenAI, Anthropic and
Google models are rejected, including their open-weight releases, because the
deployment region bans them regardless of host.

## Tracing

Each request can emit flat JSONL span records under the request id. The stream
path emits `router`
(intent), `retrieve` (chunk ids and top score), one `generate` per attempt
(model, prompt hash and length), `verify` (ok and reason), `retry`, and `final`.
Cache hits emit a `cache` span instead of retrieve/generate.

Traces go to the `owl.trace` logger and, when `OWL_TRACE_FILE` is set, to a
size-capped file that is safe to ship. Prompt text is never emitted: the span
carries a hash and a character count so a run can be identified without storing
the excerpts. The trace records the agent's decisions, not hidden model
reasoning.

Retrieved text is treated as untrusted. `sanitize_evidence` removes instruction
spans from the evidence and logs the affected chunk ids; a chunk left empty is
dropped from the citation set ("ignore previous instructions", "reveal the prompt", "you must
now"), and the answer system prompt tells the model to ignore instructions inside
excerpts.

## Chat intents vs exam bank

The chat graph is the online surface. Its three intents are intentionally
lightweight:

| Intent | Trigger | Output | Persisted | Authoritative |
|---|---|---|---|---|
| `answer` | a question about the books | grounded explanation with citations | no | no |
| `practice` | "give me a practice question on ..." | one or two grounded questions, streamed | no | no |
| `feedback` | "mark my answer", or a supplied answer | formative feedback and a provisional mark | no | no |

The exam bank is a separate, offline surface. It is not a chat intent and it does
not run inside `/ask` or `/ask/stream`. Generation and lesson mode read from
versioned subject knowledge packs, not from free model memory:

```mermaid
flowchart LR
  CORP[(Corpus + index)] --> PACK[Subject knowledge pack]
  PACK --> EXAM[Exam builder]
  PACK --> LESSON[Lesson builder]
  EXAM --> DB[(Exam store)]
  DB --> API[Static exam API]
```

A pack contains subjects, topics, concepts, materials and source refs. Every
material points to a chunk id, book, chapter, quote, text hash and index hash.
Every generated question or lesson section must cite a material id and source
ref; the validator rejects anything else before publication. Secondary
references such as a Lexicon entry may be stored as links for discovery and
attribution, but they are not the canonical source and are never copied into
the pack.

Canon tiers are explicit:

| Tier | Sources | Exam use |
|---|---|---|
| Primary | the seven novels | exam-gradable, the only source refs |
| Secondary | Rowling companion books | optional further reading, not exam-gradable in v1 |
| Tertiary | interviews, Pottermore, Cursed Child | optional metadata, not exam-gradable |
| Excluded | films, games, fan works | discovery only |

A subject with thin primary coverage is reported as thin. It is not padded with
film or secondary material.

| Stage | Where it runs | Output |
|---|---|---|
| Pack build | batch job over the corpus | validated materials with source refs and pack version |
| Exam build | batch job over the packs | validated questions, rubrics, evidence snapshots |
| Exam store | SQLite in `/data` | static papers with versions and status |
| Exam serving | `GET /exams` and `GET /exams/{id}` | stored paper, no model call |
| Attempt grading | submit endpoint | hybrid score and score band |

The boundary matters because the two surfaces have different guarantees. Chat
practice is disposable and formative. Exam-bank papers are validated, versioned
and reproducible.

### Hybrid grading

An O.W.L. paper mixes question types, so grading is not one algorithm:

| Question type | Scorer |
|---|---|
| `mcq` | deterministic normalised match |
| `short_answer` | deterministic accepted variants, LLM fallback for paraphrase |
| `long_answer` | pinned LLM judge with the stored rubric and evidence |

Each question stores its maximum marks, rubric criteria, evidence snapshot and
model answer. The judge scores one question per call and returns structured
JSON:

```json
{
  "criteria": [
    {"id": "c1", "awarded": 2, "max": 2, "reason": "..."},
    {"id": "c2", "awarded": 1, "max": 2, "reason": "..."}
  ],
  "total": 3,
  "feedback": "...",
  "evidence_ids": ["b3-c10-0036"]
}
```

The scorer validates that every criterion appears once, that `0 <= awarded <=
max`, that the total is the sum, and that evidence ids are a subset of the
question evidence. A parse or validation failure gets one retry, then a
`needs_review` state; it is never silently scored zero.

Totals and bands are computed by code. The LLM writes criterion marks and
feedback; it does not write the final grade. The judge is pinned by model,
temperature 0, prompt version and rubric version. It must be a different model
family from the question generator. Grading outputs are cached by exam version,
question id, answer hash and judge configuration so a regrade is reproducible.

A human-marked calibration set measures exact and adjacent agreement, mean
absolute error and per-criterion agreement. That set is the evidence that the
judge is usable, not a claim that it is infallible.

If a future feature wants to save a chat-generated question to the bank, it must
go through validation and versioning, not write directly.

### Memory and identity

The chat is stateless today. Short-term memory is a later phase: a `thread_id`, a
graph checkpointer, recent messages plus a rolling summary, and a rewrite node
that resolves follow-ups. Anonymous threads are enough for a continuous
professor chat.

Per-user long-term memory is the last optional phase. It needs Google OIDC, a
users table, ownership checks, and storage for chat threads and exam attempts. It
also needs retention, export and delete rules. Auth is deliberately not a
dependency of the exam bank or of short-term chat continuity.

See `docs/workplan.md` for phase order and exit criteria.

### Cost controls

Chat is the variable-cost surface; exam content is mostly offline. The chat
controls (#88) enforce per-session limits (10/min, 100/day, 2 concurrent), the same minute and
concurrency limits per IP plus a 100/day IP cap, and a daily token budget. Over a limit the API returns 429
with `Retry-After`; over the budget it returns 503 for chat only, so `/health`
and future exam routes stay up. Counters live in the one API process, so a
restart resets the windows; auth later moves them to a user id.

Corpus-only answers pass through an in-process exact cache keyed by prompt
version, index text hash, retrieval settings, embedder and reranker config,
model and normalised question. Practice and feedback never
read or write it: feedback is personalised by the student answer and practice is
meant to vary. Usage is logged for each processed request, cache hits included; a
429, 502, 503 or 504 does not produce a line. The line carries estimated
input/output tokens,
model, intent, cache hit, cost and latency; a client that disconnects before the
stream ends may not produce a line. Prices are configuration, not constants.

The `Runtime` (the retriever with its optional reranker, the llm, the compiled
agent graph and the index text hash used by the cache key) is built once in the
app lifespan, never per request.
Provider failures surface as a normalized `ProviderError` and become a 502 at
the edge, or an SSE `error` event once a stream has started.

Logging is one formatter at `OWL_LOG_LEVEL`. Each request gets a short id
(echoed as `X-Request-ID`), and `ask()` logs per-stage timings (retrieve,
generate) so a slow request can be attributed to a stage without a profiler.
The retriever and the providers add DEBUG lines (dense, sparse, rerank, embed,
generate) for the per-call detail.

## Data shapes

| Type | Module | Kind | Purpose |
|---|---|---|---|
| `Chunk` | `app/schemas.py` | pydantic | retrieved passage, metadata, optional generated context for indexing, relevance or fused score |
| `ChunkMetadata` | `app/schemas.py` | pydantic | book and chapter identity |
| `AskResult` | `app/pipeline/generate/generate.py` | dataclass | answer, citations, abstained, chunks, attempts, retry_reason, abstain_reason |
| `AgentState` | `app/agent/state.py` | TypedDict | question, chat mode, student answer, chunks, answer, citations, abstained, needs_input, attempts, retry_reason |
| `RetrievalSetup` | `app/pipeline/retrieve/composition.py` | dataclass | wired retriever plus build facts |
| `BuiltIndex` | `app/pipeline/index/builder.py` | dataclass | collection, rebuilt flag, dims |
| `IngestSummary` | `app/pipeline/ingest/ingest_corpus.py` | dataclass | ingestion counts and sizes |
| `Runtime` | `app/api/runtime.py` | dataclass | retriever, llm, compiled agent graph, index hash |
| `AskRequest` / `AskResponse` | `app/api/schemas.py` | pydantic | HTTP contract |
| `StreamRequest` | `app/api/schemas.py` | pydantic | question, chat-intent override, optional answer to review |

Planned subject knowledge types, once the packs land:

| Type | Module | Purpose |
|---|---|---|
| `Subject` | `app/knowledge/taxonomy.py` | one of the 12 O.W.L. subjects |
| `Topic` | `app/knowledge/taxonomy.py` | subject topic and parent topic |
| `Concept` | `app/knowledge/taxonomy.py` | spell, character, event, definition or procedure |
| `Material` | `app/knowledge/materials.py` | grounded explanation or passage with kind, canon tier, canon scope, review status and canonical text |
| `SourceRef` | `app/knowledge/materials.py` | chunk id, book, chapter, quote, text hash, index hash |
| `ReferenceLink` | `app/knowledge/materials.py` | optional secondary source with title, URL, publisher and access date |
| `SubjectPack` | `app/knowledge/packs.py` | version, status, coverage and manifest |

Planned exam-bank types, once the offline pipeline lands:

| Type | Module | Purpose |
|---|---|---|
| `ExamFormat` | `app/storage/models.py` | subject blueprint, canon basis, fidelity, marks, duration and question mix |
| `Exam` | `app/storage/models.py` | paper identity, scope, version, publication status |
| `Question` | `app/storage/models.py` | prompt, type, max marks, stored rubric, evidence snapshot |
| `RubricCriterion` | `app/storage/models.py` | criterion id, marks, guidance |
| `EvidenceSnapshot` | `app/storage/models.py` | chunk id plus excerpt text, book and chapter at generation time |
| `Attempt` | `app/storage/models.py` | one student submission, total score, band, judge config |
| `Response` | `app/storage/models.py` | one answer, awarded marks, feedback, matched criteria |
| `JudgeRun` | `app/storage/models.py` | judge model, prompt version, rubric version, raw or hashed output |

## Keeping this current

- Update the contracts diagram when a Protocol or an adapter changes.
- Update the sequence diagrams when the `/ask` or `/ask/stream` flow changes.
- Update the SSE event contract in this page when `app/main.py` changes an event
  name or payload field.
- `pyreverse -o puml -d /tmp app` (pylint) can bootstrap the class view from source;
  the hand-kept diagrams stay small on purpose, so they describe seams rather than
  every method.
