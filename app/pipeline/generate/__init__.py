"""Grounded generation and the ask() entrypoint."""

from app.pipeline.generate.generate import (
    ABSTAIN_MESSAGE,
    CONVERSATION_NOTE,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MIN_SCORE,
    DEFAULT_TOP_K,
    RETRY_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    AskResult,
    ask,
    build_prompt,
    ground_answer,
    render_evidence,
    retrieval_floor,
    sanitize_evidence,
)
from app.pipeline.generate.lesson import ask_lesson, build_lesson_prompt, ground_lesson_answer
from app.pipeline.generate.verify import Verification, verify_draft

__all__ = [
    "ABSTAIN_MESSAGE",
    "CONVERSATION_NOTE",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_MIN_SCORE",
    "DEFAULT_TOP_K",
    "RETRY_SYSTEM_PROMPT",
    "SYSTEM_PROMPT",
    "AskResult",
    "Verification",
    "ask",
    "ask_lesson",
    "build_lesson_prompt",
    "build_prompt",
    "ground_answer",
    "ground_lesson_answer",
    "render_evidence",
    "retrieval_floor",
    "sanitize_evidence",
    "verify_draft",
]
