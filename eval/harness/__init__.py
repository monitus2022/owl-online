"""Eval harness: gold set, retrieval, abstention, generation and judging.

Each concern lives in its own module; the public names are re-exported here so
callers keep importing from `eval.harness`.
"""

from eval.harness.abstention import (
    AbstentionMetrics,
    AbstentionScore,
    abstention_metrics,
    abstention_metrics_all,
    abstention_metrics_by_slice,
    abstention_scores,
    summarize_abstention,
)
from eval.harness.cache import CachedLlm
from eval.harness.generation import (
    GenerationMetrics,
    JudgeVerdict,
    exact_match,
    generation_metrics_by_slice,
    normalize_answer,
    strip_citations,
    summarize_generation,
    token_f1,
)
from eval.harness.gold import GoldItem, load_gold
from eval.harness.judging import (
    FAITHFUL_SYSTEM,
    JUDGE_MODEL,
    JUDGE_SYSTEM,
    judge_sample,
    parse_faithful,
    parse_verdict,
    sample_answerable,
)
from eval.harness.retrieval import (
    DiagnosticScore,
    RetrievalDiagnostics,
    RetrievalMetrics,
    RetrievalScore,
    retrieval_diagnostic_scores,
    retrieval_diagnostics_all,
    retrieval_metrics,
    retrieval_metrics_all,
    retrieval_metrics_by_slice,
    retrieval_scores,
    summarize_diagnostics,
    summarize_retrieval,
)

__all__ = [
    "FAITHFUL_SYSTEM",
    "JUDGE_MODEL",
    "JUDGE_SYSTEM",
    "AbstentionMetrics",
    "AbstentionScore",
    "CachedLlm",
    "DiagnosticScore",
    "GenerationMetrics",
    "GoldItem",
    "JudgeVerdict",
    "RetrievalDiagnostics",
    "RetrievalMetrics",
    "RetrievalScore",
    "abstention_metrics",
    "abstention_metrics_all",
    "abstention_metrics_by_slice",
    "abstention_scores",
    "exact_match",
    "generation_metrics_by_slice",
    "judge_sample",
    "load_gold",
    "normalize_answer",
    "parse_faithful",
    "parse_verdict",
    "retrieval_metrics",
    "retrieval_metrics_all",
    "retrieval_metrics_by_slice",
    "retrieval_scores",
    "retrieval_diagnostic_scores",
    "retrieval_diagnostics_all",
    "sample_answerable",
    "strip_citations",
    "summarize_abstention",
    "summarize_diagnostics",
    "summarize_generation",
    "summarize_retrieval",
    "token_f1",
]