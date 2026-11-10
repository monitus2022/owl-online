"""Scripted persona nodes: meta and personal chat, no model call.

These answers are reviewed text from the persona card. They are not generated,
so the professor cannot invent a date, a rule or a fact while introducing
himself or answering a personal message.
"""

from collections.abc import Mapping

from app.agent.persona import Persona, active_persona
from app.agent.state import AgentState
from app.knowledge import LoreStore
from app.pipeline.generate.generate import ABSTAIN_MESSAGE


def _result(text: str) -> dict[str, object]:
    return {
        "answer": text,
        "citations": [],
        "typed_citations": [],
        "abstained": False,
        "chunks": [],
        "attempts": 0,
        "model_calls": 0,
        "retry_reason": None,
        "abstain_reason": None,
    }


def _active(
    state: AgentState,
    *,
    persona: Persona | None,
    personas: Mapping[str, Persona] | None,
    default_subject: str,
) -> Persona | None:
    cards = personas
    if cards is None and persona is not None:
        cards = {default_subject: persona}
    return active_persona(
        state.get("subject"),
        enabled=state.get("persona_enabled", True),
        personas=cards,
        default_subject=default_subject,
    )


def meta_node(
    state: AgentState,
    *,
    persona: Persona | None = None,
    personas: Mapping[str, Persona] | None = None,
    default_subject: str = "dada",
) -> dict[str, object]:
    active = _active(
        state, persona=persona, personas=personas, default_subject=default_subject
    )
    if active is None:
        return _result("")
    topic = state.get("meta_topic") or "identity"
    text = (
        active.meta_response(topic)
        or active.meta_response("boundaries")
        or ""
    )
    return _result(text)


def personal_node(
    state: AgentState,
    *,
    persona: Persona | None = None,
    personas: Mapping[str, Persona] | None = None,
    default_subject: str = "dada",
) -> dict[str, object]:
    active = _active(
        state, persona=persona, personas=personas, default_subject=default_subject
    )
    return _result(active.personal_response() if active is not None else "")


CLARIFY_RESPONSE = (
    "Do you mean what the subject covers, or what the examination will assess?"
)
POLICY_REFUSAL = (
    "I cannot answer that. I do not disclose the examination format or its contents."
)


def fact_node(
    state: AgentState,
    *,
    lore: LoreStore | None,
    persona: Persona | None = None,
    personas: Mapping[str, Persona] | None = None,
    default_subject: str = "dada",
) -> dict[str, object]:
    """A closed lore fact, returned from the reviewed setting pack."""
    active = _active(
        state, persona=persona, personas=personas, default_subject=default_subject
    )
    entries: list[str] = []
    citations: list[str] = []
    for fact_id in state.get("fact_ids", []):
        if not fact_id.startswith("lore:") or lore is None:
            continue
        entry = lore.get(fact_id[5:])
        if entry is None:
            continue
        entries.append(entry.body.strip())
        citations.append(entry.id)
    if not entries:
        text = active.abstain_response() if active is not None else ABSTAIN_MESSAGE
        result = _result(text)
        result["abstained"] = True
        result["abstain_reason"] = "no_evidence"
        return result
    result = _result("\n\n".join(entries))
    result["lore_citations"] = citations
    result["typed_citations"] = [
        fact_id
        for fact_id in state.get("fact_ids", [])
        if fact_id.startswith(("persona:", "lore:"))
    ]
    return result


def clarify_node(state: AgentState) -> dict[str, object]:
    """A scripted disambiguation for an ambiguous closed-fact ask."""
    return _result(CLARIFY_RESPONSE)


def policy_node(
    state: AgentState,
    *,
    persona: Persona | None = None,
    personas: Mapping[str, Persona] | None = None,
    default_subject: str = "dada",
) -> dict[str, object]:
    """A policy refusal, from the card when live and generic otherwise."""
    active = _active(
        state, persona=persona, personas=personas, default_subject=default_subject
    )
    topic = state.get("meta_topic") or "exam"
    text = (
        active.meta_response(topic) if active is not None else None
    ) or POLICY_REFUSAL
    subject = state.get("subject") or default_subject
    result = _result(text)
    result["typed_citations"] = [f"policy:script:assessment.{subject}"]
    return result


def abstain_node(
    state: AgentState,
    *,
    persona: Persona | None = None,
    personas: Mapping[str, Persona] | None = None,
    default_subject: str = "dada",
) -> dict[str, object]:
    """The in-world abstention for an unclassified teaching request."""
    active = _active(
        state, persona=persona, personas=personas, default_subject=default_subject
    )
    text = active.abstain_response() if active is not None else ABSTAIN_MESSAGE
    result = _result(text)
    result["abstained"] = True
    result["abstain_reason"] = "no_evidence"
    return result
