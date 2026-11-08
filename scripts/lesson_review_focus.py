"""Focused DADA + Charms lesson-table review file with teacher attribution.

Passes over the corpus chunks, scores lesson-cue sentences per chapter,
infers the most-likely teacher per chapter from cue-sentence mentions, and
writes a review file with up to 3 evidence quotes per row. The crawl in
progress is not needed: this is books-chunks-only (#128).
"""

import json
import re
from collections import Counter, defaultdict

CHUNKS = "/Users/tc/Documents/Github/owl-online/data/chunks.jsonl"
OUT = "/Users/tc/Documents/Github/owl-128/data/lessons_review_dada_charms.md"

# (teacher, subject, extra cue) - DADA teachers rotate per book year.
DADA_TEACHERS = {
    1: "Quirrell", 2: "Lockhart", 3: "Lupin (Snape subs c9-c10)",
    4: "Crouch (Bartemius, as Mad-Eye Moody)", 5: "Umbridge",
    6: "Dumbledore (private lessons; classroom DADA unnamed)",
    7: "none (on the run; Snape/Alecto era untaught)",
}
TEACHER_CUE = re.compile(
    r"\b(Quirrell|Lockhart|Lupin|Moody|Mad-Eye|Umbridge|Snape|Dumbledore|"
    r"Flitwick|Sprout|McGonagall|Binns|Trelawney|Firenze|Hagrid|"
    r"Grubbly-Plank|Slughorn|Vector|Sinistra)\b"
)
LESSON = re.compile(
    r"lesson|\bclass\b|classroom|in class|after class|\btaught\b|detention|"
    r"our (?:new )?teacher|Defen[cs]e Against the Dark Arts|Charms", re.I,
)
DADA_TEXT = re.compile(r"Defen[cs]e Against the Dark Arts|\bdark arts\b|\bD\.?A\.?\b", re.I)
CHARMS_TEXT = re.compile(r"\bCharms\b")
SENT_SPLIT = re.compile(r"(?<=[.!?])\s")


def sentences(text):
    return [s for s in SENT_SPLIT.split(text) if 25 < len(s) < 400]


def main():
    # subject -> (book, chapter) -> {"n": int, "teachers": Counter, "ex": []}
    acc = defaultdict(lambda: defaultdict(lambda: {"n": 0, "t": Counter(), "ex": []}))
    for line in open(CHUNKS, encoding="utf-8"):
        c = json.loads(line)
        m = re.match(r"b(\d+)-c(\d+)-", c["id"])
        if not m:
            continue
        b, ch = int(m.group(1)), int(m.group(2))
        for sent in sentences(c["text"]):
            if not LESSON.search(sent):
                continue
            teachers = set(TEACHER_CUE.findall(sent))
            if DADA_TEXT.search(sent):
                row = acc["DADA"][(b, ch)]
                row["n"] += 1
                for t in teachers:
                    row["t"][t] += 1
                if len(row["ex"]) < 3:
                    row["ex"].append((c["id"], sent.strip()[:170]))
            if CHARMS_TEXT.search(sent) or "Flitwick" in teachers:
                row = acc["Charms"][(b, ch)]
                row["n"] += 1
                for t in teachers:
                    row["t"][t] += 1
                if len(row["ex"]) < 3:
                    row["ex"].append((c["id"], sent.strip()[:170]))

    with open(OUT, "w", encoding="utf-8") as out:
        for subj in ("DADA", "Charms"):
            out.write(f"# {subj} lesson-table review (machine proposal)\n\n")
            out.write("Approve each row or strike it. Teacher column: X = "
                      "cue-mention\nwinner, and for DADA the book-year roster "
                      "is the check.\n\n")
            out.write("| keep | chapter | n | teacher (inferred) | year "
                      "roster | top evidence |\n")
            out.write("|---|---|---:|---|---|---|\n")
            items = sorted(acc[subj].items(), key=lambda x: (x[0][0], -x[1]["n"]))
            for (b, ch), row in items:
                if row["n"] < 2:
                    continue
                top_t = row["t"].most_common(1)[0] if row["t"] else ("?", 0)
                roster = DADA_TEACHERS.get(b, "") if subj == "DADA" else "Flitwick"
                ev = row["ex"][0][0] if row["ex"] else "-"
                q = row["ex"][0][1] if row["ex"] else ""
                out.write(
                    f"| [ ] | b{b} c{ch} | {row['n']} | {top_t[0]} ({top_t[1]}) "
                    f"| {roster} | `{ev}` {q} |\n"
                )
            out.write("\n## Dropped from view (n<2 cue sentences)\n\n")
            low = [f"b{b}c{ch}({r['n']})" for (b, ch), r in items if r["n"] < 2]
            out.write(", ".join(low) + "\n\n")
    print(f"rows written: DADA={sum(1 for r in acc['DADA'].values() if r['n'] >= 2)} "
          f"Charms={sum(1 for r in acc['Charms'].values() if r['n'] >= 2)}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
