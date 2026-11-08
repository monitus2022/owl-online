"""Draft the chapter-to-subject lesson table from corpus chunks (#128).

Heuristic extractor: classroom-scene evidence = a sentence containing a
teacher/subject name AND a lesson cue, counted per chapter. Output is a
review draft (local, with quotes); the APPROVED table is structure-only
(chapter, subject, teacher) and is what gets committed.
"""

import json
import re
import sys
from collections import defaultdict

CHUNKS = sys.argv[1] if len(sys.argv) > 1 else "data/chunks.jsonl"
OUT = sys.argv[2] if len(sys.argv) > 2 else "data/lessons_draft.md"

SUBJECT_TEACHERS = {
    "DADA": [
        "Quirrell", "Lockhart", "Lupin", "the Mad-Eye", "Moody",
        "Umbridge", "Snape", "Dumbledore",
    ],
    "Charms": ["Flitwick", "Sprite"],
    "Transfiguration": ["McGonagall"],
    "Potions": ["Snape", "Slughorn"],
    "Herbology": ["Sprout"],
    "History of Magic": ["Binns"],
    "Divination": ["Trelawney", "Firenze"],
    "Astronomy": ["Sinistra"],
    "Care of Magical Creatures": ["Hagrid", "Grubbly-Plank", "Kettleburn"],
    "Arithmancy": ["Vector"],
}
SUBJECT_ALIASES = {
    "DADA": ["Defense Against the Dark Arts", "Defence Against the Dark Arts",
             "D.A.", "defence lessons", "dark arts"],
    "Potions": ["Potions lesson", "Potions class", "Potions"],
    "Herbology": ["Herbology"],
    "Divination": ["Divination"],
    "Charms": ["Charms lesson", "Charms class", "Charms"],
    "Transfiguration": ["Transfiguration"],
    "History of Magic": ["History of Magic"],
    "Care of Magical Creatures": ["Care of Magical Creatures", "Creatures lesson"],
    "Astronomy": ["Astronomy"],
    "Arithmancy": ["Arithmancy"],
}
CUE = re.compile(
    r"\blesson|\bclass\b|classroom|in class|after class|\btaught\b|"
    r"our teacher|lesson text|detention",
    re.I,
)

SENT_SPLIT = re.compile(r"(?<=[.!?])\s")


def sentences(text):
    return [s for s in SENT_SPLIT.split(text) if 25 < len(s) < 400]


def main():
    # (subject, book, chapter) -> {"chunks": [(id, quote)], "n": count}
    hits = defaultdict(lambda: {"n": 0, "ex": []})
    per_chapter_subjects = defaultdict(set)
    for line in open(CHUNKS, encoding="utf-8"):
        c = json.loads(line)
        m = re.match(r"b(\d+)-c(\d+)-", c["id"])
        if not m:
            continue
        b, ch = int(m.group(1)), int(m.group(2))
        for sent in sentences(c["text"]):
            for subj, teachers in SUBJECT_TEACHERS.items():
                t_hit = next((t for t in teachers if t in sent), None)
                a_hit = next((a for a in SUBJECT_ALIASES[subj] if a in sent), None)
                if not (t_hit or a_hit):
                    continue
                if not CUE.search(sent) and not a_hit:
                    continue
                if a_hit and not t_hit and not CUE.search(sent):
                    continue
                key = (subj, b, ch)
                hits[key]["n"] += 1
                per_chapter_subjects[(b, ch)].add(subj)
                if len(hits[key]["ex"]) < 3:
                    q = sent.strip()[:200]
                    hits[key]["ex"].append((c["id"], q, t_hit or a_hit))

    with open(OUT, "w", encoding="utf-8") as out:
        out.write("# Lesson table draft - machine proposal, awaiting review\n\n")
        out.write("Rows grouped by subject; n = lesson-cue sentences in the "
                  "chapter.\nReview each row, keep/merge/drop; the approved "
                  "table is\nchapter -> subject + teacher with no quotes.\n\n")
        cur = None
        for (subj, b, ch), d in sorted(hits.items(),
                                       key=lambda x: (x[0][0], -x[1]["n"])):
            if subj != cur:
                out.write(f"\n## {subj}\n\n")
                cur = subj
            out.write(f"- b{b} c{ch} (n={d['n']})\n")
            for cid, q, who in d["ex"]:
                out.write(f"    - `{cid}` [{who}]: \"{q}\"\n")
        out.write("\n# Multi-subject chapters (disambiguation needed)\n\n")
        for (b, ch), subjs in sorted(per_chapter_subjects.items()):
            if len(subjs) > 1:
                out.write(f"- b{b} c{ch}: {', '.join(sorted(subjs))}\n")
    total = sum(d["n"] for d in hits.values())
    print(f"chapters proposed: {len(hits)} | cue sentences: {total}")
    for (subj, b, ch), d in sorted(hits.items(), key=lambda x: -x[1]["n"])[:25]:
        print(f"  {subj:<24} b{b} c{ch:>2}  n={d['n']}")
    print(f"draft written: {OUT}")


if __name__ == "__main__":
    main()
