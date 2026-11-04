"""The repro manifest must agree with the code's pinned defaults.

This is how the eval "cites" the manifest: if a slug or a parameter changes in
one place and not the other, this test fails.
"""

import tomllib
from pathlib import Path

from app.config import Settings
from app.pipeline.generate import DEFAULT_TOP_K
from app.pipeline.ingest.chunker import _CHUNK_SIZE, _MIN_CHUNK_SIZE, _OVERLAP
from app.pipeline.retrieve.retriever import DEFAULT_RRF_K, QUERY_CANDIDATES
from app.providers.bedrock import DEFAULT_EMBED_DIMS, DEFAULT_EMBED_MODEL, DEFAULT_MODEL
from app.providers.openrouter import DEFAULT_MODEL as GENERATOR_MODEL
from eval.harness import JUDGE_MODEL

MANIFEST = tomllib.loads(Path("config/manifest.toml").read_text(encoding="utf-8"))
# The declared field default, independent of any OWL_ value in the environment.
RERANK_POOL_DEFAULT = Settings.model_fields["rerank_pool"].default


def test_manifest_pins_the_generator():
    assert MANIFEST["generator"]["model"] == GENERATOR_MODEL


def test_manifest_pins_the_judge():
    assert MANIFEST["judge"]["model"] == JUDGE_MODEL


def test_manifest_pins_the_reranker():
    assert MANIFEST["reranker"]["model"] == DEFAULT_MODEL
    assert MANIFEST["reranker"]["pool"] == RERANK_POOL_DEFAULT


def test_manifest_pins_the_embedder():
    assert MANIFEST["embedder"]["model"] == DEFAULT_EMBED_MODEL
    assert MANIFEST["embedder"]["dimensions"] == DEFAULT_EMBED_DIMS


def test_manifest_pins_the_chunking():
    assert MANIFEST["chunking"]["size"] == _CHUNK_SIZE
    assert MANIFEST["chunking"]["overlap"] == _OVERLAP
    assert MANIFEST["chunking"]["min_size"] == _MIN_CHUNK_SIZE


def test_manifest_pins_the_retrieval():
    assert MANIFEST["retrieval"]["top_k"] == DEFAULT_TOP_K
    assert MANIFEST["retrieval"]["rrf_k"] == DEFAULT_RRF_K
    assert MANIFEST["retrieval"]["candidates"] == QUERY_CANDIDATES
