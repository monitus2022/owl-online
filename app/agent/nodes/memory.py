"""Graph nodes for short-term conversation memory (#30)."""

from __future__ import annotations

from app.agent.memory import (
    TOKEN_BUDGET,
    WINDOW_MESSAGES,
    extract_entity,
    resolve_followup,
    trim_history,
)
from app.agent.state import AgentState


def resolve_node(
    state: AgentState,
    *,
    window: int = WINDOW_MESSAGES,
    token_budget: int = TOKEN_BUDGET,
) -> dict[str, object]:
    """Bound the context and turn a follow-up into a standalone query."""
    messages, summary = trim_history(
        list(state.get("messages", [])),
        state.get("summary", ""),
        window=window,
        token_budget=token_budget,
    )
    resolution = resolve_followup(
        state["question"],
        messages=messages,
        summary=summary,
        last_entity=state.get("last_entity"),
        last_person=state.get("last_person"),
        last_place=state.get("last_place"),
        last_mode=state.get("last_mode"),
        pending_clarify=bool(state.get("pending_clarify", False)),
        subject=state.get("subject") or "dada",
    )
    return {
        "messages": messages,
        "summary": summary,
        "standalone_question": resolution.standalone,
        "forced_mode": resolution.forced_mode,
        "preferred_mode": resolution.preferred_mode,
    }


def remember_node(
    state: AgentState,
    *,
    window: int = WINDOW_MESSAGES,
    token_budget: int = TOKEN_BUDGET,
) -> dict[str, object]:
    """Append the turn and keep the context under the configured budget."""
    question = state.get("question", "")
    answer = state.get("answer", "")
    mode = state.get("routed_mode") or state.get("mode", "answer")
    messages = list(state.get("messages", []))
    messages.append({"role": "user", "content": question})
    messages.append({"role": "assistant", "content": answer})
    messages, summary = trim_history(
        messages,
        state.get("summary", ""),
        window=window,
        token_budget=token_budget,
    )
    updates: dict[str, object] = {
        "messages": messages,
        "summary": summary,
        "last_mode": mode,
        "pending_clarify": mode == "clarify",
    }
    entity = extract_entity(state.get("standalone_question") or question)
    if entity is not None:
        updates["last_entity"] = entity.text
        if entity.kind == "person":
            updates["last_person"] = entity.text
        if entity.kind == "place":
            updates["last_place"] = entity.text
    return updates


__all__ = ["remember_node", "resolve_node"]
