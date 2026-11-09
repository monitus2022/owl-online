"""Tests for exam grading (#192): MCQ, one-call judge, validation and bands."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from app.config import settings
from app.exam.bank import (
    BankItem,
    BankManifest,
    EvidenceSnapshot,
    ExamBank,
    McqOption,
    RubricCriterion,
)
from app.grading import (
    AttemptAnswer,
    JudgeCache,
    band_for,
    grade_attempt,
    judge_llm_from_bank,
    score_mcq,
)
from app.knowledge.materials import SourceRef

QUOTE = "The sample lesson turns a feared shape into a comic one."
REF = SourceRef(
    chunk_id="b3-c07-0007",
    book=3,
    chapter=7,
    quote=QUOTE,
    text_hash="a" * 16,
    index_text_hash="test-index",
)
SNAPSHOT = EvidenceSnapshot(
    chunk_id=REF.chunk_id,
    book=REF.book,
    chapter=REF.chapter,
    quote=REF.quote,
    text_hash=REF.text_hash,
    index_text_hash=REF.index_text_hash,
)

GOLDEN_ONE = (
    "Riddikulus forces the boggart to take a form the caster finds funny. "
    "The caster must concentrate on making the feared shape ridiculous, such as "
    "picturing it in comical clothes. Saying the word without that clear comic "
    "image is not enough."
)
GOLDEN_TWO = (
    "A boggart takes the form of whatever the caster fears most, so the student "
    "must recognise the fear and keep control. A student can freeze before forcing "
    "out the word, and even a well-prepared caster can be undone by a shape that "
    "promises failure. Recognition, nerve and a clear comic image all have to work "
    "together under pressure."
)


def _mcq() -> BankItem:
    options = (
        McqOption(option_id="a", text="Riddikulus"),
        McqOption(option_id="b", text="Expecto Patronum"),
        McqOption(option_id="c", text="Protego"),
        McqOption(option_id="d", text="Stupefy"),
        McqOption(option_id="e", text="Expelliarmus"),
        McqOption(option_id="f", text="Lumos"),
    )
    return BankItem(
        item_id="dada-mcq-001",
        subject="dada",
        kind="mcq",
        prompt="Which charm turns a boggart's shape aside?",
        topic="dark-creatures",
        concepts=("dada-creature-boggart",),
        material_id="dada-test-boggart",
        source_refs=(REF,),
        evidence_snapshot=SNAPSHOT,
        difficulty="recall",
        marks=3,
        options=options,
        correct_option_id="a",
        rationale="Riddikulus is the boggart counter.",
        review_status="reviewed",
        prompt_version="dada-bank-v1",
    )


def _short(
    item_id: str,
    prompt: str,
    golden: str,
    points: tuple[str, ...],
) -> BankItem:
    return BankItem(
        item_id=item_id,
        subject="dada",
        kind="short_answer",
        prompt=prompt,
        topic="dark-creatures",
        concepts=("dada-creature-boggart",),
        material_id="dada-test-boggart",
        source_refs=(REF,),
        evidence_snapshot=SNAPSHOT,
        difficulty="explanation",
        marks=8,
        rubric=(
            RubricCriterion(
                criterion_id="correctness",
                description="States the comic transformation.",
                max_marks=4,
            ),
            RubricCriterion(
                criterion_id="completeness",
                description="Explains the mental image and the word-alone limit.",
                max_marks=4,
            ),
        ),
        required_points=points,
        model_answer=golden,
        rationale="The rubric separates correctness from completeness.",
        review_status="reviewed",
        prompt_version="dada-bank-v1",
    )


def _bank(
    *,
    generator_model: str = "deepseek/deepseek-v4.1-flash",
    judge_model: str = "mistralai/mistral-small-3.2-24b-instruct",
    judge_prompt_version: str = "dada-bank-judge-v2",
    judge_temperature: float = 0.0,
    status: str = "published",
) -> ExamBank:
    items = [
        _mcq(),
        _short(
            "dada-short-001",
            "Explain how Riddikulus works against a boggart and what the caster "
            "must do beyond saying the word.",
            GOLDEN_ONE,
            ("feared form", "ridiculous"),
        ),
        _short(
            "dada-short-002",
            "Explain why facing a boggart tests more than the ability to recite "
            "an incantation.",
            GOLDEN_TWO,
            ("recognition", "nerve"),
        ),
    ]
    manifest = BankManifest(
        subject="dada",
        tier="owl",
        version="1.0.0",
        status=status,
        built_at="2026-11-09T00:00:00Z",
        reviewed_at="2026-11-09T00:00:00Z",
        pack_version="1.0.0",
        pack_fingerprint="test-pack",
        index_text_hash="test-index",
        generator_model=generator_model,
        generator_temperature=0.0,
        generator_prompt_version="test-gen",
        judge_model=judge_model,
        judge_temperature=judge_temperature,
        judge_prompt_version=judge_prompt_version,
        mcq_count=1,
        short_answer_count=2,
    )
    return ExamBank(manifest=manifest, items=items)


class ScriptedLlm:
    """Return a scripted judge response per call; fail if called unexpectedly."""

    def __init__(self, *answers: str) -> None:
        self.answers = list(answers)
        self.calls: list[tuple[str, str]] = []

    async def generate(self, system: str, prompt: str, *, context=None) -> str:
        self.calls.append((system, prompt))
        if not self.answers:
            raise AssertionError("unexpected judge call")
        return self.answers.pop(0)

    def stream(self, system: str, prompt: str, *, context=None):
        async def gen():
            yield ""

        return gen()


def _judge_json(
    marks: dict[str, tuple[int, int]],
    *,
    evidence: dict[str, list[str]] | None = None,
    missing: dict[str, list[str]] | None = None,
    totals: dict[str, int] | None = None,
    duplicate: dict[str, str] | None = None,
    maxima: dict[str, dict[str, int]] | None = None,
    floats: dict[str, dict[str, float]] | None = None,
) -> str:
    results: dict[str, dict] = {}
    for item_id, (correctness, completeness) in marks.items():
        criteria = [
            {
                "criterion_id": "correctness",
                "awarded": correctness,
                "max_marks": 4,
                "reason": "Assesses the core statement.",
            },
            {
                "criterion_id": "completeness",
                "awarded": completeness,
                "max_marks": 4,
                "reason": "Assesses the supporting detail.",
            },
        ]
        if missing and item_id in missing:
            criteria = [
                criterion
                for criterion in criteria
                if criterion["criterion_id"] not in missing[item_id]
            ]
        if duplicate and item_id in duplicate:
            duplicate_id = duplicate[item_id]
            criteria.append(
                next(
                    dict(criterion)
                    for criterion in criteria
                    if criterion["criterion_id"] == duplicate_id
                )
            )
        if maxima and item_id in maxima:
            for criterion in criteria:
                if criterion["criterion_id"] in maxima[item_id]:
                    criterion["max_marks"] = maxima[item_id][criterion["criterion_id"]]
        if floats and item_id in floats:
            for criterion in criteria:
                if criterion["criterion_id"] in floats[item_id]:
                    criterion["awarded"] = floats[item_id][criterion["criterion_id"]]
        results[item_id] = {
            "criteria": criteria,
            "total": (
                totals[item_id]
                if totals and item_id in totals
                else sum(criterion["awarded"] for criterion in criteria)
            ),
            "feedback": "The answer is assessed against the rubric.",
            "evidence_ids": (
                evidence[item_id]
                if evidence and item_id in evidence
                else [REF.chunk_id]
            ),
        }
    return json.dumps({"results": results})


def _answer(item_id: str, text: str = "A sample answer.") -> AttemptAnswer:
    return AttemptAnswer(item_id=item_id, answer_text=text)


@pytest.mark.parametrize(
    ("total", "band"),
    [
        (0, "T"),
        (14, "T"),
        (15, "D"),
        (24, "D"),
        (25, "P"),
        (34, "P"),
        (35, "A"),
        (39, "A"),
        (40, "E"),
        (44, "E"),
        (45, "O"),
        (50, "O"),
    ],
)
def test_band_thresholds(total: int, band: str) -> None:
    assert band_for(total, 50) == band


def test_band_rejects_impossible_scores() -> None:
    with pytest.raises(ValueError):
        band_for(-1, 50)
    with pytest.raises(ValueError):
        band_for(51, 50)
    with pytest.raises(ValueError):
        band_for(0, 0)


def test_mcq_scores_by_option_id_only() -> None:
    item = _bank().find_item("dada-mcq-001")
    assert item is not None
    correct = score_mcq(item, "a")
    assert correct.marks_awarded == 3
    assert correct.correct is True
    assert correct.correct_option_id == "a"
    assert correct.model_answer == "Riddikulus"
    assert correct.evidence_ids == (REF.chunk_id,)

    wrong = score_mcq(item, "b")
    assert wrong.marks_awarded == 0
    assert wrong.correct is False

    blank = score_mcq(item, None)
    assert blank.marks_awarded == 0
    assert blank.feedback == "No option selected."

    with pytest.raises(ValueError, match="unknown option id"):
        score_mcq(item, "z")


async def test_mcq_only_attempt_needs_no_judge() -> None:
    bank = _bank()
    result = await grade_attempt(
        bank,
        ["dada-mcq-001"],
        [AttemptAnswer(item_id="dada-mcq-001", option_id="a")],
        llm=None,
    )
    assert result.total == 3
    assert result.max_marks == 3
    assert result.band == "O"
    assert result.needs_review is False
    assert result.judge_output_sha256 is None


async def test_one_judge_call_for_all_short_answers() -> None:
    bank = _bank()
    llm = ScriptedLlm(
        _judge_json(
            {
                "dada-short-001": (4, 4),
                "dada-short-002": (3, 2),
            }
        )
    )
    answers = [
        AttemptAnswer(item_id="dada-mcq-001", option_id="b"),
        _answer("dada-short-001"),
        _answer("dada-short-002"),
    ]
    result = await grade_attempt(
        bank,
        ["dada-mcq-001", "dada-short-001", "dada-short-002"],
        answers,
        llm=llm,
        now=datetime(2026, 11, 9, tzinfo=UTC),
    )
    assert len(llm.calls) == 1
    assert result.total == 13
    assert result.max_marks == 19
    assert result.band == "P"
    assert result.needs_review is False
    assert result.graded_at == "2026-11-09T00:00:00Z"
    assert result.judge_output_sha256 is not None
    assert result.judge_provider == settings.exam_judge_provider
    assert result.judge_max_tokens == settings.exam_judge_max_tokens
    assert [question.marks_awarded for question in result.questions] == [0, 8, 5]
    assert result.questions[1].feedback.endswith(f"[{REF.chunk_id}]")
    assert [
        criterion.criterion_id for criterion in result.questions[1].criteria
    ] == ["correctness", "completeness"]


@pytest.mark.parametrize(
    ("label", "marks", "expected_total", "expected_band"),
    [
        ("full", (4, 4), 8, "O"),
        ("partial", (2, 2), 4, "P"),
        ("off-topic", (0, 0), 0, "T"),
        ("contradictory", (1, 0), 1, "T"),
        ("verbose", (4, 4), 8, "O"),
    ],
)
async def test_short_answer_states(
    label: str,
    marks: tuple[int, int],
    expected_total: int,
    expected_band: str,
) -> None:
    bank = _bank()
    llm = ScriptedLlm(_judge_json({"dada-short-001": marks}))
    result = await grade_attempt(
        bank,
        ["dada-short-001"],
        [_answer("dada-short-001", f"{label} answer")],
        llm=llm,
    )
    assert len(llm.calls) == 1
    assert result.questions[0].marks_awarded == expected_total
    assert result.total == expected_total
    assert result.band == expected_band


async def test_blank_short_answer_scores_zero_without_judge() -> None:
    bank = _bank()
    llm = ScriptedLlm()
    result = await grade_attempt(
        bank,
        ["dada-short-001"],
        [_answer("dada-short-001", "")],
        llm=llm,
    )
    assert len(llm.calls) == 0
    assert result.questions[0].marks_awarded == 0
    assert all(criterion.awarded == 0 for criterion in result.questions[0].criteria)
    assert result.total == 0
    assert result.band == "T"


async def test_unanswered_mcq_scores_zero() -> None:
    bank = _bank()
    result = await grade_attempt(bank, ["dada-mcq-001"], [], llm=None)
    assert result.questions[0].marks_awarded == 0
    assert result.questions[0].correct is False
    assert result.total == 0
    assert result.band == "T"


async def test_malformed_json_retries_once() -> None:
    bank = _bank()
    llm = ScriptedLlm(
        "not json",
        _judge_json({"dada-short-001": (4, 4)}),
    )
    result = await grade_attempt(
        bank,
        ["dada-short-001"],
        [_answer("dada-short-001")],
        llm=llm,
    )
    assert len(llm.calls) == 2
    assert result.needs_review is False
    assert result.total == 8


async def test_malformed_twice_needs_review() -> None:
    bank = _bank()
    llm = ScriptedLlm("not json", "still not json")
    result = await grade_attempt(
        bank,
        ["dada-short-001"],
        [_answer("dada-short-001")],
        llm=llm,
    )
    assert len(llm.calls) == 2
    assert result.needs_review is True
    assert result.total is None
    assert result.band is None
    assert result.questions[0].needs_review is True
    assert result.questions[0].marks_awarded is None
    assert "needs review" in result.questions[0].feedback
    assert REF.chunk_id in result.questions[0].feedback


async def test_missing_criterion_retries() -> None:
    bank = _bank()
    llm = ScriptedLlm(
        _judge_json(
            {"dada-short-001": (4, 4)},
            missing={"dada-short-001": ["completeness"]},
        ),
        _judge_json({"dada-short-001": (4, 4)}),
    )
    result = await grade_attempt(
        bank,
        ["dada-short-001"],
        [_answer("dada-short-001")],
        llm=llm,
    )
    assert len(llm.calls) == 2
    assert result.needs_review is False
    assert result.total == 8


async def test_out_of_range_mark_retries() -> None:
    bank = _bank()
    llm = ScriptedLlm(
        _judge_json({"dada-short-001": (5, 4)}),
        _judge_json({"dada-short-001": (4, 4)}),
    )
    result = await grade_attempt(
        bank,
        ["dada-short-001"],
        [_answer("dada-short-001")],
        llm=llm,
    )
    assert len(llm.calls) == 2
    assert result.needs_review is False
    assert result.total == 8


async def test_total_mismatch_retries() -> None:
    bank = _bank()
    llm = ScriptedLlm(
        _judge_json(
            {"dada-short-001": (4, 4)},
            totals={"dada-short-001": 99},
        ),
        _judge_json({"dada-short-001": (4, 4)}),
    )
    result = await grade_attempt(
        bank,
        ["dada-short-001"],
        [_answer("dada-short-001")],
        llm=llm,
    )
    assert len(llm.calls) == 2
    assert result.needs_review is False
    assert result.total == 8


async def test_unknown_evidence_id_retries() -> None:
    bank = _bank()
    llm = ScriptedLlm(
        _judge_json(
            {"dada-short-001": (4, 4)},
            evidence={"dada-short-001": ["b9-c99-9999"]},
        ),
        _judge_json({"dada-short-001": (4, 4)}),
    )
    result = await grade_attempt(
        bank,
        ["dada-short-001"],
        [_answer("dada-short-001")],
        llm=llm,
    )
    assert len(llm.calls) == 2
    assert result.needs_review is False
    assert result.total == 8


async def test_duplicate_criterion_retries() -> None:
    bank = _bank()
    llm = ScriptedLlm(
        _judge_json(
            {"dada-short-001": (4, 4)},
            missing={"dada-short-001": ["completeness"]},
            duplicate={"dada-short-001": "correctness"},
        ),
        _judge_json({"dada-short-001": (4, 4)}),
    )
    result = await grade_attempt(
        bank,
        ["dada-short-001"],
        [_answer("dada-short-001")],
        llm=llm,
    )
    assert len(llm.calls) == 2
    assert result.needs_review is False
    assert result.total == 8


async def test_max_marks_mismatch_retries() -> None:
    bank = _bank()
    llm = ScriptedLlm(
        _judge_json(
            {"dada-short-001": (4, 4)},
            maxima={"dada-short-001": {"correctness": 5}},
        ),
        _judge_json({"dada-short-001": (4, 4)}),
    )
    result = await grade_attempt(
        bank,
        ["dada-short-001"],
        [_answer("dada-short-001")],
        llm=llm,
    )
    assert len(llm.calls) == 2
    assert result.needs_review is False
    assert result.total == 8


async def test_negative_mark_retries() -> None:
    bank = _bank()
    llm = ScriptedLlm(
        _judge_json({"dada-short-001": (-1, 4)}),
        _judge_json({"dada-short-001": (4, 4)}),
    )
    result = await grade_attempt(
        bank,
        ["dada-short-001"],
        [_answer("dada-short-001")],
        llm=llm,
    )
    assert len(llm.calls) == 2
    assert result.needs_review is False
    assert result.total == 8


async def test_non_integer_mark_retries() -> None:
    bank = _bank()
    llm = ScriptedLlm(
        _judge_json(
            {"dada-short-001": (4, 4)},
            floats={"dada-short-001": {"correctness": 3.0}},
        ),
        _judge_json({"dada-short-001": (4, 4)}),
    )
    result = await grade_attempt(
        bank,
        ["dada-short-001"],
        [_answer("dada-short-001")],
        llm=llm,
    )
    assert len(llm.calls) == 2
    assert result.needs_review is False
    assert result.total == 8


async def test_mixed_retry_keeps_the_valid_item() -> None:
    bank = _bank()
    llm = ScriptedLlm(
        _judge_json(
            {"dada-short-001": (4, 4), "dada-short-002": (4, 4)},
            missing={"dada-short-002": ["completeness"]},
        ),
        _judge_json({"dada-short-002": (4, 4)}),
    )
    result = await grade_attempt(
        bank,
        ["dada-short-001", "dada-short-002"],
        [_answer("dada-short-001"), _answer("dada-short-002")],
        llm=llm,
    )
    assert len(llm.calls) == 2
    assert result.needs_review is False
    assert result.total == 16
    assert [question.marks_awarded for question in result.questions] == [8, 8]


async def test_cache_hit_skips_second_call(tmp_path) -> None:
    bank = _bank()
    path = tmp_path / "judge_cache.jsonl"
    first_llm = ScriptedLlm(_judge_json({"dada-short-001": (4, 4)}))
    first = await grade_attempt(
        bank,
        ["dada-short-001"],
        [_answer("dada-short-001", "The same answer.")],
        llm=first_llm,
        cache=JudgeCache(path),
    )
    second = await grade_attempt(
        bank,
        ["dada-short-001"],
        [_answer("dada-short-001", "The same answer.")],
        llm=None,
        cache=JudgeCache(path),
    )
    assert len(first_llm.calls) == 1
    assert second.total == first.total == 8
    assert second.judge_output_sha256 is None
    assert second.questions[0].judge_response_sha256 is not None


async def test_cache_entry_records_the_full_pins(tmp_path) -> None:
    bank = _bank()
    path = tmp_path / "judge_cache.jsonl"
    llm = ScriptedLlm(_judge_json({"dada-short-001": (4, 4)}))
    await grade_attempt(
        bank,
        ["dada-short-001"],
        [_answer("dada-short-001", "Pinned answer.")],
        llm=llm,
        cache=JudgeCache(path),
    )
    entry = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert entry["bank_version"] == "1.0.0"
    assert entry["item_id"] == "dada-short-001"
    assert entry["rubric_version"] == "dada-bank-v1"
    assert entry["judge_model"] == bank.manifest.judge_model
    assert entry["judge_provider"] == settings.exam_judge_provider
    assert entry["judge_temperature"] == 0.0
    assert entry["judge_max_tokens"] == settings.exam_judge_max_tokens
    assert entry["judge_prompt_version"] == "dada-bank-judge-v2"
    assert entry["answer_sha256"]
    assert entry["raw_sha256"]


async def test_cache_misses_on_a_different_answer(tmp_path) -> None:
    bank = _bank()
    path = tmp_path / "judge_cache.jsonl"
    first_llm = ScriptedLlm(_judge_json({"dada-short-001": (4, 4)}))
    await grade_attempt(
        bank,
        ["dada-short-001"],
        [_answer("dada-short-001", "The first answer.")],
        llm=first_llm,
        cache=JudgeCache(path),
    )
    second_llm = ScriptedLlm(_judge_json({"dada-short-001": (2, 2)}))
    second = await grade_attempt(
        bank,
        ["dada-short-001"],
        [_answer("dada-short-001", "A different answer.")],
        llm=second_llm,
        cache=JudgeCache(path),
    )
    assert len(second_llm.calls) == 1
    assert second.total == 4


async def test_needs_review_is_not_cached(tmp_path) -> None:
    bank = _bank()
    path = tmp_path / "judge_cache.jsonl"
    llm = ScriptedLlm("not json", "still not json")
    result = await grade_attempt(
        bank,
        ["dada-short-001"],
        [_answer("dada-short-001")],
        llm=llm,
        cache=JudgeCache(path),
    )
    assert result.needs_review is True
    assert not path.exists()


async def test_cache_key_changes_with_the_rubric(tmp_path) -> None:
    bank = _bank()
    path = tmp_path / "judge_cache.jsonl"
    first_llm = ScriptedLlm(_judge_json({"dada-short-001": (4, 4)}))
    await grade_attempt(
        bank,
        ["dada-short-001"],
        [_answer("dada-short-001", "The same answer.")],
        llm=first_llm,
        cache=JudgeCache(path),
    )
    item = bank.find_item("dada-short-001")
    assert item is not None
    changed = item.model_copy(
        update={
            "rubric": (
                RubricCriterion(
                    criterion_id="correctness",
                    description="Changed correctness.",
                    max_marks=4,
                ),
                RubricCriterion(
                    criterion_id="completeness",
                    description="Changed completeness.",
                    max_marks=4,
                ),
            )
        }
    )
    changed_bank = ExamBank(manifest=bank.manifest, items=[changed])
    second_llm = ScriptedLlm(_judge_json({"dada-short-001": (2, 2)}))
    second = await grade_attempt(
        changed_bank,
        ["dada-short-001"],
        [_answer("dada-short-001", "The same answer.")],
        llm=second_llm,
        cache=JudgeCache(path),
    )
    assert len(second_llm.calls) == 1
    assert second.total == 4


async def test_judge_must_be_a_different_family() -> None:
    bank = _bank(generator_model="mistralai/mistral-small-3.2-24b-instruct")
    with pytest.raises(ValueError, match="different model family"):
        await grade_attempt(
            bank,
            ["dada-short-001"],
            [_answer("dada-short-001")],
            llm=ScriptedLlm("{}"),
        )


async def test_family_aliases_do_not_bypass_the_family_gate() -> None:
    bank = _bank(
        generator_model="mistralai/mistral-small-3.2-24b-instruct",
        judge_model="mistral.mistral-large-2411",
    )
    with pytest.raises(ValueError, match="different model family"):
        await grade_attempt(
            bank,
            ["dada-short-001"],
            [_answer("dada-short-001")],
            llm=ScriptedLlm("{}"),
        )


async def test_judge_prompt_version_must_match() -> None:
    bank = _bank(judge_prompt_version="other")
    with pytest.raises(ValueError, match="prompt version"):
        await grade_attempt(
            bank,
            ["dada-short-001"],
            [_answer("dada-short-001")],
            llm=ScriptedLlm("{}"),
        )


def test_neutral_judge_prompt_version_is_accepted() -> None:
    bank = _bank(judge_prompt_version="owl-bank-judge-v3")
    judge_llm_from_bank(bank)


async def test_neutral_judge_prompt_is_subject_agnostic() -> None:
    bank = _bank(judge_prompt_version="owl-bank-judge-v3")
    llm = ScriptedLlm(_judge_json({"dada-short-001": (4, 4)}))
    result = await grade_attempt(
        bank,
        ["dada-short-001"],
        [_answer("dada-short-001")],
        llm=llm,
    )
    system = llm.calls[0][0]
    assert "O.W.L. subject bank" in system
    assert "Defence Against the Dark Arts" not in system
    assert result.judge_prompt_version == "owl-bank-judge-v3"
    assert result.questions[0].marks_awarded == 8


async def test_judge_temperature_must_be_zero() -> None:
    bank = _bank(judge_temperature=0.5)
    with pytest.raises(ValueError, match="temperature must be 0"):
        await grade_attempt(
            bank,
            ["dada-short-001"],
            [_answer("dada-short-001")],
            llm=ScriptedLlm("{}"),
        )


async def test_draft_bank_cannot_be_graded() -> None:
    bank = _bank(status="draft")
    with pytest.raises(ValueError, match="published bank"):
        await grade_attempt(
            bank,
            ["dada-short-001"],
            [_answer("dada-short-001")],
            llm=ScriptedLlm("{}"),
        )


def test_banned_judge_model_is_rejected() -> None:
    bank = _bank(judge_model="openai/gpt-4o")
    with pytest.raises(ValueError, match="banned vendor"):
        judge_llm_from_bank(bank)


def test_judge_llm_uses_bank_pins(monkeypatch) -> None:
    bank = _bank()
    captured: dict[str, object] = {}

    def fake_make_llm(provider: str, **kwargs: object) -> object:
        captured["provider"] = provider
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("app.grading.judge.make_llm", fake_make_llm)
    judge_llm_from_bank(bank)
    assert captured["provider"] == settings.exam_judge_provider
    assert captured["model"] == bank.manifest.judge_model
    assert captured["temperature"] == 0.0
    assert captured["max_tokens"] == settings.exam_judge_max_tokens


def test_bedrock_llm_passes_max_tokens(monkeypatch) -> None:
    from app.providers.factory import make_llm

    captured: dict[str, object] = {}

    class FakeBedrockLlm:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("app.providers.factory.BedrockLlm", FakeBedrockLlm)
    make_llm("bedrock", model="qwen.qwen3-32b-v1:0", max_tokens=1800)
    assert captured["max_tokens"] == 1800


async def test_answer_shape_must_match_item_kind() -> None:
    bank = _bank()
    with pytest.raises(ValueError, match="MCQ answers use option_id"):
        await grade_attempt(
            bank,
            ["dada-mcq-001"],
            [AttemptAnswer(item_id="dada-mcq-001", answer_text="Riddikulus")],
            llm=None,
        )
    with pytest.raises(ValueError, match="short answers use answer_text"):
        await grade_attempt(
            bank,
            ["dada-short-001"],
            [AttemptAnswer(item_id="dada-short-001", option_id="a")],
            llm=ScriptedLlm("{}"),
        )


async def test_answer_outside_attempt_raises() -> None:
    bank = _bank()
    with pytest.raises(ValueError, match="outside the attempt"):
        await grade_attempt(
            bank,
            ["dada-short-001"],
            [_answer("dada-short-002")],
            llm=ScriptedLlm("{}"),
        )


async def test_empty_attempt_raises() -> None:
    bank = _bank()
    with pytest.raises(ValueError, match="at least one item"):
        await grade_attempt(bank, [], [], llm=None)


async def test_duplicate_answer_raises() -> None:
    bank = _bank()
    with pytest.raises(ValueError, match="duplicate answer"):
        await grade_attempt(
            bank,
            ["dada-short-001"],
            [_answer("dada-short-001"), _answer("dada-short-001")],
            llm=ScriptedLlm("{}"),
        )


async def test_blank_option_id_scores_zero() -> None:
    bank = _bank()
    result = await grade_attempt(
        bank,
        ["dada-mcq-001"],
        [AttemptAnswer(item_id="dada-mcq-001", option_id="")],
        llm=None,
    )
    assert result.questions[0].marks_awarded == 0
    assert result.questions[0].feedback == "No option selected."
