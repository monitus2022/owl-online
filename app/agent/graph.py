"""Compiled LangGraph chat graph.

Router: answer | practice | feedback | meta | personal | lesson.
"""

from functools import partial

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.nodes.answer import answer_node
from app.agent.nodes.feedback import feedback_node
from app.agent.nodes.lesson import lesson_node
from app.agent.nodes.persona import meta_node, personal_node
from app.agent.nodes.practice import practice_node
from app.agent.persona import PERSONA, Persona
from app.agent.router import route
from app.agent.state import AgentState
from app.knowledge import LoreStore
from app.knowledge.lesson import DEFAULT_MIN_SCORE as LESSON_MIN_SCORE
from app.knowledge.lesson import DEFAULT_TOP_K as LESSON_TOP_K
from app.knowledge.lesson import LessonSelector
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
    persona: Persona | None = None,
    lore: LoreStore | None = None,
    lore_subject: str = "dada",
    small_llm: Llm | None = None,
    lesson: LessonSelector | None = None,
    lesson_subject: str = "dada",
    lesson_top_k: int = LESSON_TOP_K,
    lesson_min_score: float = LESSON_MIN_SCORE,
) -> CompiledStateGraph:
    """Build the stateless per-request graph; no checkpointer in D4."""
    graph = StateGraph(AgentState)
    graph.add_node("router", partial(route, persona=persona is not None))

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
            persona=persona,
            lore=lore,
            lore_subject=lore_subject,
        ),
    )
    graph.add_edge("answer", END)

    active_persona = persona or PERSONA
    graph.add_node("meta", partial(meta_node, persona=active_persona))
    graph.add_node("personal", partial(personal_node, persona=active_persona))
    graph.add_edge("meta", END)
    graph.add_edge("personal", END)

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
    routes = {
        "answer": "answer",
        "practice": "practice",
        "feedback": "feedback",
        "meta": "meta",
        "personal": "personal",
    }
    if lesson is not None:
        graph.add_node(
            "lesson",
            partial(
                lesson_node,
                selector=lesson,
                llm=llm,
                subject=lesson_subject,
                top_k=lesson_top_k,
                min_score=lesson_min_score,
                max_retries=max_retries,
                persona=persona,
            ),
        )
        graph.add_edge("lesson", END)
        routes["lesson"] = "lesson"
    else:
        # Lesson is an explicit request only; without a selector it falls back
        # to the corpus answer path rather than failing the request.
        routes["lesson"] = "answer"
    graph.add_conditional_edges(
        "router",
        lambda state: state["mode"],
        routes,
    )
    return graph.compile()
