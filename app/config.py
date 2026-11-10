"""Application settings. Secrets come from the environment, never from the repo.

Model slugs, chunk params, top_k and rrf_k belong to the repro manifest, not here.
"""

from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field, field_validator, model_validator
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
    # Per-retrieval-leg candidate quota for decomposed questions (sub-queries
    # plus the original question). 0 keeps the original global fusion.
    subquery_quota: int = Field(default=0, ge=0)
    # Experimental multi-book answer path: per-book extraction, merge, one
    # synthesis and a coverage statement. Off keeps the single-pass answer.
    multi_book: bool = False
    # Persona layer: the reviewed professor tone, scripted meta and personal
    # replies. Off keeps the plain grounded assistant.
    persona: bool = False
    # Lesson mode: teach from reviewed subject-pack materials instead of the
    # raw corpus. Off keeps the measured corpus answer path unchanged.
    lesson_mode: bool = False
    lesson_top_k: int = Field(default=3, ge=1, le=10)
    # Cosine floor on the best material match. Calibrated for
    # qwen3-embedding:0.6b on the DADA pack (related 0.598-0.791, off-topic
    # 0.160-0.549); recalibrate when the embedder changes.
    lesson_min_score: float = Field(default=0.58, ge=0.0, le=1.0)
    # When the pack does not cover the question, answer from the corpus with a
    # labelled second tier instead of abstaining. Off restores pack-only lesson.
    lesson_fallback: bool = True

    # Deadline for one /ask request (retrieve plus generate). /ask/stream is not
    # bounded because a legitimate stream can outlive it.
    ask_timeout_s: float = Field(default=30.0, gt=0)

    # Exam grading (#192). The bank manifest pins the judge model and prompt
    # version; these settings choose the runtime adapter, token budget and cache.
    exam_judge_provider: Literal["bedrock", "openrouter"] = "openrouter"
    exam_judge_max_tokens: int = Field(default=2000, ge=1)
    exam_judge_cache_path: Path | None = Path("data/exam_judge_cache.jsonl")

    # Exam serving (#193). The bank is the published SQLite import; a paper
    # samples six MCQ and four short answers and attempts are capped per day.
    exam_store_path: Path = Path("data/exams/exams.db")
    exam_subject: str = "dada"
    exam_mcq_count: int = Field(default=6, ge=1, le=25)
    exam_short_count: int = Field(default=4, ge=1, le=25)
    exam_duration_minutes: int = Field(default=60, ge=1)
    exam_attempts_per_day_anonymous: int = Field(default=3, ge=1)
    exam_attempts_per_day_signed_in: int = Field(default=5, ge=1)
    exam_attempts_per_day_ip: int = Field(default=9, ge=1)

    # Chat cost controls (#88). Anonymous limits; auth later moves them to a
    # user id. The counters live in one process, so a restart resets the windows.
    chat_per_minute: int = Field(default=10, ge=1)
    chat_per_day: int = Field(default=100, ge=1)
    chat_ip_per_day: int = Field(default=100, ge=1)
    chat_concurrent: int = Field(default=2, ge=1)
    chat_daily_token_budget: int = Field(default=200_000, ge=1)
    chat_cache_entries: int = Field(default=256, ge=1)
    chat_cache_ttl_s: int = Field(default=3600, ge=1)
    # Model routing (#82). Off keeps one model on every intent.
    routing: Literal["off", "intent"] = "off"
    small_provider: Literal["openrouter", "bedrock"] = "openrouter"
    small_model: str = "mistralai/mistral-small-3.2-24b-instruct"
    # Signs the anonymous session cookie. Empty means a random per-process
    # secret, which resets sessions on restart; set it in production.
    session_secret: str = ""
    # CIDRs whose forwarded client-IP headers are trusted. Docker's bridge
    # gateway reaches the container, so private ranges are included.
    trusted_proxies: str = "127.0.0.1/32,::1/128,172.17.0.1/32"
    # Optional JSONL trace file. Empty means stdout only (the owl.trace logger).
    trace_file: Path | None = None
    trace_max_bytes: int = 20_000_000

    @model_validator(mode="after")
    def _check_small_model_pair(self) -> "Settings":
        if self.routing == "intent":
            if self.small_provider == "openrouter" and "/" not in self.small_model:
                raise ValueError("OpenRouter small models use the vendor/model slug")
            if self.small_provider == "bedrock" and "/" in self.small_model:
                raise ValueError(
                    "Bedrock small models use the provider.model-id form, not a slug"
                )
        return self

    @field_validator(
        "trace_file",
        "lore_path",
        "subjects_path",
        "exam_judge_cache_path",
        mode="before",
    )
    @classmethod
    def _blank_path(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value
    # Placeholders for the pinned generator; set OWL_ prices to your contract.
    chat_input_price_per_mtok: float = Field(default=0.10, ge=0)
    chat_output_price_per_mtok: float = Field(default=0.30, ge=0)
    chat_small_input_price_per_mtok: float = Field(default=0.075, ge=0)
    chat_small_output_price_per_mtok: float = Field(default=0.20, ge=0)
    log_level: str = "INFO"
    live_tests: bool = False     # True: use real provider calls in tests; False: use fakes

    openrouter_api_key: str | None = None
    aws_region: str = "us-east-1"

    # Pipeline inputs and the browser origins allowed by CORS.
    chunks_path: Path = Path("data/chunks.jsonl")
    index_dir: Path = Path("data/index/chroma")
    # Authored setting facts. A directory of Markdown front-matter files, or a
    # JSONL file. Missing means the answer path stays book-only.
    lore_path: Path | None = Path("data/lore")
    # Default subject key for the eval harness and direct ask() callers. The
    # API uses the request subject, or persona_subject when it is omitted.
    lore_subject: str = "dada"
    # Default API chat subject and the card used when the request omits subject.
    # Kept separate from lore_subject so the eval default does not pin the API.
    persona_subject: str = "dada"
    # Subject knowledge packs (#87). A parent directory of per-subject pack
    # directories (data/subjects/<subject>/). Empty means no packs present:
    # exam generation and lesson mode stay disabled until a pack validates.
    subjects_path: Path | None = Path("data/subjects")
    cors_origins: str = "http://localhost:5500,http://127.0.0.1:5500"
    cors_origin_regex: str = r"https://([a-z0-9-]+\.)?owl-online\.pages\.dev"

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
