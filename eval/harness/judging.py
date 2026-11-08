"""Judge prompts, reply parsers, sample selection and the judged sample runner."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from app.knowledge.lore import LoreStore
from app.pipeline.generate import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_TOP_K,
    ask,
    render_evidence,
)
from app.providers.contracts import Llm, Retriever
from eval.harness.generation import JudgeVerdict, exact_match, token_f1
from eval.harness.gold import GoldItem

# Judge pinned in config/manifest.toml (AGENTS.md: a different family from the
# Qwen generator). The eval reads it from the manifest rather than restating it.
REPO = Path(__file__).resolve().parents[2]
JUDGE_MODEL = tomllib.loads(
    (REPO / "config" / "manifest.toml").read_text(encoding="utf-8")
)["judge"]["model"]

JUDGE_SYSTEM = (
    "You grade a revision answer against the book excerpts provided. "
    'Reply with JSON only, no prose: {"correctness": "correct" | "partial" | '
    '"wrong", "grounded": true | false}. correctness is how well the answer '
    "matches the excerpts; grounded is whether every claim is supported by them."
)

# Separate from JUDGE_SYSTEM on purpose: the mechanical grounded flag is close to
# tautological because ask() abstains when nothing is cited. This prompt ignores
# citations and grades claim support only.
FAITHFUL_SYSTEM = (
    "You check whether an answer is supported by the excerpts provided. Ignore "
    "citations and whether the answer is correct in the wider world. A claim is "
    "supported only if the excerpts state it or it follows directly from them. "
    'Reply with JSON only, no prose: {"faithful": true | false}.'
)


def _as_bool(value: object) -> bool:
    """Accept JSON booleans and the string forms a judge might emit."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "1"}


def _first_json_object(raw: str) -> dict[str, object] | None:
    """The first flat JSON object in a reply; tolerates surrounding prose."""
    # First flat JSON object only: a greedy match could span several objects.
    match = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def parse_verdict(raw: str) -> tuple[str, bool] | None:
    """Pull correctness and grounded from a judge reply; tolerate extra prose.

    Returns None when the reply has no usable verdict, so a prompt drift cannot
    masquerade as a real wrong answer.
    """
    data = _first_json_object(raw)
    if data is None:
        return None
    correctness = str(data.get("correctness", "")).lower()
    if correctness not in {"correct", "partial", "wrong"}:
        return None
    return correctness, _as_bool(data.get("grounded", False))


def parse_faithful(raw: str) -> bool | None:
    """Pull the faithful flag from the separate claim-support judge reply."""
    data = _first_json_object(raw)
    if data is None or "faithful" not in data:
        return None
    return _as_bool(data["faithful"])


def sample_answerable(items: list[GoldItem], sample: int) -> list[GoldItem]:
    """Take up to `sample` answerable items, round-robin across slices.

    Round-robin keeps the judged sample representative when one slice is much
    larger than the others (simple has 34 items, named and multi have 8 each).
    """
    answerable = [item for item in items if item.answerable]
    if sample <= 0 or sample >= len(answerable):
        return answerable
    buckets: dict[str, list[GoldItem]] = {}
    for item in answerable:
        buckets.setdefault(item.primary_slice, []).append(item)
    picked: list[GoldItem] = []
    while len(picked) < sample:
        progressed = False
        for bucket in buckets.values():
            if bucket and len(picked) < sample:
                picked.append(bucket.pop(0))
                progressed = True
        if not progressed:
            break
    return picked


async def judge_sample(
    retriever: Retriever,
    llm: Llm,
    judge: Llm,
    items: list[GoldItem],
    sample: int = 15,
    top_k: int = DEFAULT_TOP_K,
    max_retries: int = DEFAULT_MAX_RETRIES,
    persona_suffix: str | None = None,
    lore: LoreStore | None = None,
    subject: str = "dada",
) -> list[JudgeVerdict]:
    """Generate answers for a slice-balanced sample and judge them.

    EM/F1 are scored against the item's reference answer. Faithfulness is a
    second, separate judge call that ignores citations. Abstained answers keep
    EM/F1 at zero and are excluded from the faithfulness denominator.
    """
    sampled = sample_answerable(items, sample)
    verdicts: list[JudgeVerdict] = []
    for item in sampled:
        chunks = await retriever.retrieve(item.question, top_k)
        result = await ask(
            item.question,
            retriever=retriever,
            llm=llm,
            top_k=top_k,
            max_retries=max_retries,
            persona_suffix=persona_suffix,
            lore=lore,
            subject=subject,
        )
        reference = item.reference_answer
        if result.abstained:
            verdicts.append(
                JudgeVerdict(
                    item.id,
                    "abstained",
                    False,
                    True,
                    answer=result.answer,
                    reference_answer=reference,
                    faithful=None,
                    em=0.0,
                    f1=0.0,
                )
            )
            continue
        evidence = render_evidence(chunks)
        prompt = (
            f"Excerpts:\n{evidence}\n\n"
            f"Question: {item.question}\n\n"
            f"Answer: {result.answer}"
        )
        correctness, grounded = ("wrong", False)
        verdict = parse_verdict(await judge.generate(JUDGE_SYSTEM, prompt))
        judge_parse_failed = verdict is None
        if verdict is not None:
            correctness, grounded = verdict
        faithful_reply = parse_faithful(await judge.generate(FAITHFUL_SYSTEM, prompt))
        faithful_parse_failed = faithful_reply is None
        faithful = bool(faithful_reply) if faithful_reply is not None else False
        verdicts.append(
            JudgeVerdict(
                item.id,
                correctness,
                grounded,
                False,
                answer=result.answer,
                reference_answer=reference,
                faithful=faithful,
                em=exact_match(result.answer, reference),
                f1=token_f1(result.answer, reference),
                judge_parse_failed=judge_parse_failed,
                faithful_parse_failed=faithful_parse_failed,
            )
        )
    return verdicts