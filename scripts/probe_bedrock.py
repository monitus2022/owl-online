"""Probe a Bedrock Llm before building on it (AGENTS.md).

Run: uv run python scripts/probe_bedrock.py [--model model-id]

Requires AWS credentials and model access in OWL_AWS_REGION. The model must be
in-region. The default is an open-weight Qwen model available on-demand.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.config import settings  # noqa: E402
from app.providers.factory import make_llm  # noqa: E402
from app.providers.probe import ProbeReport, probe_llm  # noqa: E402


def _print(report: ProbeReport) -> None:
    print(f"probing {report.name} in {settings.aws_region}")
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
    parser = argparse.ArgumentParser(description="Probe a Bedrock Llm")
    parser.add_argument("--model", default=settings.bedrock_llm_model)
    args = parser.parse_args()
    report = asyncio.run(probe_llm(make_llm("bedrock", model=args.model)))
    _print(report)
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
