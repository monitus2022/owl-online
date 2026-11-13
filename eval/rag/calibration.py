"""Lesson faithfulness judge calibration (#258).

The production faithfulness metric is binary. This calibration uses a
three-level judge so partial answers are visible, and keeps refusals out of the
faithfulness denominator.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from app.knowledge.materials import Material
from app.pipeline.generate import ABSTAIN_MESSAGE, render_evidence
from app.pipeline.generate.generate import is_refusal
from app.pipeline.generate.lesson import is_lesson_refusal, render_materials
from app.schemas import Chunk
from eval.harness import FAITHFUL_SYSTEM, parse_faithful
from eval.rag.runner import RagStack

LABELS = ("supported", "partial", "unsupported")
LABEL_SCORE = {"unsupported": 0, "partial": 1, "supported": 2}
SLICES = frozenset({"in_pack", "paraphrase", "multi_concept", "mixed", "off_pack"})

FAITHFUL_LABEL_SYSTEM = (
    "You check whether a lesson answer is supported by the notes and excerpts "
    "provided. Ignore citations and whether the answer is correct in the wider "
    "world. A claim is supported only if the notes or excerpts state it or it "
    "follows directly from them. Reply with JSON only, no prose: "
    '{"label": "supported" | "partial" | "unsupported"}. supported means every '
    "factual claim is supported; partial means at least one factual claim is "
    "supported and at least one is not; unsupported means the main claim is "
    "not supported."
)

_LABEL = re.compile(r"\{[^{}]*\}", re.DOTALL)


@dataclass(frozen=True)
class CalibrationItem:
    """One synthetic answer and the evidence it should be judged against."""

    item_id: str
    slice_name: str
    question: str
    answer: str
    material_ids: tuple[str, ...]
    chunk_ids: tuple[str, ...]
    label: str
    label_source: str
    note: str = ""


@dataclass(frozen=True)
class CalibrationResult:
    item: CalibrationItem
    judge_label: str | None
    binary_faithful: bool | None = None
    parse_failed: bool = False
    refusal_ok: bool | None = None

    @property
    def score_ok(self) -> bool:
        if self.item.label == "refusal":
            return self.refusal_ok is True
        return self.judge_label == self.item.label


@dataclass(frozen=True)
class CalibrationReport:
    """Agreement between the proposed labels and the judge."""

    total: int
    judged: int
    refusals: int
    exact_agreement: float
    adjacent_agreement: float
    mean_absolute_error: float
    binary_agreement: float
    refusals_ok: int
    adopted: bool
    parse_failures: int
    disagreements: tuple[CalibrationResult, ...]
    label_source: str

    @property
    def ok(self) -> bool:
        return (
            self.adopted
            and self.refusals_ok == self.refusals
            and self.binary_agreement >= 0.7
            and self.parse_failures == 0
            and self.exact_agreement >= 0.7
        )


def _string_tuple(record: dict[str, object], key: str, where: str) -> tuple[str, ...]:
    value = record.get(key, [])
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValueError(f"{where}: {key!r} must be a list of non-empty strings")
    return tuple(item.strip() for item in value)


def parse_label(raw: str) -> str | None:
    """The three-level label from a judge reply, or None."""
    match = _LABEL.search(raw)
    if match is None:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    label = str(data.get("label", "")).lower()
    return label if label in LABELS else None


def load_calibration(path: Path) -> list[CalibrationItem]:
    """Load the calibration fixture; duplicate ids fail loudly."""
    items: list[CalibrationItem] = []
    seen: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError(f"{path}:{line_number}: each line must be an object")
        where = f"{path}:{line_number}"
        item_id = str(record.get("id", "")).strip()
        slice_name = str(record.get("slice", "")).strip()
        question = str(record.get("question", "")).strip()
        answer = str(record.get("answer", "")).strip()
        label = str(record.get("label", "")).strip().lower()
        label_source = str(record.get("label_source", "")).strip()
        if not item_id or not question or not answer:
            raise ValueError(f"{where}: id, question and answer are required")
        if slice_name not in SLICES:
            raise ValueError(f"{where}: unknown slice {slice_name!r}")
        if label not in {*LABELS, "refusal"}:
            raise ValueError(f"{where}: unknown label {label!r}")
        if not label_source:
            raise ValueError(f"{where}: label_source is required")
        if item_id in seen:
            raise ValueError(f"{where}: duplicate id {item_id!r}")
        seen.add(item_id)
        items.append(
            CalibrationItem(
                item_id=item_id,
                slice_name=slice_name,
                question=question,
                answer=answer,
                material_ids=_string_tuple(record, "material_ids", where),
                chunk_ids=_string_tuple(record, "chunk_ids", where),
                label=label,
                label_source=label_source,
                note=str(record.get("note", "")).strip(),
            )
        )
    if not items:
        raise ValueError(f"{path}: no calibration items")
    missing = SLICES - {item.slice_name for item in items}
    if missing:
        raise ValueError(f"{path}: missing calibration slices {sorted(missing)}")
    return items


def _evidence_prompt(
    item: CalibrationItem,
    pack_store,
    chunks_by_id: dict[str, Chunk],
) -> str:
    parts: list[str] = []
    materials: list[Material] = []
    missing_materials: list[str] = []
    for material_id in item.material_ids:
        subject = material_id.split("-", 1)[0]
        pack = pack_store.get(subject)
        material = pack.find_material(material_id) if pack is not None else None
        if material is None:
            missing_materials.append(material_id)
        elif material not in materials:
            materials.append(material)
    missing_chunks = [chunk_id for chunk_id in item.chunk_ids if chunk_id not in chunks_by_id]
    if missing_materials or missing_chunks:
        raise ValueError(
            f"{item.item_id}: unresolved evidence "
            f"materials={missing_materials} chunks={missing_chunks}"
        )
    if item.label != "refusal" and not materials and not item.chunk_ids:
        raise ValueError(f"{item.item_id}: non-refusal item has no evidence")
    if materials:
        parts.append(f"Lesson notes:\n{render_materials(materials)}")
    chunks = [chunks_by_id[cid] for cid in item.chunk_ids]
    if chunks:
        parts.append(f"Excerpts:\n{render_evidence(chunks)}")
    parts.append(f"Question: {item.question}\n\nAnswer: {item.answer}")
    return "\n\n".join(parts)


def summarize_calibration(results: list[CalibrationResult]) -> CalibrationReport:
    """Aggregate agreement, excluding refusals from the faithfulness set."""
    judged = [result for result in results if result.item.label != "refusal"]
    exact = sum(result.judge_label == result.item.label for result in judged)
    adjacent = sum(
        result.judge_label is not None
        and abs(LABEL_SCORE.get(result.judge_label, -10) - LABEL_SCORE[result.item.label]) <= 1
        for result in judged
    )
    mae = (
        sum(
            abs(LABEL_SCORE.get(result.judge_label, 0) - LABEL_SCORE[result.item.label])
            for result in judged
        )
        / len(judged)
        if judged
        else 0.0
    )
    binary_judged = [result for result in judged if result.binary_faithful is not None]
    binary_agreement = (
        sum(
            result.binary_faithful == (result.item.label == "supported") for result in binary_judged
        )
        / len(binary_judged)
        if binary_judged
        else 0.0
    )
    return CalibrationReport(
        total=len(results),
        judged=len(judged),
        refusals=len(results) - len(judged),
        exact_agreement=exact / len(judged) if judged else 0.0,
        adjacent_agreement=adjacent / len(judged) if judged else 0.0,
        mean_absolute_error=mae,
        binary_agreement=binary_agreement,
        refusals_ok=sum(
            result.refusal_ok is True for result in results if result.item.label == "refusal"
        ),
        adopted=bool(results)
        and all(result.item.label_source.startswith("owner-adopted") for result in results),
        parse_failures=sum(result.parse_failed for result in results),
        disagreements=tuple(result for result in judged if result.judge_label != result.item.label),
        label_source=results[0].item.label_source if results else "",
    )


async def run_calibration(
    items: list[CalibrationItem],
    stack: RagStack,
) -> CalibrationReport:
    """Judge every item and report agreement with the proposed labels."""
    pack_store = stack.runtime.pack_store
    results: list[CalibrationResult] = []
    for item in items:
        if item.label == "refusal":
            ok = (
                item.answer.strip().startswith(ABSTAIN_MESSAGE)
                or is_refusal(item.answer, cited=False)
                or is_lesson_refusal(item.answer, cited=False)
            )
            results.append(CalibrationResult(item=item, judge_label=None, refusal_ok=ok))
            continue
        prompt = _evidence_prompt(item, pack_store, stack.chunks_by_id)
        reply = await stack.judge.generate(FAITHFUL_LABEL_SYSTEM, prompt)
        label = parse_label(reply)
        binary_reply = await stack.judge.generate(FAITHFUL_SYSTEM, prompt)
        binary = parse_faithful(binary_reply)
        results.append(
            CalibrationResult(
                item=item,
                judge_label=label,
                binary_faithful=binary,
                parse_failed=label is None or binary is None,
            )
        )
    return summarize_calibration(results)


def render_calibration(report: CalibrationReport) -> str:
    """A short printed summary."""
    lines = [
        f"label source: {report.label_source}",
        f"items: {report.total} judged: {report.judged} refusals: {report.refusals}",
        f"exact agreement: {report.exact_agreement:.4f}",
        f"adjacent agreement: {report.adjacent_agreement:.4f}",
        f"mean absolute error: {report.mean_absolute_error:.4f}",
        f"binary judge agreement: {report.binary_agreement:.4f}",
        f"refusal checks: {report.refusals_ok}/{report.refusals}",
        f"labels adopted: {report.adopted}",
        f"parse failures: {report.parse_failures}",
    ]
    if report.disagreements:
        lines.append("disagreements:")
        for result in report.disagreements:
            lines.append(
                f"  {result.item.item_id}: label={result.item.label} judge={result.judge_label}"
            )
    if not report.adopted:
        lines.append("gate: REVIEW (labels not adopted)")
    else:
        lines.append("gate: " + ("PASS" if report.ok else "REVIEW"))
    return "\n".join(lines)


__all__ = [
    "FAITHFUL_LABEL_SYSTEM",
    "LABEL_SCORE",
    "LABELS",
    "CalibrationItem",
    "CalibrationReport",
    "CalibrationResult",
    "load_calibration",
    "parse_label",
    "render_calibration",
    "run_calibration",
    "summarize_calibration",
]
