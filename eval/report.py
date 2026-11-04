"""Result rows and printed summary for one eval run."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from eval.harness import AbstentionMetrics, GenerationMetrics, RetrievalMetrics
from eval.results import ResultRow


@dataclass(frozen=True)
class RunReport:
    """Everything one run produced, ready to render."""

    run_path: Path
    baseline_path: Path | None
    config: str
    generator: str
    judge: str
    reranker: str
    gold_total: int
    answerable: int
    unanswerable: int
    k: int
    retrieval: RetrievalMetrics
    retrieval_by_slice: dict[str, RetrievalMetrics]
    abstention: AbstentionMetrics
    abstention_by_slice: dict[str, AbstentionMetrics]
    generation: GenerationMetrics
    generation_by_slice: dict[str, GenerationMetrics]


def retrieval_rows(
    run_id: str,
    config: str,
    manifest: dict[str, str],
    overall: RetrievalMetrics,
    by_slice: dict[str, RetrievalMetrics],
) -> list[ResultRow]:
    """Hit/Recall/MRR for the overall set and each answerable slice."""
    rows = [
        ResultRow(run_id, config, "overall", "hit_at_k", overall.hit_at_k, manifest),
        ResultRow(run_id, config, "overall", "recall_at_k", overall.recall_at_k, manifest),
        ResultRow(run_id, config, "overall", "mrr", overall.mrr, manifest),
    ]
    for name, metrics in by_slice.items():
        rows.extend(
            [
                ResultRow(run_id, config, name, "hit_at_k", metrics.hit_at_k, manifest),
                ResultRow(run_id, config, name, "recall_at_k", metrics.recall_at_k, manifest),
                ResultRow(run_id, config, name, "mrr", metrics.mrr, manifest),
            ]
        )
    return rows


def abstention_rows(
    run_id: str,
    config: str,
    manifest: dict[str, str],
    overall: AbstentionMetrics,
    by_slice: dict[str, AbstentionMetrics],
) -> list[ResultRow]:
    """Refusal counts and rate for the overall set and each unanswerable slice."""
    rows = [
        ResultRow(run_id, config, "overall", "abstention_n", overall.n, manifest),
        ResultRow(run_id, config, "overall", "abstention_refused", overall.refused, manifest),
        ResultRow(run_id, config, "overall", "abstention_rate", overall.rate, manifest),
    ]
    for name, metrics in by_slice.items():
        rows.extend(
            [
                ResultRow(run_id, config, name, "abstention_n", metrics.n, manifest),
                ResultRow(run_id, config, name, "abstention_refused", metrics.refused, manifest),
                ResultRow(run_id, config, name, "abstention_rate", metrics.rate, manifest),
            ]
        )
    return rows


def generation_rows(
    run_id: str,
    config: str,
    manifest: dict[str, str],
    overall: GenerationMetrics,
    by_slice: dict[str, GenerationMetrics],
) -> list[ResultRow]:
    """EM/F1, judge buckets and faithfulness for the overall set and each slice."""

    def metrics(name: str, m: GenerationMetrics) -> list[ResultRow]:
        return [
            ResultRow(run_id, config, name, "generation_n", m.n, manifest),
            ResultRow(run_id, config, name, "answered", m.answered, manifest),
            ResultRow(run_id, config, name, "abstained", m.abstained, manifest),
            ResultRow(run_id, config, name, "em", m.em, manifest),
            ResultRow(run_id, config, name, "f1", m.f1, manifest),
            ResultRow(run_id, config, name, "judge_correct", m.correct, manifest),
            ResultRow(run_id, config, name, "judge_partial", m.partial, manifest),
            ResultRow(run_id, config, name, "judge_wrong", m.wrong, manifest),
            ResultRow(run_id, config, name, "grounded", m.grounded, manifest),
            ResultRow(run_id, config, name, "faithful", m.faithful, manifest),
            ResultRow(run_id, config, name, "faithfulness_n", m.faithfulness_n, manifest),
        ]

    rows = metrics("overall", overall)
    for name, m in by_slice.items():
        rows.extend(metrics(name, m))
    return rows


def _retrieval_lines(
    k: int,
    overall: RetrievalMetrics,
    by_slice: dict[str, RetrievalMetrics],
) -> list[str]:
    lines = [
        "retrieval",
        f"  {'overall':<22} n={overall.n:<3} "
        f"Hit@{k}={overall.hit_at_k:.2f} Recall@{k}={overall.recall_at_k:.2f} "
        f"MRR={overall.mrr:.2f}",
    ]
    for name, m in by_slice.items():
        lines.append(
            f"  {name:<22} n={m.n:<3} "
            f"Hit@{k}={m.hit_at_k:.2f} Recall@{k}={m.recall_at_k:.2f} MRR={m.mrr:.2f}"
        )
    return lines


def _abstention_lines(
    overall: AbstentionMetrics,
    by_slice: dict[str, AbstentionMetrics],
) -> list[str]:
    lines = [
        "abstention",
        f"  {'overall':<22} {overall.refused}/{overall.n} ({overall.rate:.2f})",
    ]
    for name, m in by_slice.items():
        lines.append(f"  {name:<22} {m.refused}/{m.n} ({m.rate:.2f})")
    return lines


def _generation_lines(
    overall: GenerationMetrics,
    by_slice: dict[str, GenerationMetrics],
) -> list[str]:
    def line(name: str, m: GenerationMetrics) -> str:
        return (
            f"  {name:<22} n={m.n:<3} answered={m.answered:<3} abstained={m.abstained:<3} "
            f"EM={m.em:.2f} F1={m.f1:.2f} faithful={m.faithful}/{m.faithfulness_n} "
            f"judge correct={m.correct} partial={m.partial} wrong={m.wrong} "
            f"grounded={m.grounded}"
        )

    lines = ["generation (judged sample)", line("overall", overall)]
    for name, m in by_slice.items():
        lines.append(line(name, m))
    return lines


def render_run(report: RunReport) -> str:
    """Render one run as the text the CLI prints."""
    lines = [
        f"gold: {report.gold_total} items "
        f"({report.answerable} answerable, {report.unanswerable} unanswerable)",
        f"config: {report.config}",
        f"generator: {report.generator}",
        f"judge: {report.judge}",
        f"reranker: {report.reranker}",
        "",
    ]
    lines.extend(_retrieval_lines(report.k, report.retrieval, report.retrieval_by_slice))
    lines.append("")
    lines.extend(_abstention_lines(report.abstention, report.abstention_by_slice))
    lines.append("")
    lines.extend(_generation_lines(report.generation, report.generation_by_slice))
    lines.extend(["", f"wrote {report.run_path}"])
    if report.baseline_path is not None:
        lines.append(f"wrote baseline {report.baseline_path}")
    return "\n".join(lines)