"""Scripted persona nodes: meta and personal chat, no model call.

These answers are reviewed text from the persona card. They are not generated,
so the professor cannot invent a date, a rule or a fact while introducing
himself or answering a personal message.
"""

from collections.abc import Mapping

from app.agent.persona import Persona, active_persona
from app.agent.state import AgentState


def _result(text: str) -> dict[str, object]:
    return {
        "answer": text,
        "citations": [],
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
