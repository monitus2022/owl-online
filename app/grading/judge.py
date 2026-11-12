"""Short-answer judge and attempt grading (#192).

MCQ marks are deterministic. Short answers are judged in one call per attempt:
the request contains every uncached short answer, the response is keyed by item
id, and every criterion is validated. A malformed or incomplete response gets
one retry for the affected questions; if the retry still fails, those questions
carry `needs_review` and never a silent zero.

The judge is pinned by the bank manifest: model, temperature 0, prompt version
and rubric version. It must be a different family from the question generator.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime

from app.config import Settings, settings
from app.exam.bank import BankItem, ExamBank
from app.grading.bands import band_for
from app.grading.cache import JudgeCache
from app.grading.mcq import score_mcq
from app.grading.models import (
    AttemptAnswer,
    AttemptGrade,
    CriterionGrade,
    JudgeConfig,
    QuestionGrade,
)
from app.providers.contracts import Llm
from app.providers.factory import make_llm

PROMPT_VERSION = "owl-bank-judge-v3"
DADA_PROMPT_VERSION = "dada-bank-judge-v2"

JUDGE_SYSTEM = (
    "You are an exam judge for an O.W.L. subject bank. "
    "Use only the supplied question, golden answer, rubric, material id and "
    "evidence. Compare each student answer with the golden answer for correctness "
    "and completeness. Award marks for every rubric criterion. Do not require the "
    "golden wording: a paraphrase or a correct answer without the key term can "
    "still earn marks when the rubric is satisfied. Do not reward verbosity. Do "
    "not penalise a concise answer that covers the required points. An off-topic, "
    "contradictory or unsupported answer loses the relevant criteria. A blank "
    "answer earns 0. Return strict JSON and nothing else. The response must be an "
    'object with a "results" object keyed by item id. Each value must contain '
    '"criteria" (one entry per supplied criterion, with criterion_id, awarded, '
    'max_marks and reason), "total" (the sum of awarded), "feedback" (a short '
    'comment) and "evidence_ids" (a non-empty list of chunk ids from the supplied '
    "evidence). Do not add or omit items or criteria."
)

RETRY_SYSTEM = (
    JUDGE_SYSTEM
    + " Your previous response was rejected by the validator. Correct only the "
    "listed item ids and return the corrected JSON object."
)

# The v2 text is frozen verbatim so the DADA calibration pin cannot drift when
# the neutral v3 prompt changes.
DADA_JUDGE_SYSTEM = (
    "You are an exam judge for the O.W.L. Defence Against the Dark Arts bank. "
    "Use only the supplied question, golden answer, rubric, material id and "
    "evidence. Compare each student answer with the golden answer for correctness "
    "and completeness. Award marks for every rubric criterion. Do not require the "
    "golden wording: a paraphrase or a correct answer without the key term can "
    "still earn marks when the rubric is satisfied. Do not reward verbosity. Do "
    "not penalise a concise answer that covers the required points. An off-topic, "
    "contradictory or unsupported answer loses the relevant criteria. A blank "
    "answer earns 0. Return strict JSON and nothing else. The response must be an "
    'object with a "results" object keyed by item id. Each value must contain '
    '"criteria" (one entry per supplied criterion, with criterion_id, awarded, '
    'max_marks and reason), "total" (the sum of awarded), "feedback" (a short '
    'comment) and "evidence_ids" (a non-empty list of chunk ids from the supplied '
    "evidence). Do not add or omit items or criteria."
)
DADA_RETRY_SYSTEM = (
    DADA_JUDGE_SYSTEM
    + " Your previous response was rejected by the validator. Correct only the "
    "listed item ids and return the corrected JSON object."
)

JUDGE_SYSTEMS = {
    PROMPT_VERSION: JUDGE_SYSTEM,
    DADA_PROMPT_VERSION: DADA_JUDGE_SYSTEM,
}
RETRY_SYSTEMS = {
    PROMPT_VERSION: RETRY_SYSTEM,
    DADA_PROMPT_VERSION: DADA_RETRY_SYSTEM,
}


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _vendor(slug: str) -> str:
    head = slug.split("/", 1)[0]
    return head.split(".", 1)[0].strip().lower()


_FAMILY_ALIASES = {
    "mistral": "mistral",
    "mistralai": "mistral",
    "meta": "meta",
    "meta-llama": "meta",
    "amazon": "amazon",
    "qwen": "qwen",
    "deepseek": "deepseek",
    "cohere": "cohere",
    "nvidia": "nvidia",
    "microsoft": "microsoft",
}


def _family(slug: str) -> str:
    head = _vendor(slug)
    return _FAMILY_ALIASES.get(head, head)


def _judge_config(
    bank: ExamBank, *, config_settings: Settings | None = None
) -> JudgeConfig:
    config = config_settings or settings
    manifest = bank.manifest
    if manifest.status != "published":
        raise ValueError("exam grading requires a published bank")
    if not manifest.generator_model.strip():
        raise ValueError("published bank has no generator model")
    if not manifest.judge_model.strip():
        raise ValueError("published bank has no judge model")
    if manifest.judge_temperature != 0.0:
        raise ValueError("exam judge temperature must be 0")
    if manifest.judge_prompt_version not in JUDGE_SYSTEMS:
        raise ValueError("bank judge prompt version does not match the grader")
    if _family(manifest.generator_model) == _family(manifest.judge_model):
        raise ValueError("judge must be a different model family from the generator")
    return JudgeConfig(
        model=manifest.judge_model,
        temperature=manifest.judge_temperature,
        prompt_version=manifest.judge_prompt_version,
        provider=config.exam_judge_provider,
        max_tokens=config.exam_judge_max_tokens,
    )


def judge_llm_from_bank(
    bank: ExamBank, *, config_settings: Settings | None = None
) -> Llm:
    """Build the configured judge adapter from the bank's pinned model."""
    config = _judge_config(bank, config_settings=config_settings)
    config_settings = config_settings or settings
    if config_settings.exam_judge_provider == "bedrock" and "/" in config.model:
        raise ValueError(
            "Bedrock judge models use the provider.model-id form, not an OpenRouter slug"
        )
    return make_llm(
        config_settings.exam_judge_provider,
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )


def default_judge_cache(*, config_settings: Settings | None = None) -> JudgeCache:
    """The configured grading cache; an empty path disables it."""
    config_settings = config_settings or settings
    return JudgeCache(config_settings.exam_judge_cache_path)


def _evidence(item: BankItem) -> list[dict[str, str]]:
    return [
        {"chunk_id": ref.chunk_id, "quote": ref.quote}
        for ref in item.source_refs
    ]


def _prompt(bank_version: str, entries: Sequence[tuple[BankItem, str]]) -> str:
    questions = []
    for item, answer in entries:
        questions.append(
            {
                "item_id": item.item_id,
                "question": item.prompt,
                "golden_answer": item.model_answer or "",
                "rubric": [
                    {
                        "criterion_id": criterion.criterion_id,
                        "description": criterion.description,
                        "max_marks": criterion.max_marks,
                    }
                    for criterion in item.rubric
                ],
                "material_id": item.material_id,
                "evidence": _evidence(item),
                "student_answer": answer,
                "max_marks": item.marks,
            }
        )
    return json.dumps(
        {"bank_version": bank_version, "questions": questions},
        ensure_ascii=False,
        indent=2,
    )


def _retry_prompt(
    original: str,
    raw: str,
    errors: dict[str, str],
    item_ids: Sequence[str],
) -> str:
    detail = "\n".join(f"- {item_id}: {errors[item_id]}" for item_id in item_ids)
    return (
        f"{original}\n\n"
        f"PREVIOUS RESPONSE:\n{raw}\n\n"
        f"VALIDATION ERRORS:\n{detail}\n\n"
        f"Return a corrected JSON object with exactly these item ids: "
        f"{', '.join(item_ids)}. Do not change the accepted items."
    )


def _parse_json(raw: str) -> dict:
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("judge response did not contain a JSON object")
    payload = json.loads(raw[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("judge response JSON is not an object")
    return payload


def _ensure_citation(feedback: str, item: BankItem, evidence_ids: Sequence[str]) -> str:
    if item.material_id in feedback or any(eid in feedback for eid in evidence_ids):
        return feedback
    return f"{feedback} [{evidence_ids[0]}]"


def _validate_question(
    item: BankItem,
    record: object,
    raw_sha256: str,
) -> QuestionGrade:
    if not isinstance(record, dict):
        raise ValueError("record is not an object")
    criteria = record.get("criteria")
    if not isinstance(criteria, list):
        raise ValueError("criteria must be a list")
    expected = {
        criterion.criterion_id: criterion for criterion in item.rubric
    }
    if len(criteria) != len(expected):
        raise ValueError(f"expected {len(expected)} criteria, got {len(criteria)}")

    seen: set[str] = set()
    grades: list[CriterionGrade] = []
    total = 0
    for raw_criterion in criteria:
        if not isinstance(raw_criterion, dict):
            raise ValueError("criterion is not an object")
        criterion_id = raw_criterion.get("criterion_id")
        if criterion_id not in expected:
            raise ValueError(f"unknown criterion {criterion_id!r}")
        if criterion_id in seen:
            raise ValueError(f"duplicate criterion {criterion_id!r}")
        seen.add(criterion_id)
        awarded = raw_criterion.get("awarded")
        max_marks = raw_criterion.get("max_marks")
        reason = raw_criterion.get("reason")
        if not isinstance(awarded, int) or isinstance(awarded, bool):
            raise ValueError(f"{criterion_id}: awarded must be an integer")
        if not isinstance(max_marks, int) or isinstance(max_marks, bool):
            raise ValueError(f"{criterion_id}: max_marks must be an integer")
        if max_marks != expected[criterion_id].max_marks:
            raise ValueError(
                f"{criterion_id}: max_marks {max_marks} != "
                f"{expected[criterion_id].max_marks}"
            )
        if not 0 <= awarded <= max_marks:
            raise ValueError(
                f"{criterion_id}: awarded {awarded} is outside 0..{max_marks}"
            )
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"{criterion_id}: reason must not be blank")
        total += awarded
        grades.append(
            CriterionGrade(
                criterion_id=criterion_id,
                awarded=awarded,
                max_marks=max_marks,
                reason=reason.strip(),
            )
        )
    if seen != set(expected):
        raise ValueError("criteria are incomplete")
    if total > item.marks:
        raise ValueError(f"total {total} exceeds the question maximum {item.marks}")

    reported_total = record.get("total")
    if not isinstance(reported_total, int) or isinstance(reported_total, bool):
        raise ValueError("total must be an integer")
    if reported_total != total:
        raise ValueError(f"total {reported_total} != sum {total}")

    feedback = record.get("feedback")
    if not isinstance(feedback, str) or not feedback.strip():
        raise ValueError("feedback must not be blank")

    evidence_ids = record.get("evidence_ids")
    if not isinstance(evidence_ids, list) or not evidence_ids:
        raise ValueError("evidence_ids must be a non-empty list")
    allowed = {ref.chunk_id for ref in item.source_refs}
    clean_ids: list[str] = []
    for evidence_id in evidence_ids:
        if not isinstance(evidence_id, str) or not evidence_id.strip():
            raise ValueError("evidence ids must be non-blank strings")
        if evidence_id not in allowed:
            raise ValueError(f"unknown evidence id {evidence_id!r}")
        if evidence_id not in clean_ids:
            clean_ids.append(evidence_id)

    ordered = [
        next(grade for grade in grades if grade.criterion_id == criterion.criterion_id)
        for criterion in item.rubric
    ]
    return QuestionGrade(
        item_id=item.item_id,
        kind="short_answer",
        marks_awarded=total,
        max_marks=item.marks,
        model_answer=item.model_answer,
        criteria=tuple(ordered),
        feedback=_ensure_citation(feedback.strip(), item, clean_ids),
        material_id=item.material_id,
        evidence_ids=tuple(clean_ids),
        canon_tier=item.canon_tier,
        rubric_version=item.prompt_version,
        judge_response_sha256=raw_sha256,
    )


def _validate_results(
    payload: dict,
    entries: Sequence[tuple[BankItem, str]],
    raw_sha256: str,
) -> tuple[dict[str, QuestionGrade], dict[str, str]]:
    results = payload.get("results")
    if not isinstance(results, dict):
        return {}, {
            item.item_id: "results must be an object keyed by item id"
            for item, _ in entries
        }
    valid: dict[str, QuestionGrade] = {}
    errors: dict[str, str] = {}
    for item, _ in entries:
        if item.item_id not in results:
            errors[item.item_id] = "missing item"
            continue
        try:
            valid[item.item_id] = _validate_question(
                item, results[item.item_id], raw_sha256
            )
        except ValueError as error:
            errors[item.item_id] = str(error)
    return valid, errors


def _needs_review(item: BankItem, reason: str, raw_sha256: str) -> QuestionGrade:
    return QuestionGrade(
        item_id=item.item_id,
        kind="short_answer",
        marks_awarded=None,
        max_marks=item.marks,
        model_answer=item.model_answer,
        criteria=(),
        feedback=(
            "Judge output could not be validated; needs review. "
            f"({reason}) [{item.evidence_snapshot.chunk_id}]"
        ),
        material_id=item.material_id,
        evidence_ids=(item.evidence_snapshot.chunk_id,),
        canon_tier=item.canon_tier,
        rubric_version=item.prompt_version,
        needs_review=True,
        judge_response_sha256=raw_sha256,
    )


def _blank_grade(item: BankItem) -> QuestionGrade:
    criteria = tuple(
        CriterionGrade(
            criterion_id=criterion.criterion_id,
            awarded=0,
            max_marks=criterion.max_marks,
            reason="Blank answer.",
        )
        for criterion in item.rubric
    )
    return QuestionGrade(
        item_id=item.item_id,
        kind="short_answer",
        marks_awarded=0,
        max_marks=item.marks,
        model_answer=item.model_answer,
        criteria=criteria,
        feedback=f"No answer submitted. [{item.evidence_snapshot.chunk_id}]",
        material_id=item.material_id,
        evidence_ids=(item.evidence_snapshot.chunk_id,),
        canon_tier=item.canon_tier,
        rubric_version=item.prompt_version,
    )


async def _call_judge(
    llm: Llm,
    bank_version: str,
    entries: Sequence[tuple[BankItem, str]],
    prompt_version: str,
) -> tuple[dict[str, QuestionGrade], list[str]]:
    system = JUDGE_SYSTEMS[prompt_version]
    retry_system = RETRY_SYSTEMS[prompt_version]
    prompt = _prompt(bank_version, entries)
    raws: list[str] = []

    raw = await llm.generate(system, prompt)
    raws.append(raw)
    raw_sha = _sha256(raw)
    try:
        payload = _parse_json(raw)
    except (ValueError, json.JSONDecodeError) as error:
        valid: dict[str, QuestionGrade] = {}
        errors = {
            item.item_id: f"invalid JSON: {error}" for item, _ in entries
        }
    else:
        valid, errors = _validate_results(payload, entries, raw_sha)

    if errors:
        retry_entries = [
            (item, answer) for item, answer in entries if item.item_id in errors
        ]
        retry_ids = [item.item_id for item, _ in retry_entries]
        retry_raw = await llm.generate(
            retry_system,
            _retry_prompt(prompt, raw, errors, retry_ids),
        )
        raws.append(retry_raw)
        retry_sha = _sha256(retry_raw)
        try:
            retry_payload = _parse_json(retry_raw)
        except (ValueError, json.JSONDecodeError) as error:
            retry_valid: dict[str, QuestionGrade] = {}
            retry_errors = {
                item.item_id: f"invalid JSON: {error}" for item, _ in retry_entries
            }
        else:
            retry_valid, retry_errors = _validate_results(
                retry_payload, retry_entries, retry_sha
            )
        valid.update(retry_valid)
        last_sha = retry_sha
        final_errors = retry_errors
    else:
        last_sha = raw_sha
        final_errors = {}

    for item, _ in entries:
        if item.item_id not in valid:
            valid[item.item_id] = _needs_review(
                item,
                final_errors.get(item.item_id, "missing result"),
                last_sha,
            )
    return valid, raws


async def grade_attempt(
    bank: ExamBank,
    item_ids: Sequence[str],
    answers: Sequence[AttemptAnswer],
    *,
    llm: Llm | None = None,
    cache: JudgeCache | None = None,
    now: datetime | None = None,
) -> AttemptGrade:
    """Grade one attempt: deterministic MCQ, one judge call for the short answers."""
    config = _judge_config(bank)
    if not item_ids:
        raise ValueError("an attempt needs at least one item")
    if len(set(item_ids)) != len(item_ids):
        raise ValueError("item ids must be unique")
    items: list[BankItem] = []
    for item_id in item_ids:
        item = bank.find_item(item_id)
        if item is None:
            raise ValueError(f"unknown item id {item_id!r}")
        items.append(item)

    by_id: dict[str, AttemptAnswer] = {}
    for answer in answers:
        if answer.item_id in by_id:
            raise ValueError(f"duplicate answer for {answer.item_id!r}")
        by_id[answer.item_id] = answer
    unknown = set(by_id) - set(item_ids)
    if unknown:
        raise ValueError(f"answers for items outside the attempt: {sorted(unknown)}")

    grades: dict[str, QuestionGrade] = {}
    short_entries: list[tuple[BankItem, str]] = []
    for item in items:
        answer = by_id.get(item.item_id)
        if item.kind == "mcq":
            if answer is not None and answer.answer_text is not None:
                raise ValueError(f"{item.item_id}: MCQ answers use option_id")
            grades[item.item_id] = score_mcq(
                item, answer.option_id if answer is not None else None
            )
        else:
            if answer is not None and answer.option_id is not None:
                raise ValueError(f"{item.item_id}: short answers use answer_text")
            text = (
                answer.answer_text
                if answer is not None and answer.answer_text is not None
                else ""
            )
            if text.strip():
                short_entries.append((item, text))
            else:
                grades[item.item_id] = _blank_grade(item)

    raws: list[str] = []
    if short_entries:
        pending: list[tuple[BankItem, str, str | None]] = []
        for item, text in short_entries:
            key: str | None = None
            if cache is not None:
                key = JudgeCache.key(bank.manifest.version, item, text, config)
                cached = cache.get(key, item)
                if cached is not None:
                    grades[item.item_id] = cached
                    continue
            pending.append((item, text, key))
        if pending:
            if llm is None:
                raise ValueError("short answers need a judge LLM")
            judged, raws = await _call_judge(
                llm,
                bank.manifest.version,
                [(item, text) for item, text, _ in pending],
                config.prompt_version,
            )
            for item, text, key in pending:
                grade = judged[item.item_id]
                grades[item.item_id] = grade
                if cache is not None and key is not None and not grade.needs_review:
                    cache.set(
                        key,
                        bank.manifest.version,
                        item,
                        text,
                        config,
                        grade,
                        grade.judge_response_sha256 or "",
                    )

    ordered = [grades[item_id] for item_id in item_ids]
    marks = [grade.marks_awarded for grade in ordered]
    max_marks = sum(item.marks for item in items)
    total = None if any(mark is None for mark in marks) else sum(
        mark for mark in marks if mark is not None
    )
    band = band_for(total, max_marks) if total is not None else None
    graded_at = (now or datetime.now(UTC)).astimezone(UTC).replace(
        microsecond=0
    ).isoformat().replace("+00:00", "Z")
    output_sha = _sha256("\n".join(raws)) if raws else None
    return AttemptGrade(
        bank_version=bank.manifest.version,
        subject=bank.manifest.subject,
        judge_model=config.model,
        judge_temperature=config.temperature,
        judge_provider=config.provider,
        judge_max_tokens=config.max_tokens,
        judge_prompt_version=config.prompt_version,
        graded_at=graded_at,
        questions=tuple(ordered),
        total=total,
        max_marks=max_marks,
        band=band,
        needs_review=any(grade.needs_review for grade in ordered),
        judge_output_sha256=output_sha,
    )


__all__ = [
    "JUDGE_SYSTEM",
    "PROMPT_VERSION",
    "RETRY_SYSTEM",
    "default_judge_cache",
    "grade_attempt",
    "judge_llm_from_bank",
]
