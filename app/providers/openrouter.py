"""OpenRouter provider: hosted open-weight LLMs over the OpenAI-compatible API.

Only this module imports the vendor SDK. Everything else holds the Llm contract.
"""

import logging
import time
from collections.abc import AsyncIterator
from typing import cast

from openai import (
    APITimeoutError,
    AsyncOpenAI,
    AsyncStream,
    AuthenticationError,
    OpenAIError,
    RateLimitError,
)
from openai.types.chat import ChatCompletionChunk, ChatCompletionMessageParam

from app.providers.errors import ProviderError, ProviderRateLimited, ProviderTimeout

logger = logging.getLogger(__name__)

# TODO: move to config
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "qwen/qwen3-30b-a3b-instruct-2507"
DEFAULT_TIMEOUT = 60.0


class OpenRouterLlm:
    """Llm contract over OpenRouter chat completions."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        client: AsyncOpenAI | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        if client is None and not api_key:
            raise ProviderError("OWL_OPENROUTER_API_KEY is not set")
        self.name = f"openrouter/{model}"  # manifest pin + logging
        self._model = model
        self._temperature = temperature
        if max_tokens is not None and max_tokens < 1:
            raise ValueError("max_tokens must be positive")
        self._max_tokens = max_tokens
        self._client = client or AsyncOpenAI(
            base_url=base_url, api_key=api_key, timeout=timeout
        )

    async def generate(
        self,
        system: str,
        prompt: str,
        *,
        context: str | None = None,
    ) -> str:
        start = time.perf_counter()
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=self._messages(system, prompt, context),
                **self._sampling(),
            )
        except OpenAIError as exc:
            raise _normalize(exc) from exc
        logger.debug(
            "generate %s in %.0fms", self._model, (time.perf_counter() - start) * 1000
        )
        content = response.choices[0].message.content if response.choices else None
        return content or ""

    def stream(
        self,
        system: str,
        prompt: str,
        *,
        context: str | None = None,
    ) -> AsyncIterator[str]:
        return self._stream(system, prompt, context)

    async def _stream(
        self, system: str, prompt: str, context: str | None
    ) -> AsyncIterator[str]:
        try:
            stream = cast(
                "AsyncStream[ChatCompletionChunk]",
                await self._client.chat.completions.create(
                    model=self._model,
                    messages=self._messages(system, prompt, context),
                    stream=True,
                    **self._sampling(),
                ),
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    yield delta
        except OpenAIError as exc:
            raise _normalize(exc) from exc

    async def aclose(self) -> None:
        """Close the underlying HTTP client, if the SDK exposes one."""
        close = getattr(self._client, "close", None)
        if close is not None:
            await close()

    def _sampling(self) -> dict[str, float | int]:
        """Optional sampling parameters; omitted entirely when not pinned."""
        sampling: dict[str, float | int] = {}
        if self._temperature is not None:
            sampling["temperature"] = self._temperature
        if self._max_tokens is not None:
            sampling["max_tokens"] = self._max_tokens
        return sampling

    @staticmethod
    def _messages(
        system: str, prompt: str, context: str | None
    ) -> list[ChatCompletionMessageParam]:
        user = prompt if context is None else f"{context}\n\n{prompt}"
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]


def _normalize(exc: OpenAIError) -> ProviderError:
    """Map a vendor error onto our types, keeping the cause for the traceback."""
    if isinstance(exc, APITimeoutError):
        return ProviderTimeout(str(exc))
    if isinstance(exc, RateLimitError):
        return ProviderRateLimited(str(exc))
    if isinstance(exc, AuthenticationError):
        return ProviderError(f"OpenRouter authentication failed: {exc}")
    return ProviderError(str(exc))