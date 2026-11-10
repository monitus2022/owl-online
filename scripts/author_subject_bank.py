"""Author a subject exam bank on a published subject pack.

The item batch lives in the committed `config/banks/<subject>.json`; each item
cites one reviewed material, reuses that material's books-bucket source refs,
and is validated by `app.exam.bank.validate_bank` against the current corpus
index hash. Evidence quotes are never invented; they come from the pack's
hash-checked refs.

Items are concept-only. Neither the prompt nor the golden answer may name a
character, house, book or scene, and a student must not need story knowledge to
answer. The batch also rejects exam-administration and classroom-pedagogy
questions. `_check_prose` enforces the denylist before the bank is written.

    uv run python scripts/author_subject_bank.py potions
    uv run python scripts/author_subject_bank.py potions --mark-reviewed
    uv run python scripts/author_subject_bank.py potions --publish
    uv run python scripts/author_subject_bank.py potions --mark-reviewed --publish --force
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.exam.bank import (  # noqa: E402
    BankItem,
    BankManifest,
    EvidenceSnapshot,
    ExamBank,
    McqOption,
    RubricCriterion,
    validate_bank,
    write_exam_bank,
)
from app.knowledge.packs import load_subject_pack, pack_fingerprint  # noqa: E402
from app.pipeline.index.builder import load_chunks, text_hash  # noqa: E402

SUBJECT = ""
DRAFT_VERSION = "0.1.0"
PUBLISH_VERSION = "1.0.0"
OUT = REPO / "data" / "exams"
INPUT = REPO / "config" / "banks" / "subject.json"
PROMPT_VERSION = ""
GENERATOR_MODEL = "deepseek/deepseek-v4.1-flash"
JUDGE_MODEL = "mistralai/mistral-small-3.2-24b-instruct"
JUDGE_PROMPT_VERSION = "owl-bank-judge-v3"

ITEMS: list[dict] = []

def _words(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.lower())


def _longest_common_run(left: str, right: str) -> int:
    """Longest contiguous word run shared by two spans."""
    first, second = _words(left), _words(right)
    best = 0
    previous = [0] * (len(second) + 1)
    for word in first:
        current = [0] * (len(second) + 1)
        for index, other in enumerate(second, 1):
            if word == other:
                current[index] = previous[index - 1] + 1
                best = max(best, current[index])
        previous = current
    return best


def _check_quote_overlap(
    items: list[BankItem], chunks: dict[str, object], limit: int = 7
) -> list[str]:
    """Reject item prose that copies a long run from its source chunk."""
    problems: list[str] = []
    for item in items:
        prose = " ".join(
            [
                item.prompt,
                item.model_answer or "",
                item.rationale or "",
                " ".join(option.text for option in item.options),
                " ".join(criterion.description for criterion in item.rubric),
            ]
        )
        for ref in item.source_refs:
            chunk = chunks.get(ref.chunk_id)
            if chunk is None:
                problems.append(f"{item.item_id}: unresolved chunk {ref.chunk_id}")
                continue
            run = _longest_common_run(prose, chunk.text)
            if run >= limit:
                problems.append(
                    f"{item.item_id}: {run}-word run copied from {ref.chunk_id}"
                )
                break
    return problems


def _validate_specs() -> None:
    seen: set[str] = set()
    for spec in ITEMS:
        if spec["item_id"] in seen:
            raise SystemExit(f"duplicate item id in ITEMS: {spec['item_id']}")
        seen.add(spec["item_id"])
        if spec["kind"] == "mcq":
            if len(spec["options"]) < 6:
                raise SystemExit(f"{spec['item_id']}: needs at least six options")
            if not 0 <= spec["correct"] < len(spec["options"]):
                raise SystemExit(f"{spec['item_id']}: correct index out of range")
        elif spec["kind"] == "short_answer":
            if len(spec["rubric"]) < 2:
                raise SystemExit(f"{spec['item_id']}: needs two rubric criteria")
            if sum(marks for _, _, marks in spec["rubric"]) != 8:
                raise SystemExit(f"{spec['item_id']}: rubric must sum to 8")
            answer = spec["model_answer"].lower()
            for point in spec["required_points"]:
                if point.lower() not in answer:
                    raise SystemExit(
                        f"{spec['item_id']}: required point {point!r} is missing "
                        "from the golden answer"
                    )
        _check_prose(spec)


# Concept-only rule: prompts, keys, options and rubrics must never need story
# knowledge. Names and scene markers are rejected rather than reviewed.
_FORBIDDEN_CHARACTERS = (
    "harry", "ron", "hermione", "malfoy", "neville", "seamus", "cedric",
    "ollivander", "tonks", "angelina", "bagman", "dumbledore", "hagrid",
    "krum", "fleur", "goyle", "crabbe", "flitwick", "mcgonagall", "snape",
    "dolohov", "ginny", "george", "fred", "luna", "sirius", "lupin",
    "voldemort", "quirrell", "lockhart", "umbridge", "slughorn", "crouch",
    "fudge", "skeeter", "cho", "dean", "lavender", "parvati", "dobby",
    "kreacher", "buckbeak", "hedwig", "crookshanks", "scabbers", "norbert",
    "aragog", "myrtle", "filch", "trelawney", "baruffio", "bellatrix",
    "lucius", "narcissa", "pettigrew", "wormtail", "moody", "kingsley",
    "shacklebolt", "pomfrey", "sprout", "vector", "binns", "hooch",
    "dudley", "vernon", "petunia", "riddle", "aberforth", "regulus",
    "karkaroff", "maxime", "grindelwald", "parkinson", "zabini", "chang",
    "diggory", "johnson", "spinnet", "alicia", "katie",
    "percy", "bill", "charlie", "arthur", "molly", "nymphadora",
)
_FORBIDDEN_HOUSES = ("gryffindor", "slytherin", "ravenclaw", "hufflepuff")
_FORBIDDEN_SCENES = (
    "privet drive", "third-floor", "duelling club", "bathroom", "train "
    "compartment", "quidditch", "triwizard", "grimmauld", "ministry of magic",
    "little whinging", "diagon alley", "hogwarts", "d.a.", "dumbledore's army",
    "chamber of secrets", "room of requirement", "burrow", "spinner's end",
    "library", "great hall", "whomping willow", "forbidden forest", "azkaban",
    "hogsmeade", "hogwarts express", "platform nine", "leaky cauldron",
    "gringotts", "shrieking shack", "department of mysteries",
    "quidditch pitch", "malfoy manor", "godric's hollow", "little hangleton",
    "philosopher's stone", "sorcerer's stone", "prisoner of azkaban",
    "goblet of fire", "order of the phoenix", "half-blood prince",
    "deathly hallows",
)
# Exam administration and classroom pedagogy are not charm concepts. A paper
# that asks about the exam while the student is sitting it is a bad item.
_FORBIDDEN_PEDAGOGY = (
    "exam", "exams", "lesson", "lessons", "classroom", "syllabus", "revision",
    "curriculum", "student", "students", "teacher", "teachers", "pupil",
    "pupils", "paper", "papers", "school", "professor", "taught", "homework",
    "schoolwork", "practical examination", "written paper", "theory paper",
    "task", "penalty", "mirror", "eyebrow", "learning", "theory", "advanced",
    "beginner", "introduced",
)


def _check_prose(spec: dict) -> None:
    """Reject a character name or scene marker anywhere student-facing."""
    fields: list[tuple[str, str]] = [
        ("prompt", spec["prompt"]),
        ("rationale", spec.get("rationale") or ""),
    ]
    fields.extend(
        (f"options[{index}]", text)
        for index, text in enumerate(spec.get("options", []))
    )
    fields.extend(
        (f"required_points[{index}]", point)
        for index, point in enumerate(spec.get("required_points", []))
    )
    fields.extend(
        (f"rubric[{criterion_id}]", description)
        for criterion_id, description, _ in spec.get("rubric", [])
    )
    if spec.get("model_answer"):
        fields.append(("model_answer", spec["model_answer"]))
    for name, value in fields:
        lowered = value.lower()
        for term in _FORBIDDEN_CHARACTERS:
            if re.search(rf"\b{re.escape(term)}\b", lowered):
                raise SystemExit(
                    f"{spec['item_id']}: {name} names a character ({term!r}); "
                    "questions must stand without story knowledge"
                )
        for term in _FORBIDDEN_HOUSES:
            if re.search(rf"\b{re.escape(term)}\b", lowered):
                raise SystemExit(
                    f"{spec['item_id']}: {name} names a house ({term!r}); "
                    "questions must stand without story knowledge"
                )
        for term in _FORBIDDEN_SCENES:
            if term in lowered:
                raise SystemExit(
                    f"{spec['item_id']}: {name} refers to a scene ({term!r}); "
                    "questions must stand without story knowledge"
                )
        for term in _FORBIDDEN_PEDAGOGY:
            if re.search(rf"\b{re.escape(term)}\b", lowered):
                raise SystemExit(
                    f"{spec['item_id']}: {name} asks about exams or teaching "
                    f"({term!r}); items test charm concepts only"
                )


def _build_item(spec: dict, material, mark_reviewed: bool, position: int = 0) -> BankItem:
    option_ids = "abcdef"
    common = {
        "item_id": spec["item_id"],
        "subject": SUBJECT,
        "kind": spec["kind"],
        "prompt": spec["prompt"],
        "topic": material.topic,
        "concepts": (material.concept,),
        "material_id": spec["material_id"],
        "source_refs": material.source_refs,
        "evidence_snapshot": EvidenceSnapshot(
            **{
                key: value
                for key, value in material.source_refs[0].model_dump().items()
                if key != "citation_bucket"
            }
        ),
        "difficulty": spec["difficulty"],
        "rationale": spec.get("rationale"),
        "review_status": "reviewed" if mark_reviewed else "draft",
        "prompt_version": PROMPT_VERSION,
    }
    if spec["kind"] == "mcq":
        ordered = list(spec["options"])
        correct_text = ordered.pop(spec["correct"])
        ordered.insert(position, correct_text)
        options = tuple(
            McqOption(option_id=option_ids[index], text=text)
            for index, text in enumerate(ordered)
        )
        return BankItem(
            **common,
            marks=3,
            options=options,
            correct_option_id=option_ids[position],
        )
    rubric = tuple(
        RubricCriterion(criterion_id=criterion_id, description=description, max_marks=marks)
        for criterion_id, description, marks in spec["rubric"]
    )
    return BankItem(
        **common,
        marks=8,
        model_answer=spec["model_answer"],
        required_points=tuple(spec["required_points"]),
        rubric=rubric,
    )


def main() -> int:
    global SUBJECT, OUT, INPUT, ITEMS, PROMPT_VERSION
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "subject", choices=["potions", "transfiguration", "herbology"]
    )
    parser.add_argument("--mark-reviewed", action="store_true")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    SUBJECT = args.subject
    OUT = REPO / "data" / "exams" / SUBJECT
    INPUT = REPO / "config" / "banks" / f"{SUBJECT}.json"
    PROMPT_VERSION = f"{SUBJECT}-bank-authoring-v1"
    if not INPUT.exists():
        print(f"item batch not found at {INPUT}", file=sys.stderr)
        return 1
    ITEMS = json.loads(INPUT.read_text(encoding="utf-8"))["items"]
    publish = args.publish
    mark_reviewed = args.mark_reviewed
    force = args.force
    _validate_specs()

    pack = load_subject_pack(REPO / "data" / "subjects" / SUBJECT)
    chunks = load_chunks(REPO / "data" / "chunks.jsonl")
    index_hash = text_hash(chunks)
    by_id = {chunk.id: chunk for chunk in chunks}
    materials = {material.material_id: material for material in pack.materials}

    if OUT.joinpath("manifest.toml").exists() and not force:
        import tomllib

        existing = tomllib.loads(OUT.joinpath("manifest.toml").read_text("utf-8"))
        if existing.get("status") == "published":
            print(
                f"{OUT} holds a published bank; pass --force to rebuild it as a draft",
                file=sys.stderr,
            )
            return 1

    items: list[BankItem] = []
    mcq_seen = 0
    for spec in ITEMS:
        material = materials.get(spec["material_id"])
        if material is None:
            raise SystemExit(f"{spec['item_id']}: unknown material {spec['material_id']!r}")
        position = mcq_seen % 6 if spec["kind"] == "mcq" else 0
        if spec["kind"] == "mcq":
            mcq_seen += 1
        items.append(_build_item(spec, material, mark_reviewed, position))

    overlap = _check_quote_overlap(items, by_id)
    if overlap:
        for problem in overlap:
            print(f"error: {problem}", file=sys.stderr)
        print("not writing the bank: item prose copies its evidence", file=sys.stderr)
        return 1

    if publish:
        unreviewed = [item.item_id for item in items if item.review_status != "reviewed"]
        if unreviewed:
            print(
                "cannot publish unreviewed items: "
                + ", ".join(unreviewed[:5])
                + (" ..." if len(unreviewed) > 5 else "")
                + "; run --mark-reviewed after the maintainer review",
                file=sys.stderr,
            )
            return 1

    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    counts = {"mcq": sum(1 for item in items if item.kind == "mcq"),
              "short_answer": sum(1 for item in items if item.kind == "short_answer")}
    manifest = BankManifest(
        subject=SUBJECT,
        tier=pack.manifest.tier,
        version=PUBLISH_VERSION if publish else DRAFT_VERSION,
        status="published" if publish else "draft",
        built_at=now,
        reviewed_at=now if publish else "",
        pack_version=pack.manifest.version,
        pack_fingerprint=pack_fingerprint(pack),
        index_text_hash=index_hash,
        generator_model=GENERATOR_MODEL,
        generator_temperature=0.0,
        generator_prompt_version=PROMPT_VERSION,
        judge_model=JUDGE_MODEL,
        judge_temperature=0.0,
        judge_prompt_version=JUDGE_PROMPT_VERSION,
        mcq_count=counts["mcq"],
        short_answer_count=counts["short_answer"],
    )
    bank = ExamBank(manifest=manifest, items=items)
    validation = validate_bank(bank, pack, by_id, index_hash)

    print(
        f"bank {manifest.version} status={manifest.status} "
        f"mcq={counts['mcq']} short_answer={counts['short_answer']}"
    )
    print(f"pack {pack.manifest.version} fingerprint={manifest.pack_fingerprint}")
    for warning in validation.warnings:
        print(f"warning: {warning}")
    for error in validation.errors:
        print(f"error: {error}")
    if not validation.ok:
        print("not writing the bank: validation failed")
        return 1

    write_exam_bank(bank, OUT)
    print(f"wrote {OUT}")
    print(
        "coverage: "
        + ", ".join(
            f"{topic}={sum(kind.values())}"
            for topic, kind in sorted(validation.coverage.per_topic_kind.items())
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
