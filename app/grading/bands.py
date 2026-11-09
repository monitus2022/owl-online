"""Deterministic O/E/A/P/D/T bands for exam attempts (#192).

The thresholds are percentage-based and match the frontend `bandFor` helper:

    O >= 90%, E >= 80%, A >= 70%, P >= 50%, D >= 30%, T below.

Integer cross-multiplication keeps the paper-score cutoffs exact: for a 50-mark
paper the boundaries are 45, 40, 35, 25 and 15 marks.
"""

from __future__ import annotations

from typing import Literal

Band = Literal["O", "E", "A", "P", "D", "T"]

BAND_LABELS: dict[Band, str] = {
    "O": "Outstanding",
    "E": "Exceeds Expectations",
    "A": "Acceptable",
    "P": "Poor",
    "D": "Dreadful",
    "T": "Troll",
}


def band_for(total: int, max_marks: int) -> Band:
    """Return the band for an integer score; raise on an impossible score."""
    if max_marks <= 0:
        raise ValueError("max_marks must be positive")
    if total < 0 or total > max_marks:
        raise ValueError(f"total {total} is outside 0..{max_marks}")
    if total * 10 >= max_marks * 9:
        return "O"
    if total * 10 >= max_marks * 8:
        return "E"
    if total * 10 >= max_marks * 7:
        return "A"
    if total * 10 >= max_marks * 5:
        return "P"
    if total * 10 >= max_marks * 3:
        return "D"
    return "T"


__all__ = ["BAND_LABELS", "Band", "band_for"]
