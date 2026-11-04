"""Application settings. Secrets come from the environment, never from the repo.

Model slugs, chunk params, top_k and rrf_k belong to the repro manifest, not here.
"""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="OWL_",
        extra="ignore",
    )

    app_name: str = "O.W.L. Online"
    # OpenRouter is the V1 path; the Bedrock adapter lands in V2 (#36).
    provider: Literal["bedrock", "openrouter"] = "openrouter"
    embedder_provider: str = "local"
    log_level: str = "INFO"
    live_tests: bool = False     # True: use real provider calls in tests; False: use fakes

    openrouter_api_key: str | None = None
    aws_region: str = "us-east-1"

    # Pipeline inputs and the browser origins allowed by CORS.
    chunks_path: Path = Path("data/chunks.jsonl")
    index_dir: Path = Path("data/index/chroma")
    cors_origins: str = "http://localhost:5500,http://127.0.0.1:5500"
    cors_origin_regex: str = r"https://.*\.pages\.dev"

    @property
    def cors_origin_list(self) -> list[str]:
        """The configured CORS origins, split from the comma-separated value."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
