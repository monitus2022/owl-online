"""Independent model checks for the DADA bank (#191).

A second model answers each MCQ without the key and judges every option, then
answers each short question and compares its answer with the golden answer and
rubric. These are quality gates, not the production grader.
"""

from __future__ import annotations

import asyncio
import json

from app.exam.bank import BankItem, ExamBank
from app.knowledge.packs import SubjectPack
from app.providers.contracts import Llm
from eval.exam.models import IndependentReport

INDEPENDENT_PROMPT_VERSION = "dada-bank-independent-v1"
LETTERS = "ABCDEF"

MCQ_SYSTEM = (
    "You are an independent exam-bank verifier. Use only the supplied material "
    "and evidence. Do not use outside knowledge. Return strict JSON and nothing else."
)
SHORT_SOLVER_SYSTEM = (
    "You are an independent exam-bank verifier. Answer the question using only the "
    "supplied material and evidence. Write 2-3 sentences and do not mention the JSON."
)
SHORT_JUDGE_SYSTEM = (
    "You are an independent judge for short-answer exam items. Use only the supplied "
    "material and evidence. Compare the golden answer and a candidate answer against "
    "the required points and rubric. Return strict JSON and nothing else."
)


def _evidence_block(item: BankItem) -> str:
    return "\n".join(f"[{ref.chunk_id}] {ref.quote}" for ref in item.source_refs)


def _material_text(pack: SubjectPack, item: BankItem) -> str:
    material = next(
        (row for row in pack.materials if row.material_id == item.material_id),
        None,
    )
    if material is None:
        raise ValueError(f"{item.item_id}: material {item.material_id!r} not in pack")
    return material.text


def json_payload(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"no JSON object in reply: {text!r}")
    return json.loads(text[start : end + 1])


async def _call_json(llm: Llm, system: str, prompt: str) -> dict:
    reply = await llm.generate(system, prompt)
    try:
        return json_payload(reply)
    except (ValueError, json.JSONDecodeError):
        retry = await llm.generate(
            system + " Your previous reply was not valid JSON. Return only the JSON object.",
            prompt,
        )
        return json_payload(retry)


def _mcq_prompt(item: BankItem, material_text: str) -> str:
    options = "\n".join(
        f"{LETTERS[index]}. {option.text}" for index, option in enumerate(item.options)
    )
    return (
        f"MATERIAL:\n{material_text}\n\n"
        f"EVIDENCE:\n{_evidence_block(item)}\n\n"
        f"QUESTION:\n{item.prompt}\n\n"
        f"OPTIONS:\n{options}\n\n"
        "Return a JSON object with: best (letter), option_judgements (each letter -> "
        '"correct", "plausible" or "false"), second_defensible (letter only if another '
        "option is also fully correct, else null), reason (one sentence)."
    )


def _short_solver_prompt(item: BankItem, material_text: str) -> str:
    return (
        f"MATERIAL:\n{material_text}\n\n"
        f"EVIDENCE:\n{_evidence_block(item)}\n\n"
        f"QUESTION:\n{item.prompt}\n\nAnswer in 2-3 sentences."
    )


def _short_judge_prompt(item: BankItem, material_text: str, candidate: str) -> str:
    points = "\n".join(f"- {point}" for point in item.required_points)
    rubric = "\n".join(
        f"- {criterion.criterion_id}: {criterion.description} "
        f"({criterion.max_marks} marks)"
        for criterion in item.rubric
    )
    return (
        f"MATERIAL:\n{material_text}\n\n"
        f"EVIDENCE:\n{_evidence_block(item)}\n\n"
        f"QUESTION:\n{item.prompt}\n\n"
        f"REQUIRED POINTS:\n{points}\n\n"
        f"RUBRIC:\n{rubric}\n\n"
        f"GOLDEN ANSWER:\n{item.model_answer}\n\n"
        f"CANDIDATE ANSWER:\n{candidate}\n\n"
        "Return a JSON object with: golden_correct (bool), golden_complete (bool), "
        "missing_required_points (list), candidate_correct (bool), candidate_complete "
        "(bool), notes (one or two sentences)."
    )


def _mcq_flags(item: BankItem, payload: dict) -> tuple[bool, bool]:
    """Return (key_match, ambiguous) for one MCQ reply."""
    key_index = next(
        index
        for index, option in enumerate(item.options)
        if option.option_id == item.correct_option_id
    )
    key_letter = LETTERS[key_index]
    judgements = payload.get("option_judgements", {})
    if not isinstance(judgements, dict):
        judgements = {}
    other_correct = [
        letter
        for letter, value in judgements.items()
        if letter != key_letter and str(value).lower() == "correct"
    ]
    second = payload.get("second_defensible")
    ambiguous = (
        payload.get("best") != key_letter
        or (key_letter in judgements and str(judgements[key_letter]).lower() != "correct")
        or bool(other_correct)
        or (second and str(judgements.get(second, "")).lower() == "correct")
    )
    return payload.get("best") == key_letter, bool(ambiguous)


async def _verify_mcq(
    llm: Llm, item: BankItem, pack: SubjectPack
) -> tuple[bool, bool, str | None]:
    try:
        material = _material_text(pack, item)
        payload = await _call_json(llm, MCQ_SYSTEM, _mcq_prompt(item, material))
        key_match, ambiguous = _mcq_flags(item, payload)
        return key_match, ambiguous, None
    except Exception as error:  # noqa: BLE001 - report, never crash the run
        return False, False, f"{item.item_id}: {error}"


async def _verify_short(
    llm: Llm, item: BankItem, pack: SubjectPack
) -> tuple[bool, int, str | None]:
    try:
        material = _material_text(pack, item)
        candidate = await llm.generate(
            SHORT_SOLVER_SYSTEM, _short_solver_prompt(item, material)
        )
        judgement = await _call_json(
            llm,
            SHORT_JUDGE_SYSTEM,
            _short_judge_prompt(item, material, candidate),
        )
        missing = judgement.get("missing_required_points") or []
        ok = (
            judgement.get("golden_correct") is True
            and judgement.get("golden_complete") is True
            and not missing
        )
        return ok, len(missing), None
    except Exception as error:  # noqa: BLE001
        return False, 0, f"{item.item_id}: {error}"


async def run_independent_checks(
    bank: ExamBank,
    pack: SubjectPack,
    llm: Llm,
    *,
    concurrency: int = 4,
) -> IndependentReport:
    """Run the MCQ solver, distractor and short-answer golden checks."""
    report = IndependentReport(
        model=bank.manifest.judge_model,
        temperature=bank.manifest.judge_temperature or 0.0,
        prompt_version=INDEPENDENT_PROMPT_VERSION,
    )
    mcq_items = [item for item in bank.items if item.kind == "mcq"]
    short_items = [item for item in bank.items if item.kind == "short_answer"]
    report.mcq_total = len(mcq_items)
    report.short_total = len(short_items)

    semaphore = asyncio.Semaphore(concurrency)

    async def one_mcq(item: BankItem) -> None:
        async with semaphore:
            key_match, ambiguous, error = await _verify_mcq(llm, item, pack)
            if key_match:
                report.mcq_key_matches += 1
            if ambiguous:
                report.mcq_ambiguities += 1
            if error:
                report.errors.append(error)

    async def one_short(item: BankItem) -> None:
        async with semaphore:
            ok, missing, error = await _verify_short(llm, item, pack)
            if ok:
                report.short_golden_ok += 1
            report.short_missing_points += missing
            if error:
                report.errors.append(error)

    await asyncio.gather(*(one_mcq(item) for item in mcq_items))
    await asyncio.gather(*(one_short(item) for item in short_items))
    return report


__all__ = [
    "INDEPENDENT_PROMPT_VERSION",
    "MCQ_SYSTEM",
    "SHORT_JUDGE_SYSTEM",
    "SHORT_SOLVER_SYSTEM",
    "run_independent_checks",
]
