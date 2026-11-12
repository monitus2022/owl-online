"""Lesson and multi-turn RAG evaluation (#248)."""

from eval.rag.check import (
    CheckError,
    RagCheckReport,
    check_rag,
    render_check,
)
from eval.rag.fixtures import (
    Conversation,
    LessonItem,
    Turn,
    load_conversations,
    load_lesson_items,
)
from eval.rag.metrics import (
    LessonMetrics,
    LessonResult,
    MultiTurnMetrics,
    RagReport,
    TurnResult,
    summarize_lesson,
    summarize_multiturn,
)
from eval.rag.report import (
    flatten,
    latest_report,
    load_report,
    render_report,
    to_dict,
    write_report,
)
from eval.rag.runner import (
    RagStack,
    build_stack,
    run_lesson,
    run_multiturn,
    run_rag_eval,
)

__all__ = [
    "CheckError",
    "Conversation",
    "LessonItem",
    "LessonMetrics",
    "LessonResult",
    "MultiTurnMetrics",
    "RagCheckReport",
    "RagReport",
    "RagStack",
    "Turn",
    "TurnResult",
    "build_stack",
    "check_rag",
    "flatten",
    "latest_report",
    "load_conversations",
    "load_lesson_items",
    "load_report",
    "render_check",
    "render_report",
    "run_lesson",
    "run_multiturn",
    "run_rag_eval",
    "summarize_lesson",
    "summarize_multiturn",
    "to_dict",
    "write_report",
]
