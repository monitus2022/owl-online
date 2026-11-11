"""Process-local chat metrics for the p50/p95 and cost report (#19).

The counters live in the API process and reset on restart. They are aggregate
only: no prompt, answer or session id is stored. The usage log remains the
per-request record; this module answers the aggregate question.
"""

from __future__ import annotations

import math
from collections import Counter, deque
from datetime import UTC, datetime
from threading import Lock


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[int(position)]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (
        position - lower
    )


class Metrics:
    """Bounded rolling latency samples plus lifetime counters and cost."""

    def __init__(self, sample_size: int = 1000) -> None:
        self._lock = Lock()
        self._latencies: deque[float] = deque(maxlen=sample_size)
        self._total_cost = 0.0
        self._requests = 0
        self._cache_hits = 0
        self._abstentions = 0
        self._refusals = 0
        self._intents: Counter[str] = Counter()
        self._subjects: Counter[str] = Counter()

    def record(
        self,
        *,
        latency_ms: float,
        cost_usd: float,
        intent: str,
        subject: str,
        cache_hit: bool,
        abstained: bool,
        refused: bool,
    ) -> None:
        with self._lock:
            self._requests += 1
            self._latencies.append(float(latency_ms))
            self._total_cost += float(cost_usd)
            if cache_hit:
                self._cache_hits += 1
            if abstained:
                self._abstentions += 1
            if refused:
                self._refusals += 1
            self._intents[intent] += 1
            if subject:
                self._subjects[subject] += 1

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            latencies = list(self._latencies)
            return {
                "window": "process lifetime",
                "updated_at": datetime.now(UTC)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
                "requests": self._requests,
                "sample_size": len(latencies),
                "p50_latency_ms": round(_percentile(latencies, 0.50), 2),
                "p95_latency_ms": round(_percentile(latencies, 0.95), 2),
                "total_cost_usd": round(self._total_cost, 6),
                "cache_hits": self._cache_hits,
                "abstentions": self._abstentions,
                "refusals": self._refusals,
                "by_intent": dict(self._intents),
                "by_subject": dict(self._subjects),
            }


__all__ = ["Metrics"]
