"""OpenRouter adapter tests: no network. A fake client stands in for the SDK."""

from types import SimpleNamespace

import httpx
import pytest
from openai import APITimeoutError, OpenAIError, RateLimitError

from app.providers.errors import ProviderError, ProviderRateLimited, ProviderTimeout
from app.providers.openrouter import OpenRouterLlm


def _response(text: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def _chunk(text: str):
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=text))])


def _request() -> httpx.Request:
    return httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")


class _FakeCompletions:
    def __init__(self, *, text: str = "ok", error: Exception | None = None) -> None:
        self._text = text
        self._error = error
        self.calls: list[dict] = []

    async def create(self, *, model, messages, stream=False, **kwargs):
        self.calls.append(
            {"model": model, "messages": messages, "stream": stream, **kwargs}
        )
        if self._error is not None:
            raise self._error
        if stream:

            async def gen():
                for piece in self._text:
                    yield _chunk(piece)

            return gen()
        return _response(self._text)


class _FakeClient:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.chat = SimpleNamespace(completions=completions)


def _llm(
    completions: _FakeCompletions, *, temperature: float | None = None
) -> OpenRouterLlm:
    return OpenRouterLlm(
        model="test/model", client=_FakeClient(completions), temperature=temperature
    )


async def test_generate_returns_content_and_sends_system_then_user():
    completions = _FakeCompletions(text="An answer [b1-c01-0000].")
    out = await _llm(completions).generate("sys", "ask")
    assert out == "An answer [b1-c01-0000]."
    call = completions.calls[0]
    assert call["model"] == "test/model"
    assert call["messages"][0] == {"role": "system", "content": "sys"}
    assert call["messages"][1] == {"role": "user", "content": "ask"}


async def test_context_is_folded_into_the_user_message():
    completions = _FakeCompletions(text="x")
    await _llm(completions).generate("sys", "ask", context="EVIDENCE")
    assert completions.calls[0]["messages"][1]["content"] == "EVIDENCE\n\nask"


async def test_stream_yields_pieces_in_order():
    tokens = [t async for t in _llm(_FakeCompletions(text="Hello")).stream("sys", "ask")]
    assert "".join(tokens) == "Hello"


async def test_name_is_the_manifest_slug():
    assert _llm(_FakeCompletions()).name == "openrouter/test/model"


async def test_temperature_is_sent_when_pinned():
    completions = _FakeCompletions(text="ok")
    llm = _llm(completions, temperature=0.0)
    await llm.generate("sys", "ask")
    tokens = [token async for token in llm.stream("sys", "ask")]
    assert "".join(tokens) == "ok"
    assert all(call["temperature"] == 0.0 for call in completions.calls)


async def test_temperature_is_omitted_when_unset():
    completions = _FakeCompletions()
    await _llm(completions).generate("sys", "ask")
    assert "temperature" not in completions.calls[0]


async def test_missing_key_without_client_raises():
    with pytest.raises(ProviderError):
        OpenRouterLlm(model="m", api_key=None)


async def test_timeout_is_normalized():
    err = APITimeoutError(request=_request())
    with pytest.raises(ProviderTimeout):
        await _llm(_FakeCompletions(error=err)).generate("s", "p")


async def test_rate_limit_is_normalized():
    err = RateLimitError("slow down", response=httpx.Response(429, request=_request()), body=None)
    with pytest.raises(ProviderRateLimited):
        await _llm(_FakeCompletions(error=err)).generate("s", "p")


async def test_generic_error_is_normalized():
    with pytest.raises(ProviderError):
        await _llm(_FakeCompletions(error=OpenAIError("boom"))).generate("s", "p")


async def test_live_generate_and_stream(openrouter_live):
    """Opt-in: real calls against the pinned model (OWL_LIVE_TESTS=1)."""
    if not openrouter_live:
        pytest.skip("set OWL_LIVE_TESTS=1 and OWL_OPENROUTER_API_KEY to run")
    llm = OpenRouterLlm()
    answer = await llm.generate(
        "Answer using only the excerpt. Cite the id in brackets.",
        "Excerpt [b1-c01-0000]: The lighthouse keeper, Rowan, trims the wick every "
        "evening. Who trims the wick each evening?",
    )
    assert answer.strip()
    tokens = [t async for t in llm.stream("Reply with the single word ok.", "say ok")]
    assert "".join(tokens).strip()