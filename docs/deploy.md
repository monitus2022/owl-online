# Deploy

The API container is portable; what is not portable is the data and the
embedder. Read the two constraints before picking a host.

## Two runtime constraints

1. Corpus, index and lore pack. The source text is copyrighted, so neither `chunks.jsonl`
   nor the vector index is in the image or the repo. The host must be given both
   out of band, as a mounted volume or a private bucket, at `OWL_CHUNKS_PATH` and
   `OWL_INDEX_DIR`. Build the index locally once (`uv run python
   scripts/build_index.py`) and upload `data/chunks.jsonl` plus
   `data/index/chroma/`, plus the authored `data/lore/` pack. The index directory must be writable: Chroma opens its
   SQLite store read-write at startup, so mount it writable (or copy it to a
   writable path) rather than read-only. The published subject packs live under
   `/data/subjects/` (`OWL_SUBJECTS_PATH`); `GET /v1/subjects` serves the valid
   published packs and skips drafts or broken ones. The planned exam database
   lives under `/data/`; both stay on the same mounted volume and out of the
   image.

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
  -e OWL_SESSION_SECRET=<long-random-value> \
  -e OWL_AWS_REGION=ap-northeast-1 \
  -e AWS_ACCESS_KEY_ID=... -e AWS_SECRET_ACCESS_KEY=... \
  owl-online
```

`host.docker.internal` reaches an Ollama daemon running on the host (macOS and
Windows; on Linux use the host gateway address).

Behind nginx, set the client IP and clear the Cloudflare header so a client
cannot supply either one. The app prefers `X-Real-IP`:

```
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header CF-Connecting-IP "";
```

If Cloudflare fronts nginx, `ngx_http_realip_module` is required, because
without it every request shares the edge address and the per-client IP caps
become per-edge. Fetch the ranges from
`https://www.cloudflare.com/ips-v4` and `https://www.cloudflare.com/ips-v6`:

```
real_ip_header CF-Connecting-IP;
set_real_ip_from 173.245.48.0/20;   # add every published range
real_ip_recursive on;
```

Then `$remote_addr` is the client and `X-Real-IP` carries it to the app.

`OWL_TRUSTED_PROXIES` defaults to loopback plus the Docker bridge
(`172.17.0.0/16`); widen it only for a proxy that is not on that bridge.

To use the Bedrock Llm instead of OpenRouter, set `OWL_PROVIDER=bedrock` and the
model, for example `OWL_BEDROCK_LLM_MODEL=qwen.qwen3-32b-v1:0` and
`OWL_BEDROCK_LLM_MAX_TOKENS=1024`. The model must be available in
`OWL_AWS_REGION`; check it once with `uv run python scripts/probe_bedrock.py`.
The instance role needs `bedrock:InvokeModel` and
`bedrock:InvokeModelWithResponseStream` on the model or inference-profile ARN.

The image is runtime-only: `uv sync --no-default-groups` installs `[project]`
dependencies, including LangGraph and sse-starlette because the V2 API imports
them. The `ingest` (PDF parsing) group is excluded, and chromadb's unused
`kubernetes` and `onnxruntime` are excluded in `pyproject.toml`. The V1 image was
about 215 MB; the V2 image adds LangGraph and SSE, so re-measure after the next
build. It remains well within the host's 8 GB volume.

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
   static keys where the platform supports it. Set `OWL_PROVIDER=bedrock` plus
   `OWL_BEDROCK_LLM_MODEL` and `OWL_BEDROCK_LLM_MAX_TOKENS` to use the Bedrock
   Converse path.
3. Attach the data volume at `/data` (or point `OWL_CHUNKS_PATH` /
   `OWL_INDEX_DIR` at the mounted files).
4. A query-time embedder. Use the vendor path, `OWL_EMBEDDER_PROVIDER=bedrock`
   (Amazon Titan), so no Ollama daemon is needed; the index must be built with
   the same embedder. See the two runtime constraints above.
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

The root volume is 8 GB and `/data` (the corpus plus the index) shares it. The
V1 image was about 215 MB to download (about 590 MB on disk); re-measure the V2
image after the next build. A pull should still fit comfortably next to the
running one, and the rollout prunes the previous image after a successful start.
It still pulls first, so the old version keeps serving while the pull fits; only
on failure does it stop the container, prune unused images, and retry. That retry
is the one window where a failed deploy leaves the API down until the next
successful rollout. A larger or separate volume for `/data` remains the durable
fix.

### V1 host

| Field | Value |
|---|---|
| Live URL | `https://api.monitus.org` (Cloudflare proxy, Full strict) |
| Instance | `i-0bd80b876b2c1ab56` (t3.micro, Amazon Linux 2023) |
| Region | `ap-northeast-3` |
| Elastic IP | `13.208.134.172` |
| Instance role | `monitus-ec2-ecr-role` (`AmazonSSMManagedInstanceCore`, `AmazonEC2ContainerRegistryReadOnly`, `owl-online-bedrock`) |
| Bedrock policy | `owl-online-bedrock`: `bedrock:Rerank` on `*`, `bedrock:InvokeModel` on the Titan and rerank model ARNs, and `bedrock:InvokeModel` plus `bedrock:InvokeModelWithResponseStream` on the Llm model ARN (or inference-profile ARN) in `ap-northeast-1` |
| Data volume | `/data` on the instance root volume |

The Bedrock Llm needs both invoke actions on the exact model or inference-profile
ARN. For the default on-demand model:

```
arn:aws:bedrock:ap-northeast-1::foundation-model/qwen.qwen3-32b-v1:0
```

If the chosen model is served through an inference profile, grant the same
actions on the profile ARN instead. Converse streaming fails without
`bedrock:InvokeModelWithResponseStream`.

## Log shipping

Application logs go to stdout, and Docker's json-file driver keeps them on the
host. A deploy removes the old container, which deletes its log file, so a
nightly copy would lose a day of logs on every rollout. Ship continuously
instead.

One-time AWS setup, with `LOG_BUCKET` and the instance role:

```
aws s3api create-bucket --bucket "$LOG_BUCKET" --region "$AWS_REGION" \
  --create-bucket-configuration LocationConstraint="$AWS_REGION"
aws s3api put-public-access-block --bucket "$LOG_BUCKET" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-lifecycle-configuration --bucket "$LOG_BUCKET" \
  --lifecycle-configuration '{"Rules":[{"ID":"expire-7d","Status":"Enabled",
  "Filter":{"Prefix":"owl-online/"},"Expiration":{"Days":7}}]}'
```

Attach `s3:PutObject` on `arn:aws:s3:::$LOG_BUCKET/owl-online/*` to the
instance role (`monitus-ec2-ecr-role`). No list or delete permission is needed.

Run Fluent Bit on the host. It tails the Docker json files, buffers on disk and
flushes every 30 seconds or 5 MB:

```
mkdir -p /var/lib/owl/fluent-bit
docker run -d --name owl-logs --restart unless-stopped \
  --log-driver=none \
  -e LOG_BUCKET="$LOG_BUCKET" -e AWS_REGION="$AWS_REGION" \
  -v /var/lib/docker/containers:/var/lib/docker/containers:ro \
  -v /var/lib/owl/fluent-bit:/var/lib/owl/fluent-bit \
  -v "$PWD/deploy/fluent-bit/fluent-bit.conf:/fluent-bit/etc/fluent-bit.conf:ro" \
  fluent/fluent-bit:3.1
```

`--log-driver=none` keeps the shipper from tailing its own output. The API
container keeps `--log-driver json-file` with `max-size=10m` and `max-file=3`,
so `docker logs` still works and a log burst cannot fill the 8 GB volume.

Rules:

- 7-day expiry is an S3 lifecycle rule, not a job.
- A shipper outage only delays the copy: Fluent Bit buffers on disk up to 512 MB.
- The tail covers every Docker container on the host; only the API and the shipper
run there. If the shipper is down long enough to fill that buffer, new records
are dropped; the API keeps serving.
- Logs carry ids, counts, timings and opaque session ids. Prompts, answers and
  student text are not logged, so nothing copyrighted or personal leaves the
  host through this path.

Verify with `aws s3 ls "s3://$LOG_BUCKET/owl-online/" --recursive | tail` and
`aws s3api get-bucket-lifecycle-configuration --bucket "$LOG_BUCKET"`.

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
   OWL_LORE_PATH=/data/lore
   OWL_INDEX_DIR=/data/index/titan
   OWL_RERANK_PROVIDER=bedrock
   OWL_RERANK_CACHE_PATH=/data/rerank_cache.jsonl
   OWL_SESSION_SECRET=<long-random-value>
   OWL_TRUSTED_PROXIES=127.0.0.1/32,::1/128,172.17.0.1/32
   OWL_CHAT_PER_MINUTE=10
   OWL_CHAT_PER_DAY=100
   OWL_CHAT_IP_PER_DAY=100
   OWL_CHAT_CONCURRENT=2
   OWL_CHAT_DAILY_TOKEN_BUDGET=200000
   OWL_TRACE_FILE=/data/traces.jsonl
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

## Cloudflare Pages

### The academy frontend (web/)

`web/` is a React + Vite app deployed as its own static site. Create a Pages
project connected to the repository and set:

| Field | Value |
|---|---|
| Root directory | `web` |
| Build command | `npm run build` |
| Output directory | `dist` |
| `NODE_VERSION` (build environment) | `22` |
| `VITE_OWL_API_BASE` (build environment, production and preview) | the API origin, for example `https://api.monitus.org` |

`VITE_OWL_API_BASE` is read at build time, not at runtime: an unset variable
bakes in the same-origin default and chat then calls Pages instead of the
API. Set it in both environments, or previews fail chat in ways production
will not reveal. `public/_redirects` serves `index.html` for deep links, so
`/venue/...` routes load on refresh. The `web` workflow
(`.github/workflows/web.yml`) runs the same build on every pull request.

CORS already allows `https://*.pages.dev` - deploy previews included - through
`OWL_CORS_ORIGIN_REGEX`. For a custom domain, add the exact origin to
`OWL_CORS_ORIGINS` on the host and restart the API.

### The single-file test page

The chat page is a single file, `app/api/static/index.html`, with no build
step. Host it on Cloudflare Pages and point it at the API by setting the meta
tag:

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
