"""Chapter-title cross-check: Lexicon abbreviations vs corpus chapter names.

Usage:
    uv run python scripts/lexicon_title_check.py \
        --chapters data/lexicon/chapter_index.jsonl \
        --chunks /path/to/data/chunks.jsonl

Reports exact matches and explains every delta: our ingest fallback
("Chapter N"), first-line truncation of multi-line titles, US/UK spelling
wording, and the intentional dhe -> chapter-36 mapping. Informational for
#127; a finding for the corpus ingest (#113 line of work). No scraped prose
is printed beyond short chapter titles (factual labels).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

CODE_BY_BOOK = {1: "PS", 2: "CS", 3: "PA", 4: "GF", 5: "OP", 6: "HBP", 7: "DH"}
BOOK_BY_CODE = {v: k for k, v in CODE_BY_BOOK.items()}


def normalise(title: str) -> str:
    title = title.replace("’", "'").replace("‘", "'")
    return re.sub(r"[^a-z0-9 ]", "", title.casefold()).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chapters", type=Path, default=Path("data/lexicon/chapter_index.jsonl"))
    parser.add_argument("--chunks", type=Path, required=True)
    args = parser.parse_args()

    corpus: dict[tuple[int, int], str] = {}
    with args.chunks.open(encoding="utf-8") as handle:
        for line in handle:
            chunk = json.loads(line)
            meta = chunk["metadata"]
            corpus[(meta["book_num"], meta["chapter_num"])] = meta["chapter_name"]

    exact = 0
    categories: dict[str, list[str]] = {
        "ingest-fallback (no corpus title)": [],
        "ingest-truncated (multi-line title)": [],
        "spelling-or-wording": [],
        "other": [],
    }
    with args.chapters.open(encoding="utf-8") as handle:
        for line in handle:
            page = json.loads(line)
            book = BOOK_BY_CODE[page["code"]]
            chapter = 36 if page["is_epilogue"] else page["chapter_num"]
            corpus_title = corpus.get((book, chapter), "")
            site = page["abbreviation"].split(":", 1)[-1]
            site = re.sub(r"^Epilogue:\s*", "", site)
            site_norm, corpus_norm = normalise(site), normalise(corpus_title)
            if site_norm == corpus_norm:
                exact += 1
                continue
            label = f"{page['code']}{'' if page['is_epilogue'] else chapter}: "
            label += f"corpus={corpus_title!r} site={site!r}"
            if re.fullmatch(r"Chapter \d+", corpus_title):
                categories["ingest-fallback (no corpus title)"].append(label)
            elif corpus_norm and corpus_norm in site_norm:
                # multi-line titles where ingest grabbed one line (head or tail)
                categories["ingest-truncated (multi-line title)"].append(label)
            elif corpus_norm and (
                corpus_norm.replace("ll", "l") == site_norm.replace("ll", "l")
                or set(corpus_norm) - set(site_norm) <= set("aeiouy ")
                or page["is_epilogue"]
            ):
                categories["spelling-or-wording"].append(label)
            else:
                categories["other"].append(label)

    print(f"exact: {exact}")
    for name, rows in categories.items():
        print(f"{name}: {len(rows)}")
        for row in rows:
            print(f"  {row}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
