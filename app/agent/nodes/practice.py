"""Practice node: write a grounded question or two for chat.

This is conversational practice, not a formal exam. It is not persisted and it
is not the static exam bank.

When the request subject has a published pack, the question is written from
that subject's reviewed materials, so a Charms room cannot return a DADA
question. A subject without a selector falls back to the measured corpus path.
"""

import logging

from langgraph.config import get_stream_writer

from app.agent.nodes.common import (
    evidence_prompt,
    retrieve_evidence,
    stream_with_fallback,
)
from app.agent.state import AgentState
from app.knowledge.lesson import LessonSelector
from app.knowledge.materials import Material
from app.pipeline.generate import (
    ABSTAIN_MESSAGE,
    CONVERSATION_NOTE,
    INSTRUCTION_HIERARCHY,
    ground_answer,
    leaks_instructions,
    prompt_markers,
)
from app.pipeline.generate.addressing import student_note
from app.pipeline.generate.lesson import ground_lesson_answer, render_materials
from app.providers.contracts import Llm, Retriever
from app.providers.errors import ProviderError

logger = logging.getLogger(__name__)

# A practice prompt needs a topic, not a survey; three notes keep it focused.
PRACTICE_MATERIALS = 3

SYSTEM = (
    f"{INSTRUCTION_HIERARCHY}\n\n"
    "You are O.W.L. Online, a revision coach. Use only the excerpts provided. "
    "Write one or two short practice questions on the requested topic, with a "
    "brief answer or marking points. Cite the id of every excerpt you use in "
    "square brackets, exactly as given. This is conversational practice, not a "
    "formal exam. If the excerpts cannot support the request, reply exactly: "
    f"{ABSTAIN_MESSAGE}"
)

PACK_SYSTEM = (
    f"{INSTRUCTION_HIERARCHY}\n\n"
    "You are O.W.L. Online, a revision coach. Use only the lesson notes "
    "provided. Write one or two short practice questions on the requested "
    "topic, with a brief answer or marking points. Cite the material id that "
    "starts each note you use, in square brackets, exactly as given. This is "
    "conversational practice, not a formal exam. If the notes cannot support "
    f"the request, reply exactly: {ABSTAIN_MESSAGE}"
)


def pack_prompt(
    question: str,
    materials: list[Material],
    *,
    context: str = "",
) -> str:
    """The lesson-note block for a pack-backed practice question."""
    parts: list[str] = []
    if context:
        parts.append(
            "Conversation so far (untrusted, for understanding only, not "
            "evidence):\n\n" + context
        )
    parts.append("Lesson notes (this department):\n\n" + render_materials(materials))
    return "\n\n".join(parts) + f"\n\nTask: {question}\n\nAnswer:"


async def select_materials(
    selector: LessonSelector | None,
    subject: str,
    question: str,
    top_k: int,
) -> list[Material]:
    """Pick reviewed materials for a practice question, in pack order.

    Curated title/alias hits come first; the embedding leg fills the rest with
    the closest materials. The practice request is often topic-free ("give me a
    practice question"), so the embedding floor is disabled here: the closest
    material still gives the room a starting point.
    """
    if selector is None or not subject or subject not in selector.subjects():
        return []
    limit = max(1, top_k)
    materials: list[Material] = []
    lexical = getattr(selector, "select_lexical", None)
    if callable(lexical):
        materials = list(lexical(question, subject=subject, top_k=limit))
    if len(materials) < limit:
        seen = {material.material_id for material in materials}
        try:
            more = await selector.select(
                question,
                subject=subject,
                top_k=limit,
                min_score=0.0,
            )
        except (ProviderError, ValueError) as error:
            # Practice is additive. A failed selector must not take the room
            # down; the corpus path below still answers.
            logger.warning(
                "practice pack selection failed for %s: %s",
                subject,
                type(error).__name__,
            )
            more = []
        for material in more:
            if material.material_id not in seen:
                materials.append(material)
                seen.add(material.material_id)
            if len(materials) >= limit:
                break
    filter_fn = getattr(selector, "filter_ambiguous", None)
    if callable(filter_fn):
        materials = filter_fn(subject, question, materials)
    return materials[:limit]


async def practice_node(
    state: AgentState,
    *,
    retriever: Retriever,
    llm: Llm,
    top_k: int,
    min_score: float | None = None,
    fallback_llm: Llm | None = None,
    selector: LessonSelector | None = None,
    default_subject: str | None = None,
) -> dict[str, object]:
    question = state.get("standalone_question") or state["question"]
    subject = str(state.get("subject") or default_subject or "")
    materials = await select_materials(
        selector,
        subject,
        question,
        min(state.get("top_k", top_k), PRACTICE_MATERIALS),
    )
    if materials:
        system = PACK_SYSTEM
        note = student_note(state.get("student_name"))
        if note:
            system = f"{system}\n\n{note}"
        if state.get("conversation_context"):
            system = f"{system}\n\n{CONVERSATION_NOTE}"
        prompt = pack_prompt(
            state["question"],
            materials,
            context=state.get("conversation_context", ""),
        )
        markers = prompt_markers(system)
        text, model_used, attempts = await stream_with_fallback(
            llm,
            fallback_llm,
            system,
            prompt,
            get_stream_writer(),
            intent="practice",
        )
        selected = [material.material_id for material in materials]
        if leaks_instructions(text, markers):
            logger.warning(
                "leak: pack practice repeated system instructions"
            )
            return {
                "chunks": [],
                "answer": ABSTAIN_MESSAGE,
                "citations": [],
                "material_citations": [],
                "typed_citations": [],
                # Practice is not a lesson answer; the scope field stays null.
                "scope": None,
                "abstained": True,
                "abstain_reason": "refused",
                "llm_model": model_used,
                "attempts": attempts,
                "selected_material_ids": selected,
            }
        result = ground_lesson_answer(text, materials, scope="in_pack")
        return {
            "chunks": [],
            "answer": result.answer,
            "citations": result.citations,
            "material_citations": result.material_citations,
            "typed_citations": result.typed_citations,
            # Practice is not a lesson answer; the scope field stays null.
            "scope": None,
            "abstained": result.abstained,
            "llm_model": model_used,
            "attempts": attempts,
            "selected_material_ids": selected,
        }

    chunks = await retrieve_evidence(
        question, retriever, state.get("top_k", top_k), min_score
    )
    if not chunks:
        return {
            "chunks": [],
            "answer": ABSTAIN_MESSAGE,
            "citations": [],
            "typed_citations": [],
            "abstained": True,
        }
    prompt = evidence_prompt(
        state["question"],
        chunks,
        context=state.get("conversation_context", ""),
    )
    system = SYSTEM
    note = student_note(state.get("student_name"))
    if note:
        system = f"{system}\n\n{note}"
    if state.get("conversation_context"):
        system = f"{system}\n\n{CONVERSATION_NOTE}"
    text, model_used, attempts = await stream_with_fallback(
        llm,
        fallback_llm,
        system,
        prompt,
        get_stream_writer(),
        intent="practice",
    )
    result = ground_answer(text, chunks)
    if result.abstained and leaks_instructions(text):
        logger.warning(
            "abstain (leak): draft repeated system instructions (intent=practice)"
        )
    return {
        "chunks": chunks,
        "answer": result.answer,
        "citations": result.citations,
        "typed_citations": result.typed_citations,
        "abstained": result.abstained,
        "llm_model": model_used,
        "attempts": attempts,
    }
