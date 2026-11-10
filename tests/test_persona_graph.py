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


class _WeakRetriever:
    async def retrieve(self, query: str, top_k: int) -> list[Chunk]:
        return []


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
    assert state["answer"] in PERSONA.meta_variants("identity")
    assert state["abstained"] is False


async def test_a_repeated_meta_question_can_return_a_different_phrasing(monkeypatch):
    from app.agent import persona as persona_module

    variants = PERSONA.meta_variants("identity")
    assert len(variants) > 1
    picks = iter([variants[0], variants[1]])
    monkeypatch.setattr(
        persona_module.Persona,
        "_pick",
        staticmethod(lambda variants, choice: next(picks)),
    )
    graph = build_graph(_Retriever(), _Llm(), persona=PERSONA)
    request = {
        "question": "Who are you?",
        "requested_mode": "auto",
        "student_answer": None,
        "top_k": 5,
    }
    first = await graph.ainvoke(request)
    second = await graph.ainvoke(request)
    assert first["answer"] == variants[0]
    assert second["answer"] == variants[1]
    assert first["abstained"] is False
    assert second["abstained"] is False


async def test_a_repeated_unanswerable_question_can_vary_the_refusal(monkeypatch):
    from app.agent import persona as persona_module

    variants = PERSONA.abstain_variants()
    assert len(variants) > 1
    picks = iter([variants[0], variants[1]])
    monkeypatch.setattr(
        persona_module.Persona,
        "_pick",
        staticmethod(lambda variants, choice: next(picks)),
    )
    graph = build_graph(_WeakRetriever(), _Llm(), persona=PERSONA)
    request = {
        "question": "Who trims the wick?",
        "requested_mode": "auto",
        "student_answer": None,
        "top_k": 5,
    }
    first = await graph.ainvoke(request)
    second = await graph.ainvoke(request)
    assert first["answer"] == variants[0]
    assert second["answer"] == variants[1]
    assert first["abstained"] is True
    assert second["abstained"] is True


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
    assert state["answer"] in PERSONA.personal_variants()


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
    assert classify("Who founded Hogwarts?", persona=True) == "answer"
    assert classify("What did the founders value?", persona=True) == "answer"
    assert (
        classify("What was the DADA curriculum under Lupin?", persona=True)
        == "answer"
    )
    assert (
        classify("What is the DADA curriculum at Hogwarts?", persona=True)
        == "answer"
    )
    assert (
        classify("What is the DADA curriculum in the books?", persona=True)
        == "answer"
    )
    assert (
        classify("What was the DADA curriculum under Crouch?", persona=True)
        == "answer"
    )
    assert (
        classify("What is the DADA curriculum in the fourth year?", persona=True)
        == "answer"
    )


def test_meta_topics_cover_greeting_syllabus_and_grading():
    from app.agent.router import classify

    assert classify("Hello", persona=True) == "meta"
    assert classify("Good morning.", persona=True) == "meta"
    assert classify("What is the syllabus?", persona=True) == "policy"
    assert classify("What is the DADA curriculum?", persona=True) == "fact"
    assert classify("How is the exam graded?", persona=True) == "policy"


def test_a_greeting_prefix_does_not_steal_a_question():
    from app.agent.router import classify

    assert classify("Hello, what is a Horcrux?", persona=True) == "answer"
    assert classify("Hi, I'm worried", persona=True) == "personal"


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


async def test_persona_abstention_uses_the_in_world_line():
    graph = build_graph(_WeakRetriever(), _Llm(), persona=PERSONA)
    state = await graph.ainvoke(
        {
            "question": "Who trims the wick?",
            "requested_mode": "auto",
            "student_answer": None,
            "top_k": 5,
        }
    )
    assert state["abstained"] is True
    assert state["answer"] in PERSONA.abstain_variants()
    assert state["citations"] == []
    assert state["abstain_reason"] == "no_evidence"


def test_grading_cue_is_reachable():
    from app.agent.router import meta_topic

    assert meta_topic("How is the exam graded?") == "grading"
    assert meta_topic("What is the exam format?") == "exam"
