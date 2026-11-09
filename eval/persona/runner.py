"""Run the persona-conformance fixture for a baseline and a candidate prompt.

The baseline is the pre-#176 lesson composition; the candidate is the shipped
persona-first composition. Both use the same selector, retriever, generator and
judge, so the only difference is the prompt. The judge never sees the condition.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable
from dataclasses import dataclass, field

from app.agent.persona import Persona
from app.agent.router import classify, meta_topic
from app.knowledge.lesson import LessonSelector
from app.knowledge.lore import LoreStore
from app.knowledge.packs import SubjectPack
from app.pipeline.generate import DEFAULT_TOP_K, ask, ask_lesson
from app.pipeline.generate.generate import ABSTAIN_MESSAGE
from app.providers.contracts import Llm, Retriever
from app.schemas import Chunk
from eval.persona.checks import Check, run_checks
from eval.persona.fixtures import PersonaScenario
from eval.persona.judge import judge_answer, wilson_lower_bound
from eval.persona.prompts import baseline_prompts

CONDITIONS = ("baseline", "candidate")
NOISE_BAND = 0.05


@dataclass(frozen=True)
class PersonaEvalStack:
    """The wired pieces the runner needs; the CLI builds them once."""

    persona: Persona
    selector: LessonSelector
    retriever: Retriever
    llm_for_sample: Callable[[int], Llm]
    judge: Llm
    pack: SubjectPack
    chunks_by_id: dict[str, Chunk]
    subject: str = "dada"
    lore: LoreStore | None = None
    lesson_top_k: int = 3
    lesson_min_score: float | None = None
    lesson_fallback: bool = True
    max_retries: int = 1


@dataclass(frozen=True)
class SampleResult:
    scenario_id: str
    condition: str
    sample: int
    route: str
    expected_route: str
    topic: str | None
    expected_topic: str | None
    scope: str | None
    expected_scopes: tuple[str, ...]
    abstained: bool
    citation_expected: bool
    judge_expected: bool
    answer: str
    checks: tuple[Check, ...]
    judge_score: int | None = None
    judge_reason: str = ""
    judge_parse_failed: bool = False
    error: str | None = None

    def check(self, name: str) -> bool:
        matches = [check for check in self.checks if check.name == name]
        return bool(matches) and all(check.ok for check in matches)

    @property
    def route_ok(self) -> bool:
        return self.route == self.expected_route

    @property
    def topic_ok(self) -> bool:
        return self.expected_topic is None or self.topic == self.expected_topic

    @property
    def scope_ok(self) -> bool:
        return not self.expected_scopes or self.scope in self.expected_scopes

    @property
    def boundary_ok(self) -> bool:
        return self.check("boundary")

    @property
    def style_ok(self) -> bool:
        return self.check("style")

    @property
    def length_ok(self) -> bool:
        return self.check("length")

    @property
    def citation_ok(self) -> bool:
        return (
            self.citation_expected
            and not self.abstained
            and self.check("citations")
        )

    @property
    def persona_pass(self) -> bool:
        return self.judge_score == 2


@dataclass(frozen=True)
class ConditionReport:
    condition: str
    samples: tuple[SampleResult, ...]

    @property
    def total(self) -> int:
        return len(self.samples)

    @property
    def errors(self) -> int:
        return sum(1 for sample in self.samples if sample.error is not None)

    @property
    def route_accuracy(self) -> float:
        return (
            sum(sample.route_ok for sample in self.samples) / self.total
            if self.total
            else 0.0
        )

    @property
    def topic_checked(self) -> int:
        return sum(1 for sample in self.samples if sample.expected_topic is not None)

    @property
    def topic_accuracy(self) -> float:
        if not self.topic_checked:
            return 1.0
        passed = sum(
            1
            for sample in self.samples
            if sample.expected_topic is not None and sample.topic_ok
        )
        return passed / self.topic_checked

    @property
    def scope_checked(self) -> int:
        return sum(1 for sample in self.samples if sample.expected_scopes)

    @property
    def scope_accuracy(self) -> float:
        return (
            sum(sample.scope_ok for sample in self.samples if sample.expected_scopes)
            / self.scope_checked
            if self.scope_checked
            else 1.0
        )

    @property
    def citation_checked(self) -> int:
        return sum(1 for sample in self.samples if sample.citation_expected)

    @property
    def citation_retention(self) -> float:
        if not self.citation_checked:
            return 1.0
        passed = sum(
            1 for sample in self.samples if sample.citation_ok
        )
        return passed / self.citation_checked

    @property
    def abstention_checked(self) -> int:
        return sum(1 for sample in self.samples if sample.expected_scopes)

    @property
    def abstention_accuracy(self) -> float:
        if not self.abstention_checked:
            return 1.0
        passed = sum(
            1
            for sample in self.samples
            if sample.expected_scopes and sample.check("abstention")
        )
        return passed / self.abstention_checked

    @property
    def boundary_violations(self) -> int:
        return sum(1 for sample in self.samples if not sample.boundary_ok)

    @property
    def style_violations(self) -> int:
        return sum(1 for sample in self.samples if not sample.style_ok)

    @property
    def length_violations(self) -> int:
        return sum(1 for sample in self.samples if not sample.length_ok)

    @property
    def judged(self) -> int:
        return sum(1 for sample in self.samples if sample.judge_score is not None)

    @property
    def expected_judged(self) -> int:
        return sum(1 for sample in self.samples if sample.judge_expected)

    @property
    def persona_passes(self) -> int:
        return sum(1 for sample in self.samples if sample.persona_pass)

    @property
    def persona_pass_rate(self) -> float:
        # The denominator is the full expected set, not only the answered
        # samples, so an abstention cannot shrink it and inflate the rate.
        return (
            self.persona_passes / self.expected_judged
            if self.expected_judged
            else 0.0
        )

    @property
    def persona_wilson_lb(self) -> float:
        return wilson_lower_bound(self.persona_passes, self.expected_judged)

    @property
    def mean_score(self) -> float:
        scores = [
            sample.judge_score
            for sample in self.samples
            if sample.judge_score is not None
        ]
        return statistics.fmean(scores) if scores else 0.0

    @property
    def score_variance(self) -> float:
        by_scenario: dict[str, list[int]] = {}
        for sample in self.samples:
            if sample.judge_score is not None:
                by_scenario.setdefault(sample.scenario_id, []).append(sample.judge_score)
        variances = [
            statistics.pvariance(scores)
            for scores in by_scenario.values()
            if len(scores) >= 2
        ]
        return statistics.fmean(variances) if variances else 0.0

    @property
    def judge_parse_failures(self) -> int:
        return sum(1 for sample in self.samples if sample.judge_parse_failed)


@dataclass(frozen=True)
class PersonaEvalReport:
    baseline: ConditionReport
    candidate: ConditionReport
    scenarios: int
    samples_per_scenario: int
    judge_model: str
    judge_temperature: float
    generator_model: str
    fixture_sha: str = ""
    calibration: object | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    def gate_reasons(self) -> list[str]:
        reasons: list[str] = []
        if self.candidate.errors:
            reasons.append(f"candidate errors: {self.candidate.errors}")
        if (
            self.candidate.citation_retention + NOISE_BAND
            < self.baseline.citation_retention
        ):
            reasons.append("citation retention dropped")
        if (
            self.candidate.abstention_accuracy + NOISE_BAND
            < self.baseline.abstention_accuracy
        ):
            reasons.append("abstention accuracy dropped")
        if self.candidate.boundary_violations:
            reasons.append(
                f"boundary violations: {self.candidate.boundary_violations}"
            )
        if self.candidate.style_violations:
            reasons.append(f"style violations: {self.candidate.style_violations}")
        if self.candidate.length_violations:
            reasons.append(f"length violations: {self.candidate.length_violations}")
        if self.candidate.judge_parse_failures:
            reasons.append(
                f"judge parse failures: {self.candidate.judge_parse_failures}"
            )
        if (
            self.candidate.persona_wilson_lb
            <= self.baseline.persona_pass_rate + NOISE_BAND
        ):
            reasons.append("persona pass rate did not improve beyond the noise band")
        if self.calibration is not None and not getattr(self.calibration, "ok", True):
            reasons.append("judge calibration failed")
        return reasons

    @property
    def ok(self) -> bool:
        return not self.gate_reasons()


def _abstention_expectation(route: str, scopes: tuple[str, ...]) -> str:
    if scopes == ("abstained",):
        return "required"
    if "abstained" in scopes:
        return "allowed"
    if route == "lesson" and not scopes:
        # An adversarial probe has no scope expectation; a refusal is a pass.
        return "allowed"
    return "forbidden"


def _abstention_check(
    *,
    expectation: str,
    abstained: bool,
    answer: str,
    persona: Persona,
) -> Check:
    reviewed = answer.strip() in set(persona.abstain_variants())
    if abstained and not (reviewed or answer.strip().startswith(ABSTAIN_MESSAGE)):
        return Check("abstention", False, "abstained without the in-world line")
    if expectation == "required" and not abstained:
        return Check("abstention", False, "expected abstention")
    if expectation == "forbidden" and abstained:
        return Check("abstention", False, "unexpected abstention")
    return Check("abstention", True, expectation)


async def _run_scenario(
    scenario: PersonaScenario,
    *,
    condition: str,
    sample: int,
    stack: PersonaEvalStack,
) -> SampleResult:
    route = classify(scenario.question, requested_mode="lesson", persona=True)
    topic: str | None = None
    scope: str | None = None
    abstained = False
    answer = ""
    checks: list[Check] = []
    try:
        llm = stack.llm_for_sample(sample)
        if route == "meta":
            topic = meta_topic(scenario.question) or scenario.topic or "identity"
            answer = stack.persona.meta_response(topic, choice=sample) or ""
        elif route == "personal":
            answer = stack.persona.personal_response(choice=sample)
        elif route == "lesson":
            if condition == "candidate":
                result = await ask_lesson(
                    scenario.question,
                    selector=stack.selector,
                    subject=stack.subject,
                    llm=llm,
                    retriever=stack.retriever,
                    fallback=stack.lesson_fallback,
                    top_k=stack.lesson_top_k,
                    min_score=stack.lesson_min_score,
                    max_retries=stack.max_retries,
                    persona=stack.persona,
                )
            else:
                result = await ask_lesson(
                    scenario.question,
                    selector=stack.selector,
                    subject=stack.subject,
                    llm=llm,
                    retriever=stack.retriever,
                    fallback=stack.lesson_fallback,
                    top_k=stack.lesson_top_k,
                    min_score=stack.lesson_min_score,
                    max_retries=stack.max_retries,
                    prompt_builder=lambda scope: baseline_prompts(
                        scope, stack.persona
                    ),
                )
            scope = result.scope
            abstained = result.abstained
            answer = (
                stack.persona.abstain_response(choice=sample)
                if result.abstained
                else result.answer
            )
        elif route == "answer":
            result = await ask(
                scenario.question,
                retriever=stack.retriever,
                llm=llm,
                top_k=DEFAULT_TOP_K,
                max_retries=stack.max_retries,
                persona_suffix=stack.persona.answer_suffix(),
                lore=stack.lore,
                subject=stack.subject,
            )
            abstained = result.abstained
            answer = (
                stack.persona.abstain_response(choice=sample)
                if result.abstained
                else result.answer
            )
        else:
            answer = ""

        checks.append(
            Check(
                "topic",
                scenario.topic is None or topic == scenario.topic,
                f"{topic} expected {scenario.topic}",
            )
        )
        expectation = _abstention_expectation(route, scenario.scopes)
        checks.append(
            _abstention_check(
                expectation=expectation,
                abstained=abstained,
                answer=answer,
                persona=stack.persona,
            )
        )
        checks.extend(
            run_checks(
                answer,
                persona=stack.persona,
                pack=stack.pack,
                chunks_by_id=stack.chunks_by_id,
                required=scenario.citation,
                abstained=abstained,
                max_words=scenario.max_words,
            )
        )
        judge_score: int | None = None
        judge_reason = ""
        judge_parse_failed = False
        if (
            route == "lesson"
            and not abstained
            and answer.strip()
            and scenario.citation != "none"
        ):
            verdict = await judge_answer(
                stack.judge, scenario, answer, persona=stack.persona
            )
            judge_score = verdict.score
            judge_reason = verdict.reason
            judge_parse_failed = verdict.parse_failed
        return SampleResult(
            scenario_id=scenario.scenario_id,
            condition=condition,
            sample=sample,
            route=route,
            expected_route=scenario.route,
            topic=topic,
            expected_topic=scenario.topic,
            scope=scope,
            expected_scopes=scenario.scopes,
            abstained=abstained,
            citation_expected=scenario.citation != "none",
            judge_expected=route == "lesson" and scenario.citation != "none",
            answer=answer,
            checks=tuple(checks),
            judge_score=judge_score,
            judge_reason=judge_reason,
            judge_parse_failed=judge_parse_failed,
        )
    except Exception as error:  # noqa: BLE001 - one failed sample must not end the run
        return SampleResult(
            scenario_id=scenario.scenario_id,
            condition=condition,
            sample=sample,
            route=route,
            expected_route=scenario.route,
            topic=topic,
            expected_topic=scenario.topic,
            scope=scope,
            expected_scopes=scenario.scopes,
            abstained=abstained,
            citation_expected=scenario.citation != "none",
            judge_expected=route == "lesson" and scenario.citation != "none",
            answer=answer,
            checks=tuple(checks),
            error=f"{type(error).__name__}: {error}",
        )


async def run_persona_eval(
    scenarios: list[PersonaScenario],
    stack: PersonaEvalStack,
    *,
    samples: int = 3,
    generator_model: str = "",
    judge_model: str = "",
    judge_temperature: float = 0.0,
    fixture_sha: str = "",
    calibration: object | None = None,
) -> PersonaEvalReport:
    """Run every scenario for both conditions, sample by sample."""
    results: dict[str, list[SampleResult]] = {condition: [] for condition in CONDITIONS}
    for scenario in scenarios:
        for condition in CONDITIONS:
            for sample in range(samples):
                results[condition].append(
                    await _run_scenario(
                        scenario,
                        condition=condition,
                        sample=sample,
                        stack=stack,
                    )
                )
    return PersonaEvalReport(
        baseline=ConditionReport("baseline", tuple(results["baseline"])),
        candidate=ConditionReport("candidate", tuple(results["candidate"])),
        scenarios=len(scenarios),
        samples_per_scenario=samples,
        judge_model=judge_model,
        judge_temperature=judge_temperature,
        generator_model=generator_model,
        fixture_sha=fixture_sha,
        calibration=calibration,
    )


def render_report(report: PersonaEvalReport) -> str:
    """Structure-only summary for the run record."""
    lines = [
        "persona conformance eval",
        "",
        f"scenarios={report.scenarios} samples_per_scenario={report.samples_per_scenario}",
        f"generator={report.generator_model}",
        f"judge={report.judge_model} temperature={report.judge_temperature}",
        f"fixture_sha={report.fixture_sha}",
        "",
        "| Metric | Baseline | Candidate |",
        "|---|---:|---:|",
    ]

    def row(name: str, left: object, right: object) -> None:
        lines.append(f"| {name} | {left} | {right} |")

    b = report.baseline
    c = report.candidate
    row("route accuracy", f"{b.route_accuracy:.4f}", f"{c.route_accuracy:.4f}")
    row("topic accuracy", f"{b.topic_accuracy:.4f}", f"{c.topic_accuracy:.4f}")
    row("scope accuracy", f"{b.scope_accuracy:.4f}", f"{c.scope_accuracy:.4f}")
    row("citation retention", f"{b.citation_retention:.4f}", f"{c.citation_retention:.4f}")
    row("abstention accuracy", f"{b.abstention_accuracy:.4f}", f"{c.abstention_accuracy:.4f}")
    row("boundary violations", b.boundary_violations, c.boundary_violations)
    row("style violations", b.style_violations, c.style_violations)
    row("length violations", b.length_violations, c.length_violations)
    row("persona pass rate", f"{b.persona_pass_rate:.4f}", f"{c.persona_pass_rate:.4f}")
    row("persona Wilson LB", f"{b.persona_wilson_lb:.4f}", f"{c.persona_wilson_lb:.4f}")
    row("mean voice score", f"{b.mean_score:.4f}", f"{c.mean_score:.4f}")
    row("score variance", f"{b.score_variance:.4f}", f"{c.score_variance:.4f}")
    row("expected judged samples", b.expected_judged, c.expected_judged)
    row("judged samples", b.judged, c.judged)
    row("judge parse failures", b.judge_parse_failures, c.judge_parse_failures)
    row("errors", b.errors, c.errors)
    if report.calibration is not None:
        calibration = report.calibration
        lines.extend(
            [
                "",
                "Calibration:",
                f"  n={getattr(calibration, 'n', 0)} "
                f"exact={getattr(calibration, 'exact', 0.0):.4f} "
                f"adjacent={getattr(calibration, 'adjacent', 0.0):.4f} "
                f"MAE={getattr(calibration, 'mae', 0.0):.4f} "
                f"parse_failures={getattr(calibration, 'parse_failures', 0)} "
                f"labels_adopted={getattr(calibration, 'labels_adopted', False)}",
            ]
        )
        for detail in getattr(calibration, "details", ()):
            lines.append(
                f"  {detail.case_id}: human={detail.human} judge={detail.judge} "
                f"delta={detail.delta}"
            )
    reasons = report.gate_reasons()
    lines.extend(["", f"gate: {'PASS' if report.ok else 'FAIL'}"])
    for reason in reasons:
        lines.append(f"  - {reason}")
    return "\n".join(lines)


__all__ = [
    "CONDITIONS",
    "ConditionReport",
    "PersonaEvalReport",
    "PersonaEvalStack",
    "SampleResult",
    "render_report",
    "run_persona_eval",
]
