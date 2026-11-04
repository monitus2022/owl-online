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

2. A query-time embedder. Retrieval embeds every question. There are two
   providers, and the index must be built with the same one:
   - `OWL_EMBEDDER_PROVIDER=local` (Ollama): for dev. Point `OWL_OLLAMA_BASE_URL`
     at the daemon, and use the index built with `qwen3-embedding:0.6b`.
   - `OWL_EMBEDDER_PROVIDER=bedrock` (Amazon Titan): the vendor path for cloud,
     no daemon needed. Build a separate index once:

     ```
     uv run python scripts/build_index.py --provider bedrock --index data/index/titan
     ```

     then set `OWL_EMBEDDER_PROVIDER=bedrock` and `OWL_INDEX_DIR=/data/index/titan`
     on the host. The slug guard keeps the two indexes apart.

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

## CI/CD (GitHub Actions)

`.github/workflows/deploy.yml` is the minimal pipeline: on a push to `main` it
builds the image, pushes it to ECR, and rolls it out on the EC2 instance over
SSM. It runs no tests and touches no data; the corpus and index are a one-time
upload (see below). The full pipeline (ECS, gated tests) stays in #37.

Repo secrets required:

| Secret | Value |
|---|---|
| `AWS_ACCESS_KEY_ID` | the `monitus-companion` IAM user access key |
| `AWS_SECRET_ACCESS_KEY` | the matching secret |

The workflow settings live in the `env:` block at the top of the file (region,
ECR repository, instance id, container name, host port, env-file path, data
dir). Trigger it by pushing to `main`, or run it manually with
`workflow_dispatch`.

The instance pulls the image with its own role
(`AmazonEC2ContainerRegistryReadOnly`) and calls Bedrock with its own role, so
no keys live on the host. The container binds `127.0.0.1:8000`; nginx terminates
TLS on 80/443 and proxies to it, and reads its runtime secrets from the env file
in the next section.

### V1 host

| Field | Value |
|---|---|
| Instance | `i-0bd80b876b2c1ab56` (t3.micro, Amazon Linux 2023) |
| Region | `ap-northeast-3` |
| Elastic IP | `13.208.134.172` |
| Instance role | `monitus-ec2-ecr-role` (`AmazonSSMManagedInstanceCore`, `AmazonEC2ContainerRegistryReadOnly`, `owl-online-bedrock`) |
| Bedrock policy | `owl-online-bedrock`: `bedrock:Rerank` on `*`, `bedrock:InvokeModel` on the Titan and rerank model ARNs in `ap-northeast-1` |
| Data volume | `/data` on the instance root volume |

## One-time host setup

The pipeline ships only the image. Do these once on the instance:

1. The ECR repository `owl-online` (the workflow creates it if missing).

2. The runtime env file, outside the repo and the image, at
   `/home/ec2-user/owl.env`:

   ```
   OWL_PROVIDER=openrouter
   OWL_OPENROUTER_API_KEY=...
   OWL_EMBEDDER_PROVIDER=bedrock
   OWL_CHUNKS_PATH=/data/chunks.jsonl
   OWL_INDEX_DIR=/data/index/titan
   OWL_RERANK_PROVIDER=bedrock
   OWL_AWS_REGION=ap-northeast-1
   OWL_CORS_ORIGINS=https://your-chat-page.pages.dev
   ```

3. The data at `/data`: `chunks.jsonl` plus the index built with the same
   embedder. Build the Titan index locally, then upload both:

   ```
   uv run python scripts/build_index.py --provider bedrock --index data/index/titan
   # copy data/chunks.jsonl and data/index/titan/ to /data on the host
   ```

4. TLS. nginx terminates HTTPS on 443 with the Cloudflare Origin Certificate
   (`*.monitus.org`, from `s3://monitus-cloudflare-certs`) and proxies to the
   container on `127.0.0.1:8000`; port 80 redirects to 443. Cloudflare fronts
   `api.monitus.org` (proxied) in Full (strict) mode. Config lives at
   `/etc/nginx/conf.d/owl.conf`, certs at `/etc/nginx/owl/`.

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
