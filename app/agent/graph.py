"""Compiled LangGraph chat graph: router -> answer | practice | feedback."""

from functools import partial

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.nodes.answer import answer_node
from app.agent.nodes.feedback import feedback_node
from app.agent.nodes.practice import practice_node
from app.agent.router import route
from app.agent.state import AgentState
from app.pipeline.generate import DEFAULT_MAX_RETRIES, DEFAULT_TOP_K
from app.providers.contracts import Llm, Retriever


def build_graph(
    retriever: Retriever,
    llm: Llm,
    *,
    top_k: int = DEFAULT_TOP_K,
    min_score: float | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    multi_book: bool = False,
    small_llm: Llm | None = None,
) -> CompiledStateGraph:
    """Build the stateless per-request graph; no checkpointer in D4."""
    graph = StateGraph(AgentState)
    graph.add_node("router", route)

    # Only the answer path verifies and retries; practice and feedback stay
    # single-pass and ephemeral.
    graph.add_node(
        "answer",
        partial(
            answer_node,
            retriever=retriever,
            llm=llm,
            top_k=top_k,
            min_score=min_score,
            max_retries=max_retries,
            multi_book=multi_book,
        ),
    )
    graph.add_edge("answer", END)

    for name, node in (
        ("practice", practice_node),
        ("feedback", feedback_node),
    ):
        graph.add_node(
            name,
            partial(
                node,
                retriever=retriever,
                llm=small_llm or llm,
                fallback_llm=llm if small_llm is not None else None,
                top_k=top_k,
                min_score=min_score,
            ),
        )
        graph.add_edge(name, END)

    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        lambda state: state["mode"],
        {"answer": "answer", "practice": "practice", "feedback": "feedback"},
    )
    return graph.compile()
