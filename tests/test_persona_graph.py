"""Persona routing and the persona suffix on the answer path, no network."""

import re

from app.agent import build_graph
from app.agent.persona import PERSONA
from app.pipeline.generate import ask
from app.schemas import Chunk, ChunkMetadata


def _chunk() -> Chunk:
    return Chunk(
        id="b1-c01-0000",
        text="Rowan trims the wick.",
        metadata=ChunkMetadata(
            book_num=1, chapter_num=1, book_name="Book 1", chapter_name="Chapter 1"
        ),
        score=1.0,
    )


class _Retriever:
    async def retrieve(self, query: str, top_k: int) -> list[Chunk]:
        return [_chunk()]


class _Llm:
    name = "fake/persona"

    def __init__(self, text: str = "Rowan trims the wick [b1-c01-0000].") -> None:
        self.text = text
        self.systems: list[str] = []

    async def generate(self, system: str, prompt: str, *, context=None) -> str:
        self.systems.append(system)
        return self.text

    def stream(self, system: str, prompt: str, *, context=None):
        self.systems.append(system)

        async def gen():
            for piece in re.findall(r"\S+\s*", self.text):
                yield piece

        return gen()


async def test_meta_question_routes_to_the_scripted_answer():
    graph = build_graph(_Retriever(), _Llm(), persona=PERSONA)
    state = await graph.ainvoke(
        {
            "question": "Who are you?",
            "requested_mode": "auto",
            "student_answer": None,
            "top_k": 5,
        }
    )
    assert state["mode"] == "meta"
    assert state["answer"] == PERSONA.meta_response("identity")
    assert state["abstained"] is False


async def test_personal_question_routes_to_the_scripted_reply():
    graph = build_graph(_Retriever(), _Llm(), persona=PERSONA)
    state = await graph.ainvoke(
        {
            "question": "I am worried about the exam.",
            "requested_mode": "auto",
            "student_answer": None,
            "top_k": 5,
        }
    )
    assert state["mode"] == "personal"
    assert state["answer"] == PERSONA.personal_response()


async def test_persona_off_keeps_the_answer_route():
    graph = build_graph(_Retriever(), _Llm(), persona=None)
    state = await graph.ainvoke(
        {
            "question": "Who are you?",
            "requested_mode": "auto",
            "student_answer": None,
            "top_k": 5,
        }
    )
    assert state["mode"] == "answer"
    assert state["citations"] == ["b1-c01-0000"]


async def test_answer_suffix_is_appended_to_the_grounded_prompt():
    llm = _Llm()
    result = await ask(
        "Who trims the wick?",
        retriever=_Retriever(),
        llm=llm,
        persona_suffix=PERSONA.answer_suffix(),
    )
    assert not result.abstained
    assert "Professor Crane" in llm.systems[0]
    assert "Cite the id" in llm.systems[0]


async def test_no_persona_suffix_keeps_the_plain_prompt():
    llm = _Llm()
    await ask("Who trims the wick?", retriever=_Retriever(), llm=llm)
    assert "Professor Crane" not in llm.systems[0]


def test_book_questions_do_not_steal_the_meta_route():
    from app.agent.router import classify

    assert classify("What school did Harry attend?", persona=True) == "answer"
    assert classify("How did Tonks become an Auror?", persona=True) == "answer"


def test_meta_topics_cover_greeting_syllabus_and_grading():
    from app.agent.router import classify

    assert classify("Hello", persona=True) == "meta"
    assert classify("What is the syllabus?", persona=True) == "meta"
    assert classify("How is the exam graded?", persona=True) == "meta"


async def test_an_uncited_draft_still_abstains_with_the_persona_suffix():
    class _UncitedLlm(_Llm):
        async def generate(self, system: str, prompt: str, *, context=None) -> str:
            return "A confident answer with no citation."

    result = await ask(
        "Who trims the wick?",
        retriever=_Retriever(),
        llm=_UncitedLlm(),
        persona_suffix=PERSONA.answer_suffix(),
    )
    assert result.abstained
    assert result.abstain_reason == "uncited"
