"""Run the lesson + multi-turn RAG eval (#248).

Run:
    uv run python scripts/run_rag_eval.py
    uv run python scripts/run_rag_eval.py --write-baseline
    uv run python scripts/run_rag_eval.py --check
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from eval.rag.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
