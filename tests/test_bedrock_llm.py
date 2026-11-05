"""Bedrock Llm tests: a fake client stands in for AWS, no network."""

import threading

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from app.providers.bedrock import BedrockLlm
from app.providers.errors import ProviderError, ProviderRateLimited, ProviderTimeout


class _BlockingStream:
    """One delta, then block until close so cancellation can be observed."""

    def __init__(self) -> None:
        self.close_called = threading.Event()
        self._sent = False

    def __iter__(self):
        return self

    def __next__(self):
        if not self._sent:
            self._sent = True
            return {"contentBlockDelta": {"delta": {"text": "H"}}}
        self.close_called.wait(timeout=2)
        raise StopIteration

    def close(self) -> None:
        self.close_called.set()


class _BlockingClient:
    def __init__(self) -> None:
        self.stream = _BlockingStream()

    def converse_stream(self, **kwargs):
        return {"stream": self.stream}


class _FakeConversationClient:
    def __init__(self, text: str = "ok", error: Exception | None = None) -> None:
        self.text = text
        self.error = error
        self.calls: list[dict] = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return {
            "output": {"message": {"content": [{"text": self.text}]}},
            "stopReason": "end_turn",
        }

    def converse_stream(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        events = [{"messageStart": {"role": "assistant"}}]
        events += [
            {"contentBlockDelta": {"delta": {"text": piece}}} for piece in self.text
        ]
        events.append({"messageStop": {"stopReason": "end_turn"}})
        return {"stream": iter(events)}


def _llm(client, **kwargs) -> BedrockLlm:
    return BedrockLlm(
        model="test/model",
        region="us-east-1",
        client=client,
        **kwargs,
    )


async def test_generate_returns_text_and_builds_converse_request():
    client = _FakeConversationClient("An answer.")
    llm = _llm(client, temperature=0.0, max_tokens=128)
    assert await llm.generate("sys", "ask") == "An answer."
    call = client.calls[0]
    assert call["modelId"] == "test/model"
    assert call["system"] == [{"text": "sys"}]
    assert call["messages"] == [{"role": "user", "content": [{"text": "ask"}]}]
    assert call["inferenceConfig"] == {"maxTokens": 128, "temperature": 0.0}


async def test_context_is_folded_into_the_user_message():
    client = _FakeConversationClient("x")
    await _llm(client).generate("sys", "ask", context="EVIDENCE")
    assert client.calls[0]["messages"][0]["content"][0]["text"] == "EVIDENCE\n\nask"


async def test_temperature_is_omitted_when_unset():
    client = _FakeConversationClient()
    await _llm(client).generate("sys", "ask")
    assert "temperature" not in client.calls[0]["inferenceConfig"]


async def test_empty_system_is_omitted():
    client = _FakeConversationClient()
    await _llm(client).generate("", "ask")
    assert "system" not in client.calls[0]


async def test_stream_yields_pieces_in_order():
    llm = _llm(_FakeConversationClient("Hello!"))
    tokens = [token async for token in llm.stream("sys", "ask")]
    assert "".join(tokens) == "Hello!"


async def test_name_is_the_manifest_slug():
    assert _llm(_FakeConversationClient()).name == "bedrock/test/model"


async def test_throttling_is_normalized():
    error = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "slow"}}, "Converse"
    )
    with pytest.raises(ProviderRateLimited):
        await _llm(_FakeConversationClient(error=error)).generate("s", "p")


async def test_model_timeout_code_is_normalized():
    error = ClientError(
        {"Error": {"Code": "ModelTimeoutException", "Message": "slow"}}, "Converse"
    )
    with pytest.raises(ProviderTimeout):
        await _llm(_FakeConversationClient(error=error)).generate("s", "p")


async def test_stream_close_stops_worker_and_closes_stream():
    client = _BlockingClient()
    stream = _llm(client).stream("sys", "ask")
    assert await anext(stream) == "H"
    await stream.aclose()
    assert client.stream.close_called.wait(timeout=1)


async def test_connection_error_is_normalized_for_generate():
    error = EndpointConnectionError(endpoint_url="https://bedrock")
    with pytest.raises(ProviderTimeout):
        await _llm(_FakeConversationClient(error=error)).generate("s", "p")


async def test_connection_error_is_normalized_for_stream():
    error = EndpointConnectionError(endpoint_url="https://bedrock")
    llm = _llm(_FakeConversationClient(error=error))
    with pytest.raises(ProviderTimeout):
        async for _ in llm.stream("s", "p"):
            pass


async def test_other_client_error_is_normalized():
    error = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "no"}}, "Converse"
    )
    with pytest.raises(ProviderError):
        await _llm(_FakeConversationClient(error=error)).generate("s", "p")
