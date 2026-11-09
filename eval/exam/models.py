"""Report records for the DADA bank evaluation (#191)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Check:
    """One bank check. Ungated checks are diagnostics, not pass/fail gates."""

    name: str
    ok: bool
    detail: str
    gated: bool = True
    value: float | int | None = None
    threshold: float | int | None = None


@dataclass
class BankCheckReport:
    """Deterministic checks plus the coverage and duplicate measurements."""

    checks: list[Check] = field(default_factory=list)
    metrics: dict[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks if check.gated)

    @property
    def failures(self) -> list[Check]:
        return [check for check in self.checks if check.gated and not check.ok]


@dataclass
class IndependentReport:
    """Independent solver, distractor and golden-answer checks."""

    model: str
    temperature: float
    prompt_version: str
    mcq_total: int = 0
    mcq_key_matches: int = 0
    mcq_ambiguities: int = 0
    short_total: int = 0
    short_golden_ok: int = 0
    short_missing_points: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def mcq_accuracy(self) -> float:
        return self.mcq_key_matches / self.mcq_total if self.mcq_total else 0.0

    @property
    def ok(self) -> bool:
        return (
            not self.errors
            and self.mcq_total > 0
            and self.mcq_key_matches == self.mcq_total
            and self.mcq_ambiguities == 0
            and self.short_total > 0
            and self.short_golden_ok == self.short_total
            and self.short_missing_points == 0
        )


@dataclass(frozen=True)
class CalibrationCase:
    """One student-style answer with its human criterion marks."""

    item_id: str
    variant: str
    pass_name: str
    answer: str
    marks: dict[str, int]
    note: str = ""

    @property
    def total(self) -> int:
        return sum(self.marks.values())


@dataclass
class CalibrationDetail:
    """One judged calibration case against its human marks."""

    item_id: str
    variant: str
    human: int
    judge: int | None
    delta: int | None
    needs_review: bool
    criteria: dict[str, tuple[int, int]]


@dataclass
class CalibrationReport:
    """Agreement, error, retry and length-bias metrics for the judge."""

    model: str
    provider: str
    temperature: float
    prompt_version: str
    set_sha256: str
    n: int
    exact: float
    adjacent: float
    mae: float | None
    per_criterion: dict[str, float]
    calls: int
    passes: int
    retries: int
    needs_review: int
    verbose_delta: float | None
    word_count_correlation: float | None
    details: list[CalibrationDetail] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        if self.needs_review:
            return False
        if self.mae is None or self.adjacent < 0.9:
            return False
        return self.mae <= 1.5


@dataclass
class ExamEvalReport:
    """The full bank evaluation: deterministic, independent and calibration."""

    bank_version: str
    deterministic: BankCheckReport
    independent: IndependentReport | None = None
    calibration: CalibrationReport | None = None

    @property
    def ok(self) -> bool:
        return (
            self.deterministic.ok
            and (self.independent is None or self.independent.ok)
            and (self.calibration is None or self.calibration.ok)
        )
