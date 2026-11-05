"""Application settings. Secrets come from the environment, never from the repo.

Model slugs, chunk params, top_k and rrf_k belong to the repro manifest, not here.
"""

from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# pydantic-settings reads .env for OWL_ settings but does not populate the
# process environment. boto3 reads AWS_* from the environment, so credentials in
# .env would be invisible to it. Load .env here; existing env vars still win.
load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="OWL_",
        extra="ignore",
    )

    app_name: str = "O.W.L. Online"
    # OpenRouter is the V1 path; the Bedrock adapter lands in V2 (#36).
    provider: Literal["bedrock", "openrouter"] = "openrouter"
    # Embedder: "local" (Ollama) for dev, "bedrock" (Titan) for cloud.
    embedder_provider: str = "local"
    ollama_base_url: str = "http://localhost:11434"
    bedrock_embed_model: str = "amazon.titan-embed-text-v2:0"
    bedrock_embed_dims: int = 1024
    bedrock_llm_model: str = "qwen.qwen3-32b-v1:0"
    bedrock_llm_max_tokens: int = 1024
    # Deterministic verification retries per answer. The ticket budget is one
    # extra draft; 0 disables it. The cap is enforced at the settings boundary.
    retry_budget: int = Field(default=1, ge=0, le=1)
    # Deadline for one /ask request (retrieve plus generate). /ask/stream is not
    # bounded because a legitimate stream can outlive it.
    ask_timeout_s: float = Field(default=30.0, gt=0)

    # Chat cost controls (#88). Anonymous limits; auth later moves them to a
    # user id. The counters live in one process, so a restart resets the windows.
    chat_per_minute: int = Field(default=10, ge=1)
    chat_per_day: int = Field(default=100, ge=1)
    chat_ip_per_day: int = Field(default=100, ge=1)
    chat_concurrent: int = Field(default=2, ge=1)
    chat_daily_token_budget: int = Field(default=200_000, ge=1)
    chat_cache_entries: int = Field(default=256, ge=1)
    chat_cache_ttl_s: int = Field(default=3600, ge=1)
    # Signs the anonymous session cookie. Empty means a random per-process
    # secret, which resets sessions on restart; set it in production.
    session_secret: str = ""
    # CIDRs whose forwarded client-IP headers are trusted. Docker's bridge
    # gateway reaches the container, so private ranges are included.
    trusted_proxies: str = "127.0.0.1/32,::1/128,172.17.0.1/32"
    # Optional JSONL trace file. Empty means stdout only (the owl.trace logger).
    trace_file: Path | None = None
    trace_max_bytes: int = 20_000_000

    @field_validator("trace_file", mode="before")
    @classmethod
    def _blank_trace_file(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value
    # Placeholders for the pinned generator; set OWL_ prices to your contract.
    chat_input_price_per_mtok: float = Field(default=0.10, ge=0)
    chat_output_price_per_mtok: float = Field(default=0.30, ge=0)
    log_level: str = "INFO"
    live_tests: bool = False     # True: use real provider calls in tests; False: use fakes

    openrouter_api_key: str | None = None
    aws_region: str = "us-east-1"

    # Pipeline inputs and the browser origins allowed by CORS.
    chunks_path: Path = Path("data/chunks.jsonl")
    index_dir: Path = Path("data/index/chroma")
    cors_origins: str = "http://localhost:5500,http://127.0.0.1:5500"
    cors_origin_regex: str = r"https://.*\.pages\.dev"

    # Reranking (V1, #6). Set OWL_RERANK_PROVIDER=none to disable.
    rerank_provider: str = "bedrock"
    rerank_model: str = "amazon.rerank-v1:0"
    rerank_pool: int = 50
    rerank_min_score: float = 0.0  # relevance floor when reranking; calibrate via #51
    rerank_cache_path: Path = Path("data/rerank_cache.jsonl")

    @property
    def cors_origin_list(self) -> list[str]:
        """The configured CORS origins, split from the comma-separated value."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
