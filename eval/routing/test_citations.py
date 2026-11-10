"""Cross-type citation fixture for the authority checker (#218)."""

from __future__ import annotations

import json
from pathlib import Path

from app.knowledge.citations import check_authority

FIXTURE = Path(__file__).parent / "fixtures" / "citations.jsonl"


def test_citation_fixture_rejects_cross_type_cites():
    rows = [
        json.loads(line)
        for line in FIXTURE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) >= 16
    for row in rows:
        errors = check_authority(
            row["citations"],
            mode=row["mode"],
            abstained=row["abstained"],
        )
        assert bool(errors) != row["valid"], row["id"]
