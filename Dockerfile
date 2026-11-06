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

# Runtime image gets [project] dependencies. The ingest group is a dev default,
# so opt out with --no-default-groups; LangGraph and SSE are base dependencies
# because the V2 API imports them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-default-groups --no-cache

COPY app ./app
# The persona card is loaded at import time, so it must be in the image even
# when OWL_PERSONA is off.
COPY config ./config

ENV PATH="/app/.venv/bin:$PATH" \
    OWL_CHUNKS_PATH=/data/chunks.jsonl \
    OWL_INDEX_DIR=/data/index/chroma \
    OWL_LORE_PATH=/data/lore

RUN python -c "import app.main, app.agent.graph, app.api.runtime, app.pipeline.retrieve, app.pipeline.generate"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
