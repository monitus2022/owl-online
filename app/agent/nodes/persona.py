"""Scripted persona nodes: meta and personal chat, no model call.

These answers are reviewed text from the persona card. They are not generated,
so the professor cannot invent a date, a rule or a fact while introducing
himself or answering a personal message.
"""

from app.agent.persona import Persona
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


def meta_node(state: AgentState, *, persona: Persona) -> dict[str, object]:
    topic = state.get("meta_topic") or "identity"
    text = persona.meta_response(topic) or persona.meta_response("boundaries") or ""
    return _result(text)


def personal_node(state: AgentState, *, persona: Persona) -> dict[str, object]:
    return _result(persona.personal_response())
