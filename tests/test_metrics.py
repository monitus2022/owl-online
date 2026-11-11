"""Process-local metrics: bounded samples and lifetime counters (#19)."""

from app.api.metrics import Metrics


def test_metrics_bounds_the_latency_sample_but_keeps_lifetime_totals():
    metrics = Metrics(sample_size=2)
    for latency in (1.0, 2.0, 3.0):
        metrics.record(
            latency_ms=latency,
            cost_usd=1.0,
            intent="answer",
            subject="dada",
            cache_hit=False,
            abstained=False,
            refused=False,
        )
    snapshot = metrics.snapshot()
    assert snapshot["requests"] == 3
    assert snapshot["sample_size"] == 2
    assert snapshot["total_cost_usd"] == 3.0
    assert snapshot["p50_latency_ms"] >= 0
    assert snapshot["p95_latency_ms"] >= snapshot["p50_latency_ms"]
    assert snapshot["updated_at"].endswith("Z")
