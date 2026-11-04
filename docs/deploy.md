# Deploy

The API container is portable; what is not portable is the data and the
embedder. Read the two constraints before picking a host.

## Two runtime constraints

1. Corpus and index. The source text is copyrighted, so neither `chunks.jsonl`
   nor the vector index is in the image or the repo. The host must be given both
   out of band, as a mounted volume or a private bucket, at `OWL_CHUNKS_PATH` and
   `OWL_INDEX_DIR`. Build the index locally once (`uv run python
   scripts/build_index.py`) and upload `data/chunks.jsonl` plus
   `data/index/chroma/`. The index directory must be writable: Chroma opens its
   SQLite store read-write at startup, so mount it writable (or copy it to a
   writable path) rather than read-only.

2. A query-time embedder. Retrieval embeds every question, and the current
   embedder is Ollama (`OWL_EMBEDDER_PROVIDER=local`). The container has no
   Ollama, so the host must run one of:
   - Ollama reachable over the network, set `OWL_OLLAMA_BASE_URL` to it (the
     default is `http://localhost:11434`). The embedding model must match the one
     the index was built with (`qwen3-embedding:0.6b`), or the index slug guard
     will force a rebuild.
   - a hosted embedder, added later behind the `Embedder` contract. A Bedrock
     embedding model is the natural fit, but the index would need rebuilding.

## Run locally with Docker

```
docker build -t owl-online .
docker run --rm -p 8000:8000 \
  -v "$PWD/data:/data" \
  -e OWL_PROVIDER=openrouter \
  -e OWL_OPENROUTER_API_KEY=... \
  -e OWL_EMBEDDER_PROVIDER=local \
  -e OWL_OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  -e OWL_RERANK_PROVIDER=bedrock \
  -e OWL_AWS_REGION=ap-northeast-1 \
  -e AWS_ACCESS_KEY_ID=... -e AWS_SECRET_ACCESS_KEY=... \
  owl-online
```

`host.docker.internal` reaches an Ollama daemon running on the host (macOS and
Windows; on Linux use the host gateway address).

To keep Ollama next to the API instead, run both with Compose:

```yaml
services:
  api:
    build: .
    ports: ["8000:8000"]
    env_file: [.env]
    environment:
      OWL_OLLAMA_BASE_URL: http://ollama:11434
      OWL_CHUNKS_PATH: /data/chunks.jsonl
      OWL_INDEX_DIR: /data/index/chroma
    volumes: ["./data:/data"]
    depends_on: [ollama]
  ollama:
    image: ollama/ollama:latest
    volumes: ["ollama:/root/.ollama"]
volumes:
  ollama:
```

Then pull the embedding model once: `docker compose exec ollama ollama pull
qwen3-embedding:0.6b`.

## Deploy to a host

Any container host works (Fly.io, Render, Railway, a small EC2). The steps are
the same:

1. Push the image (or let the platform build the Dockerfile).
2. Set secrets as platform environment variables, never in the image:
   `OWL_OPENROUTER_API_KEY`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
   `OWL_AWS_REGION`, and any `OWL_*` overrides. Prefer an instance role over
   static keys where the platform supports it.
3. Attach the data volume at `/data` (or point `OWL_CHUNKS_PATH` /
   `OWL_INDEX_DIR` at the mounted files).
4. Make an embedder reachable and set `OWL_OLLAMA_BASE_URL`.
5. Health check: `GET /health`.

For Fly.io, roughly: `fly launch --no-deploy`, add a volume mounted at `/data`,
`fly secrets set ...`, upload the data into the volume, then `fly deploy`.

## Cloudflare Pages for the chat page

The chat page is a single file, `app/api/static/index.html`, with no build step.
Host it on Cloudflare Pages and point it at the API by setting the meta tag:

```html
<meta name="owl-api-base" content="https://your-api-host" />
```

CORS already allows `https://*.pages.dev` via `OWL_CORS_ORIGIN_REGEX`; add the
exact origin to `OWL_CORS_ORIGINS` if you use a custom domain.

## Check it

```
curl -s https://your-api-host/health
curl -s https://your-api-host/ask -H 'Content-Type: application/json' \
  -d '{"question":"..."}'
```
