"""Request-scoped trace: one JSON line per decision or stage.

A trace records what the agent did and what it was given, not the model's hidden
reasoning. Prompt text is represented by a hash and a length; the raw prompt is
never emitted. Spans are flat and ordered, with the request id as the trace id.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from contextvars import ContextVar, Token
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("owl.trace")

_current: ContextVar[Tracer | None] = ContextVar("owl_trace", default=None)


def prompt_fingerprint(system: str, prompt: str) -> dict[str, Any]:
    """Identify a prompt without storing its text."""
    digest = hashlib.sha256(f"{system}\n{prompt}".encode()).hexdigest()[:16]
    return {"prompt_sha": digest, "prompt_chars": len(system) + len(prompt)}


class TraceSink:
    """Append JSON lines to the log and, when configured, a size-capped file."""

    def __init__(self, path: Path | None = None, max_bytes: int = 20_000_000) -> None:
        self._path = path
        self._max_bytes = max_bytes

    def write(self, record: dict[str, Any]) -> None:
        line = json.dumps(record, ensure_ascii=False, default=str)
        logger.info(line)
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            if self._path.exists() and self._path.stat().st_size > self._max_bytes:
                rotated = self._path.with_suffix(self._path.suffix + ".1")
                self._path.replace(rotated)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            logger.warning("trace file write failed", exc_info=True)


@dataclass(frozen=True)
class Span:
    name: str
    started: float


class Tracer:
    """Emit one record per span for a single request."""

    def __init__(self, trace_id: str, sink: TraceSink) -> None:
        self.trace_id = trace_id
        self._sink = sink

    def emit(self, name: str, duration_ms: float | None = None, **attrs: Any) -> None:
        record: dict[str, Any] = {"trace_id": self.trace_id, "span": name}
        if duration_ms is not None:
            record["duration_ms"] = round(duration_ms, 2)
        record.update(attrs)
        self._sink.write(record)

    def start(self, name: str) -> Span:
        return Span(name, time.perf_counter())

    def finish(self, span: Span, **attrs: Any) -> None:
        self.emit(span.name, (time.perf_counter() - span.started) * 1000, **attrs)


def start_trace(trace_id: str, sink: TraceSink) -> Token:
    return _current.set(Tracer(trace_id, sink))


def end_trace(token: Token) -> None:
    _current.reset(token)


def current_tracer() -> Tracer | None:
    return _current.get()
