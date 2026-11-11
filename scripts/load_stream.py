"""Load check for POST /ask/stream (#179).

Runs concurrent streaming requests against a running API and reports p50/p95
latency, the error rate and the token spend read from the server's usage log.
This is a manual/release check, not a CI gate.

Run:
    uv run python scripts/load_stream.py \
        --base-url http://127.0.0.1:8001 \
        --requests 40 --concurrency 8 \
        --usage-log /tmp/owl-e2e-api.log \
        --out docs/load/2026-11-11-179-stream-load.md
"""

from __future__ import annotations

import argparse
import asyncio
import math
import re
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

_USAGE = re.compile(
    r"chat usage .*in_tokens=(\d+) out_tokens=(\d+) cost_usd=([0-9.]+)"
)


def percentile(values: list[float], fraction: float) -> float:
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


async def one_request(
    client: httpx.AsyncClient,
    base_url: str,
    question: str,
    subject: str,
    mode: str,
) -> tuple[float, int, bool, bool]:
    started = time.perf_counter()
    final = False
    failed = False
    status = 0
    try:
        async with client.stream(
            "POST",
            f"{base_url}/ask/stream",
            json={"question": question, "subject": subject, "mode": mode},
        ) as response:
            status = response.status_code
            event = ""
            async for line in response.aiter_lines():
                if line.startswith("event: "):
                    event = line[7:]
                elif line.startswith("data: ") and event:
                    if event == "final":
                        final = True
                    if event == "error":
                        failed = True
                    event = ""
    except httpx.HTTPError:
        failed = True
    return time.perf_counter() - started, status, final, failed


async def run(args: argparse.Namespace) -> int:
    semaphore = asyncio.Semaphore(args.concurrency)
    usage_offset = 0
    if args.usage_log and Path(args.usage_log).exists():
        usage_offset = Path(args.usage_log).stat().st_size

    async with httpx.AsyncClient(timeout=args.timeout) as client:
        async def bounded():
            async with semaphore:
                return await one_request(
                    client,
                    args.base_url.rstrip("/"),
                    args.question,
                    args.subject,
                    args.mode,
                )

        results = await asyncio.gather(*(bounded() for _ in range(args.requests)))

    latencies = [result[0] for result in results]
    errors = sum(
        1 for _, status, final, failed in results if status != 200 or failed or not final
    )
    usage = {"in": 0, "out": 0, "cost": 0.0}
    usage_lines = 0
    if args.usage_log and Path(args.usage_log).exists():
        with Path(args.usage_log).open(encoding="utf-8") as handle:
            handle.seek(usage_offset)
            lines = handle.read().splitlines()
        for line in lines:
            match = _USAGE.search(line)
            if match:
                usage_lines += 1
                usage["in"] += int(match.group(1))
                usage["out"] += int(match.group(2))
                usage["cost"] += float(match.group(3))

    run_id = datetime.now(UTC).strftime("load-%Y%m%dT%H%M%SZ")
    report = "\n".join(
        [
            "# Stream load check (#179)",
            "",
            f"- Run id: `{run_id}`",
            f"- Base URL: `{args.base_url.rstrip('/')}`",
            f"- Requests: {args.requests}; concurrency: {args.concurrency}",
            f"- Question: `{args.question}`; subject: `{args.subject}`; mode: `{args.mode}`",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| p50 latency | {percentile(latencies, 0.50):.3f} s |",
            f"| p95 latency | {percentile(latencies, 0.95):.3f} s |",
            f"| Mean latency | {statistics.fmean(latencies):.3f} s |",
            f"| Error rate | {errors / len(results):.1%} ({errors}/{len(results)}) |",
            f"| Usage lines | {usage_lines} |",
            f"| Input tokens | {usage['in']} |",
            f"| Output tokens | {usage['out']} |",
            f"| Cost (USD) | {usage['cost']:.6f} |",
            "",
            "Token spend is read only from usage lines appended to the server log",
            "after the run starts; the SSE final does not carry token counts. A",
            "stub-API run reports the stub's estimated usage; a release run must",
            "point `--usage-log` at the real API log.",
            "",
            "This check is manual/release-only; it is not part of the pull-request",
            "CI gate.",
            "",
        ]
    )
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(f"wrote {out}")
    print(report)
    return 0 if errors == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--requests", type=int, default=40)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--question", default="What is a Boggart?")
    parser.add_argument("--subject", default="dada")
    parser.add_argument("--mode", default="lesson")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--usage-log", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1:
        parser.error("--requests and --concurrency must be positive")
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
