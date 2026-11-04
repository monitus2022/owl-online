"""Shared test fixtures: guards for tests that need real external services."""

import httpx
import pytest

from app.config import settings

_OLLAMA_VERSION_URL = "http://localhost:11434/api/version"


@pytest.fixture(scope="session")
def ollama_running() -> bool:
    """True when an Ollama daemon answers on the default local port."""
    try:
        httpx.get(_OLLAMA_VERSION_URL, timeout=1)
    except Exception:
        return False
    return True


@pytest.fixture(scope="session")
def openrouter_live() -> bool:
    """True only when live provider calls are opted in and a key is present."""
    return settings.live_tests and bool(settings.openrouter_api_key)