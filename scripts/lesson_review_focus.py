"""Focused DADA + Charms lesson-table review file, tiered by plan precedence.

Tiers per docs/lexicon-canon-index.md (Subject assignment):
class = taught-in-class scene sentence (teacher or subject + lesson cue);
exam  = used-in-exam-context (subject + O.W.L./exam/practical/test, same
        sentence); da-army = Dumbledore's Army chapters; duel-club =
        dueling-club scenes (both DADA, both author-pick basis).
Row tier = strongest signal present (class > exam > da-army > duel-club). Deterministic
sentence-scope matching, no model calls. Outputs are local data/ (quotes);
the approved table committed later is structure-only.
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

CHUNKS = "/Users/tc/Documents/Github/owl-online/data/chunks.jsonl"
OUT = "/Users/tc/Documents/Github/owl-128/data/lessons_review_dada_charms.md"

DADA_TEACHERS = {
    1: "Quirrell", 2: "Lockhart", 3: "Lupin (Snape subs c9-c10)",
    4: "Crouch (Bartemius, as Mad-Eye Moody)", 5: "Umbridge",
    6: "Dumbledore (private lessons; Slughorn year classroom DADA unnamed)",
    7: "none (on the run; Carrow era not examinable)",
}
TEACHER_CUE = re.compile(
    r"\b(Quirrell|Lockhart|Lupin|Moody|Mad-Eye|Umbridge|Snape|Dumbledore|"
    r"Flitwick|Sprout|McGonagall|Binns|Trelawney|Firenze|Hagrid|"
    r"Grubbly-Plank|Slughorn|Vector|Sinistra)\b"
)
LESSON = re.compile(
    r"lesson|\bclass\b|classroom|in class|after class|\btaught\b|detention|"
    r"our (?:new )?teacher", re.I,
)
DADA_TEXT = re.compile(r"Defen[cs]e Against the Dark Arts|\bdark arts\b", re.I)
CHARMS_TEXT = re.compile(r"\bCharms\b")
DADA_TEACHER_NAMES = {"Quirrell", "Lockhart", "Lupin", "Moody", "Mad-Eye",
                      "Umbridge"}
EXAM_CUE = re.compile(
    r"O\.W\.Ls?|N\.E\.W\.Ts?|\bexamin|\bexam\b|\btest(s|ing)?\b|practical",
    re.I,
)
DA_CUE = re.compile(
    r"Dumbledore.{0,3}s Army|\bthe D\.A\.", re.I,
)
DUEL_CUE = re.compile(
    r"practice dueling|practis(?:ing|e) dueling|dueling club|duelling club|"
    r"\bdueling lessons?", re.I,
)
SENT_SPLIT = re.compile(r"(?<=[.!?])\s")


def sentences(text):
    return [s for s in SENT_SPLIT.split(text) if 25 < len(s) < 400]


def main():
    # subject -> (book, chapter) -> row dict
    acc = defaultdict(lambda: defaultdict(
        lambda: {"class_n": 0, "exam_n": 0, "da_n": 0, "club_n": 0,
                 "t": Counter(), "ex": []}))
    for line in open(CHUNKS, encoding="utf-8"):
        c = json.loads(line)
        m = re.match(r"b(\d+)-c(\d+)-", c["id"])
        if not m:
            continue
        b, ch = int(m.group(1)), int(m.group(2))
        for sent in sentences(c["text"]):
            teachers = set(TEACHER_CUE.findall(sent))
            da_subject = bool(DADA_TEXT.search(sent))
            char_subject = bool(CHARMS_TEXT.search(sent))
            lesson = bool(LESSON.search(sent))
            exam = bool(EXAM_CUE.search(sent))
            da = bool(DA_CUE.search(sent))
            if lesson and (da_subject or (teachers & DADA_TEACHER_NAMES)):
                row = acc["DADA"][(b, ch)]
                row["class_n"] += 1
                for t in teachers:
                    row["t"][t] += 1
                if len(row["ex"]) < 4:
                    row["ex"].append(("class", c["id"], sent.strip()))
            elif da_subject and exam:
                row = acc["DADA"][(b, ch)]
                row["exam_n"] += 1
                if len(row["ex"]) < 4:
                    row["ex"].append(("exam", c["id"], sent.strip()))
            elif da_subject and da:
                row = acc["DADA"][(b, ch)]
                row["da_n"] += 1
                if len(row["ex"]) < 4:
                    row["ex"].append(("da-army", c["id"], sent.strip()))
            elif da and not (da_subject and lesson):
                row = acc["DADA"][(b, ch)]
                row["da_n"] += 1
                if len(row["ex"]) < 4:
                    row["ex"].append(("da-army", c["id"], sent.strip()))
            elif DUEL_CUE.search(sent):
                row = acc["DADA"][(b, ch)]
                row["club_n"] += 1
                if len(row["ex"]) < 4:
                    row["ex"].append(("duel-club", c["id"], sent.strip()))
            if lesson and (char_subject or "Flitwick" in teachers):
                row = acc["Charms"][(b, ch)]
                row["class_n"] += 1
                for t in teachers:
                    row["t"][t] += 1
                if len(row["ex"]) < 4:
                    row["ex"].append(("class", c["id"], sent.strip()))
            elif char_subject and exam:
                row = acc["Charms"][(b, ch)]
                row["exam_n"] += 1
                if len(row["ex"]) < 4:
                    row["ex"].append(("exam", c["id"], sent.strip()))

    def best_tier(row):
        if row["class_n"] >= 2:
            return "class", row["class_n"]
        if row["exam_n"] >= 2:
            return "exam", row["exam_n"]
        if row["da_n"] >= 1:
            return "da-army", row["da_n"]
        if row["club_n"] >= 1:
            return "duel-club", row["club_n"]
        return None, 0

    def lex_seeded() -> dict[tuple[int, int], tuple[int, int]]:
        """(entries with edges, entries with verified candidates) per chapter."""
        path = Path("/Users/tc/Documents/Github/owl-128/data/lexicon/"
                    "canon_index.jsonl")
        if not path.exists():
            return {}
        seen: dict[tuple[int, int], tuple[set, set]] = {}
        for line in path.open(encoding="utf-8"):
            e = json.loads(line)
            if e.get("chapter") is None:
                continue
            key = (e["book"], e["chapter"])
            allk, ver = seen.setdefault(key, (set(), set()))
            allk.add(e["entry_key"])
            if e.get("candidates"):
                ver.add(e["entry_key"])
        return {k: (len(v[0]), len(v[1])) for k, v in seen.items()}

    seeded = lex_seeded()

    with open(OUT, "w", encoding="utf-8") as out:
        out.write("# DADA + Charms lesson-table review (machine proposal)\n\n")
        out.write("tier: class = taught-in-class (decisive); exam = used-in-"
                  "exam-\ncontext (strong); da-army = Dumbledore's Army "
                  "practice; duel-\nclub = Lockhart's dueling club. The two "
                  "practice tiers are recorded\nas author-pick basis (kept on "
                  "scarcity grounds, 2026-11-08\ndecision) - they inform, they "
                  "never define the syllabus.\nKeep or strike each row; "
                  "teacher X = cue-name winner, year\nroster is the DADA "
                  "cross-check. `seeded` = Lexicon entries with\nedges to the "
                  "chapter / entries with hash-verified chunk\ncandidates "
                  "(0/0 rows still stand on book evidence alone).\n\n")
        for subj in ("DADA", "Charms"):
            out.write(f"\n## {subj}\n\n")
            out.write("| keep | chapter | tier | n | teacher (inferred) | "
                      "year roster | seeded | evidence |\n")
            out.write("|---|---|---|---:|---|---|---|---|\n")
            items = sorted(acc[subj].items(), key=lambda x: (x[0][0], x[0][1]))
            quotes = []
            for (b, ch), row in items:
                tier, n = best_tier(row)
                if tier is None:
                    continue
                top_t = row["t"].most_common(1)[0][0] if row["t"] else "?"
                roster = DADA_TEACHERS.get(b, "") if subj == "DADA" else \
                    "Flitwick"
                refs = " ".join(f"`{i+1}.{cid}`"
                                for i, (_, cid, _) in enumerate(row["ex"]))
                s_all, s_ver = seeded.get((b, ch), (0, 0))
                out.write(f"| [ ] | b{b} c{ch} | {tier} | {n} | {top_t} "
                          f"| {roster} | {s_all}/{s_ver} | {refs} |\n")
                for i, (tname, cid, q) in enumerate(row["ex"]):
                    flat = " ".join(q.split())[:140]
                    quotes.append((b, ch, i, tname, cid, flat))
            out.write("\n### Evidence quotes\n\n")
            for b, ch, i, tname, cid, q in quotes:
                out.write(f"- b{b} c{ch} {i+1} [{tname}] `{cid}`: \"{q}\"\n")
            print(f"{subj}: {sum(1 for _, r in items if best_tier(r)[0])} rows")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
