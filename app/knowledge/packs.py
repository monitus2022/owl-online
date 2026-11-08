"""Subject packs: versioned, validated stores of material per subject.

On-disk layout (`data/subjects/<subject>/`, gitignored like the corpus):

    pack.toml          manifest: version, status, built_at, index_text_hash
    topics.jsonl       Topic records
    concepts.jsonl     Concept records (the items, with aliases)
    materials.jsonl    Material records (the grounded text + source refs)

`load_subject_pack` reads the directory and fails loudly on shape errors,
following the lore pack's discipline (a broken pack must stop the app, not
produce a quietly wrong answer).

Validation is a deterministic corpus join (`docs/workplan.md`, B1 exit
criteria): every material resolves to existing chunks with matching text
hashes; every material has at least one source ref; no orphan concepts; a
`published` pack requires all-reviewed, all-valid material. Coverage per
topic is reported so a thin subject shows up in the report instead of being
padded with non-canonical material.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.knowledge.materials import Material, chunk_text_hash
from app.knowledge.taxonomy import KIND_SET, SUBJECT_KEYS, TIER_SET, known_subject
from app.schemas import Chunk

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

logger = logging.getLogger(__name__)

PACK_STATUS = ("draft", "validated", "published")


class _StrictModel(BaseModel):
    """Unknown fields raise: a pack that grows a prose field must fail
    loudly, the same discipline as `app.knowledge.materials`."""

    model_config = ConfigDict(extra="forbid")


class Topic(_StrictModel):
    """A subject topic, optionally under a parent topic."""

    topic_id: str
    subject: str
    title: str
    tier: str = "owl"
    parent: str | None = None

    @field_validator("topic_id")
    @classmethod
    def _shape(cls, value: str) -> str:
        if not _ID_RE.match(value):
            raise ValueError(f"topic_id must be lowercase [a-z0-9._-], got {value!r}")
        return value

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("topic title must not be blank")
        return value.strip()

    @field_validator("tier")
    @classmethod
    def _tier(cls, value: str) -> str:
        if value not in TIER_SET:
            raise ValueError(f"tier must be one of {sorted(TIER_SET)}")
        return value


class Concept(_StrictModel):
    """An item the syllabus names: spell, potion, creature, event, and so on."""

    concept_id: str
    subject: str
    kind: str
    title: str
    aliases: tuple[str, ...] = ()

    @field_validator("concept_id")
    @classmethod
    def _shape(cls, value: str) -> str:
        if not _ID_RE.match(value):
            raise ValueError(f"concept_id must be lowercase [a-z0-9._-], got {value!r}")
        return value

    @field_validator("kind")
    @classmethod
    def _kind(cls, value: str) -> str:
        if value not in KIND_SET:
            raise ValueError(f"kind must be one of {sorted(KIND_SET)}")
        return value

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("concept title must not be blank")
        return value.strip()


class PackManifest(_StrictModel):
    """pack.toml contents."""

    subject: str
    tier: str = "owl"
    version: str
    status: str = "draft"
    built_at: str = ""
    index_text_hash: str = ""

    @field_validator("subject")
    @classmethod
    def _subject_known(cls, value: str) -> str:
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
        if not value.strip():
            raise ValueError("pack version must not be blank")
        return value

    @field_validator("status")
    @classmethod
    def _status(cls, value: str) -> str:
        if value not in PACK_STATUS:
            raise ValueError(f"pack status must be one of {PACK_STATUS}")
        return value


class SubjectPack(_StrictModel):
    """One subject's full pack."""

    manifest: PackManifest
    topics: list[Topic] = Field(default_factory=list)
    concepts: list[Concept] = Field(default_factory=list)
    materials: list[Material] = Field(default_factory=list)

    def find_material(self, material_id: str) -> Material | None:
        return next((m for m in self.materials if m.material_id == material_id), None)

    def concept_ids(self) -> set[str]:
        return {c.concept_id for c in self.concepts}


def _read_jsonl[ModelT: BaseModel](path: Path, model: type[ModelT]) -> list[ModelT]:
    rows: list[ModelT] = []
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


def load_subject_pack(directory: Path) -> SubjectPack:
    """Read and validate a subject pack directory: shape errors fail loudly.

    Corpus resolution is a separate step (`validate_pack`), so loading a pack
    never needs the index present.
    """
    manifest_path = directory / "pack.toml"
    if not manifest_path.exists():
        raise ValueError(f"{directory}: missing pack.toml")
    manifest = PackManifest.model_validate(tomllib.loads(manifest_path.read_text("utf-8")))
    if known_subject(manifest.subject) is None:
        raise ValueError(f"{directory}: unknown subject {manifest.subject!r}")
    topics = _read_jsonl(directory / "topics.jsonl", Topic)
    concepts = _read_jsonl(directory / "concepts.jsonl", Concept)
    materials = _read_jsonl(directory / "materials.jsonl", Material)

    for records, label, key in ((topics, "topic", "topic_id"), (concepts, "concept", "concept_id")):
        seen: set[str] = set()
        for record in records:
            identifier = getattr(record, key)
            if identifier in seen:
                raise ValueError(f"{directory}: duplicate {label} {identifier!r}")
            seen.add(identifier)
            if record.subject != manifest.subject:
                raise ValueError(f"{directory}: {label} {identifier!r} subject mismatch")
    seen_materials: set[str] = set()
    topic_ids = {t.topic_id for t in topics}
    concept_ids = {c.concept_id for c in concepts}
    for material in materials:
        if material.material_id in seen_materials:
            raise ValueError(f"{directory}: duplicate material {material.material_id!r}")
        seen_materials.add(material.material_id)
        if material.subject != manifest.subject:
            raise ValueError(f"{directory}: material subject mismatch {material.material_id!r}")
        if material.topic not in topic_ids:
            raise ValueError(f"{directory}: material {material.material_id!r} cites unknown topic")
        if material.concept not in concept_ids:
            raise ValueError(
                f"{directory}: material {material.material_id!r} cites unknown concept"
            )
    return SubjectPack(manifest=manifest, topics=topics, concepts=concepts, materials=materials)


@dataclass
class Coverage:
    """Materials and validated refs per topic; drives the thin-subject report."""

    per_topic: dict[str, int] = field(default_factory=dict)
    per_topic_with_source: dict[str, int] = field(default_factory=dict)
    concepts_without_material: list[str] = field(default_factory=list)
    total_materials: int = 0
    valid_materials: int = 0


@dataclass
class PackValidation:
    """Result of a deterministic pack + corpus validation pass."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    coverage: Coverage = field(default_factory=Coverage)

    @property
    def ok(self) -> bool:
        return not self.errors


def index_chunks(chunks: Iterable[Chunk]) -> dict[str, Chunk]:
    """Chunk id -> chunk, for the corpus join. Later duplicates would
    overwrite; chunk ids are unique by construction, and the loader for
    chunks.jsonl is the corpus owner."""
    return {chunk.id: chunk for chunk in chunks}


def validate_pack(
    pack: SubjectPack,
    chunks: dict[str, Chunk],
    index_text_hash: str,
) -> PackValidation:
    """Check the B1 exit rules against the corpus.

    - every material has at least one source ref;
    - every source ref resolves to an existing chunk whose recomputed text
      hash matches, whose quote occurs in the chunk, and whose book and
      chapter match the chunk metadata;
    - refs built against a different index hash are stale by design;
    - no orphan concepts (every concept has at least one material);
    - a published pack must be fully reviewed and error-free.
    """
    result = PackValidation()
    coverage = Coverage(total_materials=len(pack.materials))
    # Every topic appears in the report, even with zero materials: thin must
    # be distinguishable from empty.
    for topic in pack.topics:
        coverage.per_topic.setdefault(topic.topic_id, 0)
        if topic.subject != pack.manifest.subject:
            result.errors.append(f"topic {topic.topic_id}: subject differs from the pack manifest")
        if topic.parent is not None and topic.parent not in {t.topic_id for t in pack.topics}:
            result.errors.append(f"topic {topic.topic_id}: unknown parent {topic.parent!r}")
    topic_ids = {t.topic_id for t in pack.topics}
    concept_ids = {c.concept_id for c in pack.concepts}
    concept_kinds = {c.concept_id: c.kind for c in pack.concepts}
    for concept in pack.concepts:
        if concept.subject != pack.manifest.subject:
            result.errors.append(
                f"concept {concept.concept_id}: subject differs from the pack manifest"
            )
    for material in pack.materials:
        if material.subject != pack.manifest.subject:
            result.errors.append(
                f"{material.material_id}: subject differs from the pack manifest"
            )
        if material.topic not in topic_ids:
            result.errors.append(f"{material.material_id}: cites unknown topic {material.topic!r}")
        if material.concept not in concept_ids:
            result.errors.append(
                f"{material.material_id}: cites unknown concept {material.concept!r}"
            )
        elif concept_kinds[material.concept] != material.kind:
            result.errors.append(
                f"{material.material_id}: kind {material.kind!r} != concept kind "
                f"{concept_kinds[material.concept]!r}"
            )
        coverage.per_topic[material.topic] = coverage.per_topic.get(material.topic, 0) + 1
        if material.source_refs and material.canon_tier != "primary":
            # The anti-padding guard: only the seven novels ground a material.
            result.errors.append(
                f"{material.material_id}: canon_tier={material.canon_tier!r} may not carry "
                "source refs; only primary material is exam-gradable"
            )
        if not material.source_refs:
            result.errors.append(f"{material.material_id}: no source refs")
            continue
        refs_ok = 0
        for ref in material.source_refs:
            problems: list[str] = []
            if ref.index_text_hash != index_text_hash:
                problems.append(
                    f"index hash {ref.index_text_hash!r} != current {index_text_hash!r}"
                )
            chunk = chunks.get(ref.chunk_id)
            if chunk is None:
                problems.append(f"chunk {ref.chunk_id} not in corpus")
            else:
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
            if problems:
                message = "; ".join(problems)
                result.errors.append(f"{material.material_id} {ref.chunk_id}: {message}")
            else:
                if len(ref.quote.split()) < 3:
                    result.warnings.append(
                        f"{material.material_id} {ref.chunk_id}: quote under three words"
                    )
                refs_ok += 1
        if refs_ok:
            coverage.per_topic_with_source[material.topic] = (
                coverage.per_topic_with_source.get(material.topic, 0) + 1
            )
            coverage.valid_materials += 1
        if material.review_status != "reviewed":
            status = material.review_status
            result.warnings.append(f"{material.material_id}: review_status={status}")
    used_concepts = {m.concept for m in pack.materials}
    coverage.concepts_without_material = sorted(pack.concept_ids() - used_concepts)
    for concept in coverage.concepts_without_material:
        result.errors.append(f"orphan concept {concept}: no material")
    if pack.manifest.status == "published":
        if not pack.materials:
            result.errors.append("published pack has no materials")
        unreviewed = sorted(
            m.material_id for m in pack.materials if m.review_status != "reviewed"
        )
        if unreviewed:
            result.errors.append(f"published pack has unreviewed material: {unreviewed}")
    result.coverage = coverage
    return result


class PackSummary(_StrictModel):
    """The served summary of one published pack."""

    subject: str
    title: str
    tier: str
    version: str
    status: str
    built_at: str
    fingerprint: str
    topics: tuple[str, ...] = ()
    concepts: int = 0
    materials: int = 0


def load_pack_summaries(
    subjects_path: Path | None,
    chunks: dict[str, Chunk],
    index_text_hash: str,
) -> list[PackSummary]:
    """Summaries of the published, valid packs under `subjects_path`.

    A draft or invalid pack is skipped, not served: the same discipline as
    the pack loader, softened at the API boundary so one broken pack cannot
    take the subject index down.
    """
    if subjects_path is None or not subjects_path.is_dir():
        return []
    summaries: list[PackSummary] = []
    for directory in sorted(path for path in subjects_path.iterdir() if path.is_dir()):
        if not (directory / "pack.toml").exists():
            continue
        try:
            pack = load_subject_pack(directory)
        except Exception:
            logger.warning(
                "subject pack %s failed to load; skipping", directory, exc_info=True
            )
            continue
        if pack.manifest.status != "published":
            continue
        result = validate_pack(pack, chunks, index_text_hash)
        if not result.ok:
            logger.warning(
                "subject pack %s failed validation; skipping: %s",
                directory,
                "; ".join(result.errors[:3]),
            )
            continue
        subject = known_subject(pack.manifest.subject)
        summaries.append(
            PackSummary(
                subject=pack.manifest.subject,
                title=subject.name if subject else pack.manifest.subject,
                tier=pack.manifest.tier,
                version=pack.manifest.version,
                status=pack.manifest.status,
                built_at=pack.manifest.built_at,
                fingerprint=pack_fingerprint(pack),
                topics=tuple(sorted(topic.topic_id for topic in pack.topics)),
                concepts=len(pack.concepts),
                materials=len(pack.materials),
            )
        )
    return summaries


def pack_fingerprint(pack: SubjectPack) -> str:
    """A short deterministic hash over the pack's records: the rebuild check.

    A pack rebuild is reproducible when the fingerprint is stable for equal
    content; `built_at`, `version` and `status` are excluded so regeneration
    does not change the fingerprint by itself. `mode="json"` so date-valued
    reference fields serialise (Python-mode dumps of a ReferenceLink would
    otherwise hand `json.dumps` a raw date and raise).
    """
    payload = json.dumps(
        {
            "manifest": pack.manifest.model_dump(
                exclude={"built_at", "version", "status"}, mode="json"
            ),
            "topics": [
                t.model_dump(mode="json") for t in sorted(pack.topics, key=lambda t: t.topic_id)
            ],
            "concepts": [
                c.model_dump(mode="json")
                for c in sorted(pack.concepts, key=lambda c: c.concept_id)
            ],
            "materials": [
                m.model_dump(mode="json")
                for m in sorted(pack.materials, key=lambda m: m.material_id)
            ],
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def write_subject_pack(pack: SubjectPack, directory: Path) -> None:
    """Serialize a pack to its directory (JSONL + pack.toml), order-stable."""
    directory.mkdir(parents=True, exist_ok=True)
    manifest = pack.manifest
    toml_lines = "\n".join(
        f"{field_name} = {json.dumps(value, ensure_ascii=False)}"
        for field_name, value in (
            ("subject", manifest.subject),
            ("tier", manifest.tier),
            ("version", manifest.version),
            ("status", manifest.status),
            ("built_at", manifest.built_at),
            ("index_text_hash", manifest.index_text_hash),
        )
    )
    (directory / "pack.toml").write_text(toml_lines + "\n", encoding="utf-8")
    _dump_jsonl(directory / "topics.jsonl", pack.topics)
    _dump_jsonl(directory / "concepts.jsonl", pack.concepts)
    _dump_jsonl(directory / "materials.jsonl", pack.materials)


def _dump_jsonl(path: Path, records: list[BaseModel]) -> None:
    body = "\n".join(r.model_dump_json() for r in records)
    path.write_text(body + "\n" if body else "", encoding="utf-8")


__all__ = [
    "Concept",
    "Coverage",
    "PACK_STATUS",
    "PackManifest",
    "PackValidation",
    "SubjectPack",
    "Topic",
    "index_chunks",
    "load_subject_pack",
    "pack_fingerprint",
    "validate_pack",
    "write_subject_pack",
]
