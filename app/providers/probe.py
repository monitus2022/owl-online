"""Provider health probe: verify an Llm before building on it (AGENTS.md).

The script layer only parses args and prints; the calls, timing and pass/fail
decision live here so the logic is testable and importable.
"""

import time
from dataclasses import dataclass

from app.providers.contracts import Llm

# Invented content only: the corpus is copyrighted and must stay out of git.
PROBE_SYSTEM = "Answer using only the excerpt. Cite the excerpt id in square brackets."
PROBE_PROMPT = (
    "Excerpt [b1-c01-0000]: The lighthouse keeper, Rowan, trims the wick every "
    "evening. Question: Who trims the wick each evening?"
)


@dataclass(frozen=True)
class ProbeReport:
    """What a probe observed. ok is False if either call came back empty."""

    name: str
    generate_seconds: float
    generate_text: str
    stream_seconds: float
    stream_chunks: int
    stream_text: str

    @property
    def ok(self) -> bool:
        return bool(self.generate_text.strip()) and bool(self.stream_text.strip())


async def probe_llm(
    llm: Llm,
    *,
    system: str = PROBE_SYSTEM,
    prompt: str = PROBE_PROMPT,
) -> ProbeReport:
    """Run one generate and one stream; report empty output instead of raising."""
    start = time.perf_counter()
    answer = await llm.generate(system, prompt)
    generate_seconds = time.perf_counter() - start

    start = time.perf_counter()
    tokens = [token async for token in llm.stream(system, prompt)]
    stream_seconds = time.perf_counter() - start

    return ProbeReport(
        name=getattr(llm, "name", type(llm).__name__),
        generate_seconds=generate_seconds,
        generate_text=answer,
        stream_seconds=stream_seconds,
        stream_chunks=len(tokens),
        stream_text="".join(tokens),
    )