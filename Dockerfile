# O.W.L. Online API.
#
# The corpus and the vector index are NOT baked in: the source text is
# copyrighted, so they are provided at runtime via a mounted volume (see
# docs/deploy.md). Secrets come from the environment only, never the image.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first, for layer caching. The project is not installed
# (tool.uv.package = false); app/ is imported from the working directory.
#
# Runtime image gets only [project] dependencies. The ingest and agent groups
# (local ingestion, V2) are dev defaults, so opt out with --no-default-groups;
# chromadb's unused kubernetes/onnxruntime are excluded in pyproject.toml.
# --no-cache keeps the ~570 MB uv cache out of the image. This matters because
# the host root volume is 8 GB.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-default-groups --no-cache

COPY app ./app

# Build-time smoke test: fail the build if the runtime import graph is broken,
# for example if chromadb needed an excluded backend at import time.
RUN python -c "import app.main, app.api.runtime, app.pipeline.retrieve, app.pipeline.generate"

ENV PATH="/app/.venv/bin:$PATH" \
    OWL_CHUNKS_PATH=/data/chunks.jsonl \
    OWL_INDEX_DIR=/data/index/chroma

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
