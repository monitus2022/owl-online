# O.W.L. Online API.
#
# The corpus and the vector index are NOT baked in: the source text is
# copyrighted, so they are provided at runtime via a mounted volume (see
# docs/deploy.md). Secrets come from the environment only, never the image.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_PREFERENCE=system \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /app

# The base image already carries Python 3.12. Pin uv to it: the project's
# `python-preference = "only-managed"` would otherwise make uv download the
# newest managed interpreter from GitHub during the image build.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-default-groups --no-cache --python python3.12

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
