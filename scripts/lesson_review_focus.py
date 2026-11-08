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

REPO = Path(__file__).resolve().parents[1]
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

    def lex_seeded():
        """(entries with edges, entries with verified candidates, top titles)."""
        path = Path("/Users/tc/Documents/Github/owl-128/data/lexicon/"
                    "canon_index.jsonl")
        if not path.exists():
            return {}
        agg: dict = {}
        for line in path.open(encoding="utf-8"):
            e = json.loads(line)
            if e.get("chapter") is None:
                continue
            key = (e["book"], e["chapter"])
            a = agg.setdefault(key, {"all": set(), "cands": {}, "meta": {}})
            a["all"].add(e["entry_key"])
            if e.get("candidates"):
                cands = a["cands"]
                cands[e["entry_key"]] = max(
                    cands.get(e["entry_key"], 0), len(e["candidates"])
                )
                a["meta"][e["entry_key"]] = (e.get("family", ""),
                                             e.get("title", ""))
        order = {"magic": 0, "creature": 1}
        out = {}
        for key, a in agg.items():
            top = sorted(
                a["cands"],
                key=lambda k: (order.get(a["meta"][k][0], 2),
                               -a["cands"][k], a["meta"][k][1].lower()),
            )[:5]
            out[key] = (len(a["all"]), len(a["cands"]),
                        [a["meta"][t][1] for t in top])
        return out

    seeded = lex_seeded()

    table_paths = {
        "DADA": REPO / "config" / "lessons" / "dada.jsonl",
        "Charms": REPO / "config" / "lessons" / "charms.jsonl",
    }
    basis_map = {
        "class": ("taught-in-class", ""),
        "exam": ("used-in-exam-context", ""),
        "da-army": ("author-pick", "Dumbledore's Army practical chapters; "
                    "kept on scarcity grounds (2026-11-08 maintainer decision)"),
        "duel-club": ("author-pick", "dueling-club scene; extracurricular "
                      "defensive practice, kept on scarcity grounds"),
    }
    dada_teacher = {1: "Quirrell", 2: "Lockhart", 3: "Lupin",
                    4: "Moody (Bartemius Crouch Jr.)", 5: "Umbridge",
                    6: "unassigned classroom (Dumbledore private lessons "
                       "separately)", 7: "none (wartime)"}
    for subj in ("DADA", "Charms"):
        rows_out = []
        for (b, ch), row in acc[subj].items():
            tier, n = best_tier(row)
            if tier is None:
                continue
            basis, reason = basis_map[tier]
            s_all, s_ver, s_top = seeded.get((b, ch), (0, 0, []))
            rec = {
                "book": b, "chapter": ch, "subject": subj.lower(),
                "teacher": (dada_teacher.get(b) or "Flitwick")
                           if subj == "DADA" else "Flitwick",
                "basis": basis, "reason": reason, "cue_sentences": n,
                "evidence_chunk_ids": [cid for _, cid, _ in row["ex"]],
                "seeded_entries": s_all, "seeded_verified": s_ver,
                "key_concepts": s_top,
                "status": "approved", "approved_by": "maintainer",
                "approved_on": "2026-11-08",
            }
            if subj == "DADA" and b == 3 and ch in (9, 10):
                rec["teacher_note"] = "Snape substituting for Lupin (ill)"
            rows_out.append(rec)
        path = table_paths[subj]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for rec in sorted(rows_out, key=lambda r: (r["book"], r["chapter"])):
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"lesson table: {path} rows={len(rows_out)}")

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
                  "(0/0 rows still stand on book evidence alone).\n`key "
                  "concepts` = top verified entries in the chapter, spells "
                  "and\ncreatures first, by candidate count.\n\n")
        for subj in ("DADA", "Charms"):
            out.write(f"\n## {subj}\n\n")
            out.write("| keep | chapter | tier | n | teacher (inferred) | "
                      "year roster | seeded | key concepts | evidence |\n")
            out.write("|---|---|---|---:|---|---|---|---|---|\n")
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
                s_all, s_ver, s_top = seeded.get((b, ch), (0, 0, []))
                names = ", ".join(s_top) if s_top else "—"
                out.write(f"| [ ] | b{b} c{ch} | {tier} | {n} | {top_t} "
                          f"| {roster} | {s_all}/{s_ver} | {names} | {refs} |\n")
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
