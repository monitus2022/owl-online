"""Local open-weight provider: embeddings served by the Ollama daemon."""

import httpx

# TODO: move to config
DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen3-embedding:0.6b"


class OllamaEmbedder:
    """Embeddings from an Ollama-served model via POST /api/embed (batched input)."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        client: httpx.AsyncClient | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.name = f"ollama/{model}"  # index slug guard + manifest pin
        self._model = model
        self._client = client or httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch in one call; Ollama accepts an input list natively."""
        response = await self._client.post(
            "/api/embed", json={"model": self._model, "input": texts}
        )
        response.raise_for_status()
        return response.json()["embeddings"]

    async def aclose(self) -> None:
        """Release the HTTP pool; the composition owner (API startup, D4) calls this."""
        await self._client.aclose()
