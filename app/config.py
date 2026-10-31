"""Application settings. Secrets come from the environment, never from the repo.

Model slugs, chunk params, top_k and rrf_k belong to the repro manifest, not here.
"""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="OWL_",
        extra="ignore",
    )

    app_name: str = "O.W.L. Online"
    provider: Literal["bedrock", "openrouter"] = "bedrock"
    log_level: str = "INFO"

    openrouter_api_key: str | None = None
    aws_region: str = "us-east-1"


settings = Settings()
