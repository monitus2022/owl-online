"""Generation metrics: exact match, token F1, judge buckets and faithfulness."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from eval.harness.gold import GoldItem


@dataclass(frozen=True)
class JudgeVerdict:
    """One generated answer: judge buckets, faithfulness, EM/F1, or abstained."""

    question_id: str
    correctness: str
    grounded: bool
    abstained: bool
    answer: str = ""
    reference_answer: str = ""
    faithful: bool | None = None
    em: float = 0.0
    f1: float = 0.0
    judge_parse_failed: bool = False
    faithful_parse_failed: bool = False


@dataclass(frozen=True)
class GenerationMetrics:
    """Aggregate EM/F1, judge buckets and independent faithfulness."""

    n: int
    answered: int
    abstained: int
    em: float
    f1: float
    correct: int
    partial: int
    wrong: int
    grounded: int
    faithful: int
    faithfulness_n: int
    judge_parse_failures: int = 0
    faithful_parse_failures: int = 0

    @property
    def judged(self) -> int:
        """Answers that reached the judge, including unparseable replies."""
        return self.correct + self.partial + self.wrong

    @property
    def faithfulness_rate(self) -> float:
        return self.faithful / self.faithfulness_n if self.faithfulness_n else 0.0

    @property
    def judge_correct_rate(self) -> float:
        return self.correct / self.judged if self.judged else 0.0


_ARTICLES = re.compile(r"\b(a|an|the)\b")
_PUNCTUATION = re.compile(r"[^a-z0-9\s]")
_CITATION = re.compile(r"\[[^\]]*\]")


def strip_citations(text: str) -> str:
    """Remove inline citation markers so they do not count as answer tokens."""
    return _CITATION.sub(" ", text)


def normalize_answer(text: str) -> str:
    """Lowercase, strip citations, punctuation and articles, and collapse whitespace."""
    text = _PUNCTUATION.sub(" ", strip_citations(text).lower())
    text = _ARTICLES.sub(" ", text)
    return " ".join(text.split())


def exact_match(prediction: str, reference: str) -> float:
    """1.0 when the normalized strings are equal, else 0.0."""
    return float(normalize_answer(prediction) == normalize_answer(reference))


def token_f1(prediction: str, reference: str) -> float:
    """Token-level F1 over the normalized strings (SQuAD convention)."""
    pred_tokens = normalize_answer(prediction).split()
    ref_tokens = normalize_answer(reference).split()
    if not pred_tokens or not ref_tokens:
        return float(pred_tokens == ref_tokens)
    overlap = sum((Counter(pred_tokens) & Counter(ref_tokens)).values())
    if overlap == 0:
        return 0.0
    precision = overlap / len(pred_tokens)
    recall = overlap / len(ref_tokens)
    return 2 * precision * recall / (precision + recall)


def summarize_generation(verdicts: list[JudgeVerdict]) -> GenerationMetrics:
    """Aggregate EM/F1 over all sampled items and faithfulness over answered ones."""
    n = len(verdicts)
    abstained = sum(verdict.abstained for verdict in verdicts)
    judged = [verdict for verdict in verdicts if not verdict.abstained]
    return GenerationMetrics(
        n=n,
        answered=n - abstained,
        abstained=abstained,
        em=sum(verdict.em for verdict in verdicts) / n if n else 0.0,
        f1=sum(verdict.f1 for verdict in verdicts) / n if n else 0.0,
        correct=sum(verdict.correctness == "correct" for verdict in judged),
        partial=sum(verdict.correctness == "partial" for verdict in judged),
        wrong=sum(verdict.correctness == "wrong" for verdict in judged),
        grounded=sum(verdict.grounded for verdict in verdicts),
        faithful=sum(verdict.faithful is True for verdict in judged),
        faithfulness_n=len(judged),
        judge_parse_failures=sum(verdict.judge_parse_failed for verdict in judged),
        faithful_parse_failures=sum(verdict.faithful_parse_failed for verdict in judged),
    )


def generation_metrics_by_slice(
    verdicts: list[JudgeVerdict], items: list[GoldItem]
) -> dict[str, GenerationMetrics]:
    """Generation metrics per answerable slice, from one judged sample."""
    by_id = {item.id: item for item in items}
    groups: dict[str, list[JudgeVerdict]] = {}
    for verdict in verdicts:
        groups.setdefault(by_id[verdict.question_id].primary_slice, []).append(verdict)
    return {name: summarize_generation(group) for name, group in sorted(groups.items())}