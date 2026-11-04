"""Probe an OpenRouter model before building on it (AGENTS.md).

Run: uv run python scripts/probe_openrouter.py [--model slug]
Params only; the probe logic lives in app.providers.probe, and the adapter is
built through the factory so the API key comes from settings.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.providers.factory import make_llm  # noqa: E402
from app.providers.openrouter import DEFAULT_MODEL  # noqa: E402
from app.providers.probe import ProbeReport, probe_llm  # noqa: E402


def _print(report: ProbeReport) -> None:
    print(f"probing {report.name}")
    print(
        f"generate ok in {report.generate_seconds:.2f}s: "
        f"{report.generate_text.strip()[:200]!r}"
    )
    print(
        f"stream ok in {report.stream_seconds:.2f}s, {report.stream_chunks} chunks: "
        f"{report.stream_text.strip()[:200]!r}"
    )
    print("PROBE PASSED" if report.ok else "PROBE FAILED")


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe an OpenRouter model")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()
    report = asyncio.run(probe_llm(make_llm("openrouter", model=args.model)))
    _print(report)
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())