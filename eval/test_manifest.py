"""The repro manifest must agree with the code's pinned defaults.

Lives in eval/ so the documented gate `pytest eval/` enforces it: the eval
"cites" the manifest by refusing to run against a manifest that has drifted.
"""

import tomllib
from pathlib import Path

from app.config import Settings
from app.pipeline.generate import DEFAULT_MAX_RETRIES, DEFAULT_TOP_K
from app.pipeline.ingest.chunker import _CHUNK_SIZE, _MIN_CHUNK_SIZE, _OVERLAP
from app.pipeline.retrieve.retriever import DEFAULT_RRF_K
from app.providers.bedrock import DEFAULT_EMBED_DIMS, DEFAULT_EMBED_MODEL, DEFAULT_MODEL
from app.providers.local import DEFAULT_MODEL as LOCAL_EMBED_MODEL
from app.providers.openrouter import DEFAULT_MODEL as GENERATOR_MODEL
from eval.harness import JUDGE_MODEL

MANIFEST = tomllib.loads(
    (Path(__file__).resolve().parents[1] / "config" / "manifest.toml").read_text(encoding="utf-8")
)
# The declared field default, independent of any OWL_ value in the environment.
RERANK_POOL_DEFAULT = Settings.model_fields["rerank_pool"].default
RETRY_BUDGET_DEFAULT = Settings.model_fields["retry_budget"].default


def test_manifest_pins_the_generator():
    assert MANIFEST["generator"]["model"] == GENERATOR_MODEL


def test_manifest_pins_the_judge():
    assert MANIFEST["judge"]["model"] == JUDGE_MODEL


def test_manifest_pins_the_reranker():
    assert MANIFEST["reranker"]["model"] == DEFAULT_MODEL
    assert MANIFEST["reranker"]["pool"] == RERANK_POOL_DEFAULT


def test_manifest_pins_the_embedders():
    assert MANIFEST["embedder"]["cloud"]["model"] == DEFAULT_EMBED_MODEL
    assert MANIFEST["embedder"]["cloud"]["dimensions"] == DEFAULT_EMBED_DIMS
    assert MANIFEST["embedder"]["local"]["model"] == LOCAL_EMBED_MODEL


def test_manifest_pins_the_chunking():
    assert MANIFEST["chunking"]["size"] == _CHUNK_SIZE
    assert MANIFEST["chunking"]["overlap"] == _OVERLAP
    assert MANIFEST["chunking"]["min_size"] == _MIN_CHUNK_SIZE


def test_manifest_pins_the_retrieval():
    assert MANIFEST["retrieval"]["top_k"] == DEFAULT_TOP_K
    assert MANIFEST["retrieval"]["rrf_k"] == DEFAULT_RRF_K
    # The pinned run attaches a reranker, so the per-leg candidate count is the pool.
    assert MANIFEST["retrieval"]["candidates"] == RERANK_POOL_DEFAULT


def test_manifest_pins_the_retry_budget():
    assert MANIFEST["generation"]["retry_budget"] == RETRY_BUDGET_DEFAULT
    assert RETRY_BUDGET_DEFAULT == DEFAULT_MAX_RETRIES
