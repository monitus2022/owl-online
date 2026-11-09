"""Exam-bank records and the deterministic bank validator (#189).

The bank is the content pool a paper is sampled from. It is separate from the
paper and attempt records in #38:

    data/exams/<subject>/
        manifest.toml   bank version, pack/hash pins, generator/judge config, counts
        bank.jsonl      BankItem records

The source of truth is the Pydantic record, not the SQLite serving copy. The
authoring JSONL stays under `/data`; the serving store is built from it by the
importer. A bank item must resolve to a published subject material and to the
book corpus with a current text hash, exactly like a pack material.

Cross-field rules live in `BankItem`; pack, corpus, duplicate and publication
rules live in `validate_bank`. The model boundary rejects malformed records; the
validator rejects a structurally valid record that cannot be published.
"""

from __future__ import annotations

import json
import math
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.knowledge.materials import SourceRef, chunk_text_hash
from app.knowledge.packs import PACK_STATUS, SubjectPack, pack_fingerprint
from app.knowledge.taxonomy import REVIEW_SET, SUBJECT_KEYS, TIER_SET
from app.schemas import Chunk

BANK_KINDS = ("mcq", "short_answer")
DIFFICULTIES = ("recall", "explanation", "application", "comparison", "scenario")
MCQ_MARKS = 3
SHORT_ANSWER_MARKS = 8
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_OPTION_TEXT_RE = re.compile(r"[^a-z0-9]+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_POINT_WORD_RE = re.compile(r"[a-z0-9]{4,}")
_POINT_STOPWORDS = frozenset(
    "about after also because before being between could does each from have into "
    "more most only other should some such than that their them then there these "
    "they this those through under using were what when where which while with "
    "would your".split()
)
_TRIVIAL_OPTIONS = frozenset({"all of the above", "none of the above"})


class _StrictModel(BaseModel):
    """Unknown fields raise; a bank that grows an unreviewed field must fail."""

    model_config = ConfigDict(extra="forbid")


def _id_shape(value: str) -> str:
    if not _ID_RE.match(value):
        raise ValueError(f"identifier must be lowercase [a-z0-9._-], got {value!r}")
    return value


def _non_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must not be blank")
    return value.strip()


def normalise_prompt(value: str) -> str:
    """Normalised prompt for exact duplicate checks."""
    return " ".join(_OPTION_TEXT_RE.sub(" ", value.lower()).split())


def _sentence_count(value: str) -> int:
    return len([part for part in _SENTENCE_SPLIT_RE.split(value.strip()) if part.strip()])


def _word_count(value: str) -> int:
    return len(value.split())


class McqOption(_StrictModel):
    """One option in the stored six-or-more option pool."""

    option_id: str
    text: str

    @field_validator("option_id")
    @classmethod
    def _option_id(cls, value: str) -> str:
        return _id_shape(value)

    @field_validator("text")
    @classmethod
    def _text(cls, value: str) -> str:
        return _non_blank(value)


class RubricCriterion(_StrictModel):
    """One criterion in the item rubric."""

    criterion_id: str
    description: str
    max_marks: int = Field(gt=0)

    @field_validator("criterion_id")
    @classmethod
    def _criterion_id(cls, value: str) -> str:
        return _id_shape(value)

    @field_validator("description")
    @classmethod
    def _description(cls, value: str) -> str:
        return _non_blank(value)


class ShortAnswerKey(_StrictModel):
    """The golden answer, required points and rubric for one short answer."""

    golden_answer: str
    required_points: tuple[str, ...] = Field(min_length=2, max_length=3)
    rubric: tuple[RubricCriterion, ...] = Field(min_length=2)

    @field_validator("golden_answer")
    @classmethod
    def _golden_answer(cls, value: str) -> str:
        return _non_blank(value)

    @field_validator("required_points")
    @classmethod
    def _points(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not point.strip() for point in value):
            raise ValueError("required points must not be blank")
        return tuple(point.strip() for point in value)

    @model_validator(mode="after")
    def _answer_rules(self) -> ShortAnswerKey:
        if not 2 <= _sentence_count(self.golden_answer) <= 3:
            raise ValueError("golden answer must be 2-3 sentences")
        if not 25 <= _word_count(self.golden_answer) <= 80:
            raise ValueError("golden answer must be 25-80 words")
        if not {"correctness", "completeness"} <= {
            criterion.criterion_id for criterion in self.rubric
        }:
            raise ValueError("rubric needs correctness and completeness criteria")
        if sum(criterion.max_marks for criterion in self.rubric) != SHORT_ANSWER_MARKS:
            raise ValueError(f"rubric marks must sum to {SHORT_ANSWER_MARKS}")
        return self


class EvidenceSnapshot(_StrictModel):
    """The chunk evidence captured at generation time."""

    chunk_id: str
    book: int
    chapter: int
    quote: str
    text_hash: str
    index_text_hash: str

    @field_validator("chunk_id")
    @classmethod
    def _chunk_id(cls, value: str) -> str:
        if not re.match(r"^b[1-7]-c\d{2}-\d{4}$", value):
            raise ValueError(f"chunk_id must look like bN-cNN-NNNN, got {value!r}")
        return value

    @field_validator("book")
    @classmethod
    def _book(cls, value: int) -> int:
        if not 1 <= value <= 7:
            raise ValueError("evidence snapshots point at the seven novels only")
        return value

    @field_validator("chapter")
    @classmethod
    def _chapter(cls, value: int) -> int:
        if value < 1:
            raise ValueError("chapter must be positive")
        return value

    @field_validator("quote", "text_hash", "index_text_hash")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        return _non_blank(value)


class BankManifest(_StrictModel):
    """manifest.toml: version, pins and counts for one subject bank."""

    subject: str
    tier: str = "owl"
    version: str
    status: str = "draft"
    built_at: str = ""
    pack_version: str = ""
    pack_fingerprint: str = ""
    index_text_hash: str = ""
    generator_model: str = ""
    generator_prompt_version: str = ""
    judge_model: str = ""
    judge_prompt_version: str = ""
    mcq_count: int = Field(default=0, ge=0)
    short_answer_count: int = Field(default=0, ge=0)

    @field_validator("subject")
    @classmethod
    def _subject(cls, value: str) -> str:
        if value not in SUBJECT_KEYS:
            raise ValueError(f"unknown subject key {value!r}")
        return value

    @field_validator("tier")
    @classmethod
    def _tier(cls, value: str) -> str:
        if value not in TIER_SET:
            raise ValueError(f"tier must be one of {sorted(TIER_SET)}")
        return value

    @field_validator("version")
    @classmethod
    def _version(cls, value: str) -> str:
        return _non_blank(value)

    @field_validator("status")
    @classmethod
    def _status(cls, value: str) -> str:
        if value not in PACK_STATUS:
            raise ValueError(f"bank status must be one of {PACK_STATUS}")
        return value

    @property
    def total_count(self) -> int:
        return self.mcq_count + self.short_answer_count


class BankItem(_StrictModel):
    """One bank question, either MCQ or short answer."""

    item_id: str
    subject: str
    kind: str
    prompt: str
    topic: str
    concepts: tuple[str, ...] = Field(min_length=1)
    material_id: str
    source_refs: tuple[SourceRef, ...] = Field(min_length=1)
    evidence_snapshot: EvidenceSnapshot
    difficulty: str
    marks: int = Field(gt=0)
    rubric: tuple[RubricCriterion, ...] = ()
    required_points: tuple[str, ...] = ()
    model_answer: str | None = None
    options: tuple[McqOption, ...] = ()
    correct_option_id: str | None = None
    rationale: str | None = None
    review_status: str = "draft"
    prompt_version: str
    canon_tier: str = "primary"

    @property
    def short_answer_key(self) -> ShortAnswerKey | None:
        if self.kind != "short_answer" or self.model_answer is None:
            return None
        return ShortAnswerKey(
            golden_answer=self.model_answer,
            required_points=self.required_points,
            rubric=self.rubric,
        )

    @field_validator("item_id", "topic", "material_id")
    @classmethod
    def _ids(cls, value: str) -> str:
        return _id_shape(value)

    @field_validator("subject")
    @classmethod
    def _subject(cls, value: str) -> str:
        if value not in SUBJECT_KEYS:
            raise ValueError(f"unknown subject key {value!r}")
        return value

    @field_validator("kind")
    @classmethod
    def _kind(cls, value: str) -> str:
        if value not in BANK_KINDS:
            raise ValueError(f"kind must be one of {BANK_KINDS}")
        return value

    @field_validator("prompt", "prompt_version")
    @classmethod
    def _prompt(cls, value: str) -> str:
        return _non_blank(value)

    @field_validator("concepts")
    @classmethod
    def _concepts(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("concepts must be unique")
        for concept in value:
            _id_shape(concept)
        return value

    @field_validator("difficulty")
    @classmethod
    def _difficulty(cls, value: str) -> str:
        if value not in DIFFICULTIES:
            raise ValueError(f"difficulty must be one of {DIFFICULTIES}")
        return value

    @field_validator("review_status")
    @classmethod
    def _review(cls, value: str) -> str:
        if value not in REVIEW_SET:
            raise ValueError(f"review_status must be one of {sorted(REVIEW_SET)}")
        return value

    @field_validator("canon_tier")
    @classmethod
    def _canon_tier(cls, value: str) -> str:
        if value != "primary":
            raise ValueError("bank items are exam-gradable primary canon only")
        return value

    @model_validator(mode="after")
    def _kind_rules(self) -> BankItem:
        if self.kind == "mcq":
            if self.marks != MCQ_MARKS:
                raise ValueError(f"MCQ marks must be {MCQ_MARKS}")
            if len(self.options) < 6:
                raise ValueError("MCQ items need at least six options")
            if self.model_answer is not None:
                raise ValueError("MCQ items do not store a model_answer")
            if self.required_points:
                raise ValueError("MCQ items do not store required points")
            if self.correct_option_id is None:
                raise ValueError("MCQ items need correct_option_id")
            option_ids = [option.option_id for option in self.options]
            if len(set(option_ids)) != len(option_ids):
                raise ValueError("option ids must be unique")
            if self.correct_option_id not in option_ids:
                raise ValueError("correct_option_id must name one stored option")
            normalised = [
                _OPTION_TEXT_RE.sub(" ", option.text.lower()).strip()
                for option in self.options
            ]
            if len(set(normalised)) != len(normalised):
                raise ValueError("option texts must be unique")
            if _TRIVIAL_OPTIONS & set(normalised):
                raise ValueError("all-of-the-above and none-of-the-above are not allowed")
        else:
            if self.marks != SHORT_ANSWER_MARKS:
                raise ValueError(f"short-answer marks must be {SHORT_ANSWER_MARKS}")
            if self.options or self.correct_option_id is not None:
                raise ValueError("short-answer items do not store options")
            if self.model_answer is None:
                raise ValueError("short-answer items need a model_answer")
            sentences = _sentence_count(self.model_answer)
            if not 2 <= sentences <= 3:
                raise ValueError("short-answer model_answer must be 2-3 sentences")
            words = _word_count(self.model_answer)
            if not 25 <= words <= 80:
                raise ValueError("short-answer model_answer must be 25-80 words")
            if len(self.rubric) < 2:
                raise ValueError("short-answer items need at least two rubric criteria")
            if not {"correctness", "completeness"} <= {
                criterion.criterion_id for criterion in self.rubric
            }:
                raise ValueError("short-answer rubric needs correctness and completeness criteria")
            if not 2 <= len(self.required_points) <= 3:
                raise ValueError("short-answer items need 2-3 required points")
            if any(not point.strip() for point in self.required_points):
                raise ValueError("required points must not be blank")

        if self.rubric:
            criterion_ids = [criterion.criterion_id for criterion in self.rubric]
            if len(set(criterion_ids)) != len(criterion_ids):
                raise ValueError("rubric criterion ids must be unique")
            if sum(criterion.max_marks for criterion in self.rubric) != self.marks:
                raise ValueError("rubric marks must sum to the item marks")

        snapshot = self.evidence_snapshot.model_dump()
        if not any(
            ref.model_dump(exclude={"citation_bucket"}) == snapshot
            for ref in self.source_refs
        ):
            raise ValueError("evidence_snapshot must match one source_ref")
        return self


class ExamBank(_StrictModel):
    """One subject bank: manifest plus items."""

    manifest: BankManifest
    items: list[BankItem] = Field(default_factory=list)

    def find_item(self, item_id: str) -> BankItem | None:
        return next((item for item in self.items if item.item_id == item_id), None)

    def counts(self) -> dict[str, int]:
        counts = {"mcq": 0, "short_answer": 0}
        for item in self.items:
            counts[item.kind] += 1
        return counts


@dataclass
class BankCoverage:
    """Counts used by the coverage report and the publication gate."""

    per_topic: dict[str, int] = field(default_factory=dict)
    per_topic_kind: dict[str, dict[str, int]] = field(default_factory=dict)
    per_concept: dict[str, int] = field(default_factory=dict)
    by_kind: dict[str, int] = field(default_factory=dict)
    answer_positions: dict[str, int] = field(default_factory=dict)
    total: int = 0


@dataclass
class BankValidation:
    """Result of the pack, corpus, duplicate and publication checks."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    coverage: BankCoverage = field(default_factory=BankCoverage)

    @property
    def ok(self) -> bool:
        return not self.errors


def _read_jsonl(path: Path, model: type[BaseModel]) -> list[BaseModel]:
    rows: list[BaseModel] = []
    if not path.exists():
        return rows
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{path} line {line_number}: invalid JSON: {error}") from error
        try:
            rows.append(model.model_validate(row))
        except Exception as error:
            raise ValueError(f"{path} line {line_number}: {error}") from error
    return rows


def load_exam_bank(directory: Path) -> ExamBank:
    """Read manifest.toml and bank.jsonl; shape errors fail loudly."""
    manifest_path = directory / "manifest.toml"
    if not manifest_path.exists():
        raise ValueError(f"{directory}: missing manifest.toml")
    manifest = BankManifest.model_validate(tomllib.loads(manifest_path.read_text("utf-8")))
    items = _read_jsonl(directory / "bank.jsonl", BankItem)
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, BankItem):
            raise ValueError(f"{directory}: bank.jsonl contains a non-BankItem")
        if item.item_id in seen:
            raise ValueError(f"{directory}: duplicate item id {item.item_id!r}")
        seen.add(item.item_id)
        if item.subject != manifest.subject:
            raise ValueError(f"{directory}: item {item.item_id!r} subject mismatch")
    return ExamBank(manifest=manifest, items=items)


def write_exam_bank(bank: ExamBank, directory: Path) -> None:
    """Serialize a bank to manifest.toml and bank.jsonl, order-stable."""
    directory.mkdir(parents=True, exist_ok=True)
    counts = bank.counts()
    manifest = bank.manifest.model_copy(
        update={
            "mcq_count": counts["mcq"],
            "short_answer_count": counts["short_answer"],
        }
    )
    lines = []
    for name in BankManifest.model_fields:
        lines.append(f"{name} = {json.dumps(getattr(manifest, name), ensure_ascii=False)}")
    (directory / "manifest.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    body = "\n".join(item.model_dump_json() for item in bank.items)
    (directory / "bank.jsonl").write_text(body + "\n" if body else "", encoding="utf-8")


def structure_record(bank: ExamBank, validation: BankValidation) -> str:
    """Structure-only Markdown record: ids and counts, never prompt or quote text."""
    manifest = bank.manifest
    counts = bank.counts()
    lines = [
        f"# Bank record: {manifest.subject} {manifest.version}",
        "",
        f"- Status: `{manifest.status}`",
        f"- Built at: `{manifest.built_at}`",
        f"- Review date: `{manifest.built_at[:10]}`",
        f"- Pack: `{manifest.pack_version}` / `{manifest.pack_fingerprint}`",
        f"- Index text hash: `{manifest.index_text_hash}`",
        f"- Generator: `{manifest.generator_model}` / `{manifest.generator_prompt_version}`",
        f"- Judge: `{manifest.judge_model}` / `{manifest.judge_prompt_version}`",
        f"- Items: {sum(counts.values())} ({counts['mcq']} MCQ, "
        f"{counts['short_answer']} short answer)",
        f"- Validation: ok={validation.ok} errors={len(validation.errors)} "
        f"warnings={len(validation.warnings)}",
        "",
        "## Topic coverage",
        "",
        "| Topic | MCQ | Short answer |",
        "|---|---:|---:|",
    ]
    for topic, counts in sorted(validation.coverage.per_topic_kind.items()):
        lines.append(f"| `{topic}` | {counts.get('mcq', 0)} | {counts.get('short_answer', 0)} |")
    lines.extend(
        [
            "",
            "## Concept coverage",
            "",
            "| Concept | Items |",
            "|---|---:|",
        ]
    )
    for concept, count in sorted(validation.coverage.per_concept.items()):
        lines.append(f"| `{concept}` | {count} |")
    lines.extend(
        [
            "",
            "## Answer positions",
            "",
            "| Stored index | MCQs |",
            "|---|---:|",
        ]
    )
    for position, count in sorted(validation.coverage.answer_positions.items()):
        lines.append(f"| {position} | {count} |")
    lines.extend(
        [
            "",
            "## Items",
            "",
            "| Item | Kind | Topic | Material | Review |",
            "|---|---|---|---|---|",
        ]
    )
    for item in sorted(bank.items, key=lambda row: row.item_id):
        lines.append(
            f"| `{item.item_id}` | {item.kind} | `{item.topic}` | "
            f"`{item.material_id}` | {item.review_status} |"
        )
    lines.extend(
        [
            "",
            "## Validation summary",
            "",
            f"- Errors: {len(validation.errors)}",
            f"- Warnings: {len(validation.warnings)}",
            "- Detailed messages stay in the CLI output; this record is structure only.",
            "",
        ]
    )
    return "\n".join(lines)


def _point_supported(point: str, material_text: str, evidence_quote: str) -> bool:
    """Cheap lexical support check; the authoring verifier does the semantic pass."""
    point_words = {
        word for word in _POINT_WORD_RE.findall(point.lower())
        if word not in _POINT_STOPWORDS
    }
    source_words = set(_POINT_WORD_RE.findall(f"{material_text} {evidence_quote}".lower()))
    return bool(point_words & source_words)


def _check_source_ref(ref: SourceRef, chunks: dict[str, Chunk], index_text_hash: str) -> list[str]:
    problems: list[str] = []
    if ref.index_text_hash != index_text_hash:
        problems.append(f"index hash {ref.index_text_hash!r} != current {index_text_hash!r}")
    chunk = chunks.get(ref.chunk_id)
    if chunk is None:
        problems.append(f"chunk {ref.chunk_id} not in corpus")
        return problems
    if chunk_text_hash(chunk.text) != ref.text_hash:
        problems.append(f"chunk {ref.chunk_id} text hash mismatch")
    if ref.quote not in chunk.text:
        problems.append(f"quote not found in chunk {ref.chunk_id}")
    meta = chunk.metadata
    if (meta.book_num, meta.chapter_num) != (ref.book, ref.chapter):
        problems.append(
            f"ref points at book {ref.book} chapter {ref.chapter} but the chunk is "
            f"book {meta.book_num} chapter {meta.chapter_num}"
        )
    return problems


def validate_bank(
    bank: ExamBank,
    pack: SubjectPack,
    chunks: dict[str, Chunk],
    index_text_hash: str,
) -> BankValidation:
    """Check pack membership, corpus hashes, duplicates and publication state."""
    result = BankValidation()
    coverage = BankCoverage()
    manifest = bank.manifest
    if pack.manifest.status != "published":
        result.errors.append("source pack is not published")
    if manifest.subject != pack.manifest.subject:
        result.errors.append("manifest subject differs from the pack")
    if manifest.tier != pack.manifest.tier:
        result.errors.append("manifest tier differs from the pack")
    if manifest.pack_version != pack.manifest.version:
        result.errors.append(
            f"manifest pack_version {manifest.pack_version!r} != pack {pack.manifest.version!r}"
        )
    if manifest.pack_fingerprint != pack_fingerprint(pack):
        result.errors.append("manifest pack_fingerprint is stale")
    if manifest.index_text_hash != index_text_hash:
        result.errors.append("manifest index_text_hash is stale")

    counts = bank.counts()
    if manifest.mcq_count != counts["mcq"]:
        result.errors.append(
            f"manifest mcq_count {manifest.mcq_count} != actual {counts['mcq']}"
        )
    if manifest.short_answer_count != counts["short_answer"]:
        result.errors.append(
            f"manifest short_answer_count {manifest.short_answer_count} != actual "
            f"{counts['short_answer']}"
        )
    if manifest.status == "published" and not bank.items:
        result.errors.append("published bank has no items")
    if manifest.status == "published":
        if not manifest.built_at.strip():
            result.errors.append("published bank has no built_at")
        if not manifest.generator_model.strip():
            result.errors.append("published bank has no generator model")
        if not manifest.generator_prompt_version.strip():
            result.errors.append("published bank has no generator prompt version")
        if not manifest.judge_model.strip():
            result.errors.append("published bank has no judge model")
        if not manifest.judge_prompt_version.strip():
            result.errors.append("published bank has no judge prompt version")

    topic_ids = {topic.topic_id for topic in pack.topics}
    concept_ids = {concept.concept_id for concept in pack.concepts}
    materials = {material.material_id: material for material in pack.materials}
    seen_ids: set[str] = set()
    seen_prompts: dict[str, str] = {}

    for item in bank.items:
        if item.item_id in seen_ids:
            result.errors.append(f"duplicate item id {item.item_id!r}")
        seen_ids.add(item.item_id)
        if item.subject != manifest.subject:
            result.errors.append(f"{item.item_id}: subject differs from the manifest")
        if item.topic not in topic_ids:
            result.errors.append(f"{item.item_id}: unknown topic {item.topic!r}")
        for concept in item.concepts:
            if concept not in concept_ids:
                result.errors.append(f"{item.item_id}: unknown concept {concept!r}")
        material = materials.get(item.material_id)
        if material is None:
            result.errors.append(f"{item.item_id}: unknown material {item.material_id!r}")
        else:
            if material.review_status != "reviewed":
                result.errors.append(f"{item.item_id}: cited material is not reviewed")
            if item.topic != material.topic:
                result.errors.append(
                    f"{item.item_id}: topic {item.topic!r} != material topic {material.topic!r}"
                )
            if material.concept not in item.concepts:
                result.errors.append(
                    f"{item.item_id}: material concept {material.concept!r} "
                    "is not in item concepts"
                )
            material_chunks = {ref.chunk_id for ref in material.source_refs}
            for ref in item.source_refs:
                if ref.chunk_id not in material_chunks:
                    result.errors.append(
                        f"{item.item_id}: source ref {ref.chunk_id} is not in the material"
                    )
            for point in item.required_points:
                if not _point_supported(
                    point,
                    material.text,
                    item.evidence_snapshot.quote,
                ):
                    result.errors.append(
                        f"{item.item_id}: required point is not supported by the material: "
                        f"{point!r}"
                    )
        if not item.source_refs:
            result.errors.append(f"{item.item_id}: no source refs")
        for ref in item.source_refs:
            for problem in _check_source_ref(ref, chunks, index_text_hash):
                result.errors.append(f"{item.item_id} {ref.chunk_id}: {problem}")
            if len(ref.quote.split()) < 3:
                result.warnings.append(f"{item.item_id} {ref.chunk_id}: quote under three words")
        snapshot = item.evidence_snapshot.model_dump()
        if not any(
            ref.model_dump(exclude={"citation_bucket"}) == snapshot
            for ref in item.source_refs
        ):
            result.errors.append(f"{item.item_id}: evidence_snapshot does not match a source_ref")
        normalised = normalise_prompt(item.prompt)
        other = seen_prompts.get(normalised)
        if other is not None:
            result.errors.append(f"{item.item_id}: duplicate prompt of {other}")
        else:
            seen_prompts[normalised] = item.item_id
        if item.review_status != "reviewed":
            if manifest.status == "published":
                result.errors.append(f"{item.item_id}: unreviewed item in a published bank")
            else:
                result.warnings.append(f"{item.item_id}: review_status={item.review_status}")
        coverage.per_topic[item.topic] = coverage.per_topic.get(item.topic, 0) + 1
        topic_kind = coverage.per_topic_kind.setdefault(item.topic, {})
        topic_kind[item.kind] = topic_kind.get(item.kind, 0) + 1
        for concept in item.concepts:
            coverage.per_concept[concept] = coverage.per_concept.get(concept, 0) + 1
        coverage.by_kind[item.kind] = coverage.by_kind.get(item.kind, 0) + 1
        if item.kind == "mcq" and item.correct_option_id is not None:
            position = next(
                (
                    index
                    for index, option in enumerate(item.options)
                    if option.option_id == item.correct_option_id
                ),
                None,
            )
            if position is not None:
                coverage.answer_positions[str(position)] = (
                    coverage.answer_positions.get(str(position), 0) + 1
                )

    coverage.total = len(bank.items)
    for topic in sorted(topic_ids):
        coverage.per_topic.setdefault(topic, 0)
        coverage.per_topic_kind.setdefault(topic, {})
    for concept in sorted(concept_ids):
        coverage.per_concept.setdefault(concept, 0)

    mcq_total = coverage.by_kind.get("mcq", 0)
    if mcq_total >= 5:
        cap = max(1, math.ceil(mcq_total * 0.4))
        for position, count in sorted(coverage.answer_positions.items()):
            if count > cap:
                message = (
                    f"answer position {position} holds {count} of {mcq_total} MCQs; "
                    f"cap is {cap}"
                )
                if manifest.status == "published":
                    result.errors.append(message)
                else:
                    result.warnings.append(message)
    result.coverage = coverage
    return result


__all__ = [
    "BANK_KINDS",
    "BankCoverage",
    "BankItem",
    "BankManifest",
    "BankValidation",
    "DIFFICULTIES",
    "EvidenceSnapshot",
    "ExamBank",
    "MCQ_MARKS",
    "McqOption",
    "RubricCriterion",
    "SHORT_ANSWER_MARKS",
    "ShortAnswerKey",
    "load_exam_bank",
    "normalise_prompt",
    "structure_record",
    "validate_bank",
    "write_exam_bank",
]
