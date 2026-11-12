# Browser E2E and accessibility checks

The Playwright suite covers the student loop and the critical accessibility
surfaces. It runs the real FastAPI app with an injected stub runtime and the
real Vite frontend, so it needs no corpus, index, pack prose or model keys.

## Run

```text
npm ci --prefix web
npm ci --prefix e2e
npx --prefix e2e playwright install chromium
npm --prefix e2e test
```

`npm --prefix e2e test` starts two servers through Playwright:

- `uv run python e2e/api_server.py` on `127.0.0.1:8001`;
- `npm --prefix web run dev` on `127.0.0.1:5500`, with
  `VITE_OWL_API_BASE=http://127.0.0.1:8001`.

The stub uses the real router, graph, SSE contract, schemas and persona cards,
with a tiny in-memory DADA pack, a tiny published DADA exam bank and a fixed
LLM. It is a contract stub, not a model test.

## Coverage

- gate -> cloister -> DADA venue;
- a lesson question returns teaching prose and material/book citations;
- the identity answer is scripted;
- an off-topic question abstains in world;
- the exam room renders the no-papers state for a venue without a bank;
- a paper can be sat, marked and found in history;
- the venue stays open when the subjects API is unreachable.

## Accessibility

`tests/a11y.spec.ts` runs axe on the gate, cloister, venue, the chat after a
lesson answer and the exam room. The current audit has no critical, serious or
moderate findings. The test fails on any critical violation; minor and
best-practice findings, if any, are triaged in the pull request.

## Load check

The stream load check is manual/release-only, not a pull-request gate:

```text
uv run python scripts/load_stream.py \
  --base-url http://127.0.0.1:8001 \
  --requests 40 --concurrency 8 \
  --usage-log /tmp/owl-api.log \
  --out docs/load/2026-11-11-179-stream-load.md
```

The script reports p50/p95 latency, the error rate and the token spend parsed
from the usage lines appended to the server log after the run starts. A stub run
reports the stub's estimated usage; a release run points `--usage-log` at the
real API log.
