"""Probe logic tests: pass/fail decided on output, using the fake Llm."""

from app.providers.fakes import FakeLlm
from app.providers.probe import probe_llm


async def test_probe_reports_ok_for_a_talking_llm():
    report = await probe_llm(FakeLlm())
    assert report.ok is True
    assert report.generate_text.strip()
    assert report.stream_text.strip()
    assert report.stream_chunks > 0


class _SilentLlm:
    """Llm that returns nothing, to exercise the probe's failure path."""

    async def generate(self, system, prompt, *, context=None):
        return ""

    def stream(self, system, prompt, *, context=None):
        async def gen():
            if False:  # pragma: no cover - marks gen as an async generator
                yield ""

        return gen()


async def test_probe_reports_failure_for_an_empty_llm():
    report = await probe_llm(_SilentLlm())
    assert report.ok is False