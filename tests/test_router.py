"""Router fixture: the chat intents classify correctly and overrides win."""

import pytest

from app.agent.router import classify, meta_topic, route


@pytest.mark.parametrize(
    ("question", "student_answer", "expected"),
    [
        ("What is the name of the three-headed dog?", None, "answer"),
        ("Who is the Head of Gryffindor House?", None, "answer"),
        ("What is the score of the Quidditch match?", None, "answer"),
        ("What score did the student get?", None, "answer"),
        ("Mark the date of the battle", None, "answer"),
        ("Grade boundaries for O.W.L.s?", None, "answer"),
        ("Give me the score of the match", None, "answer"),
        ("I need a grade for Potions", None, "answer"),
        ("Explain the rules of Quidditch", None, "answer"),
        ("What questions did Harry ask?", None, "answer"),
        ("Generate five exam questions on Horcruxes", None, "practice"),
        ("Write a quiz about the Triwizard Tournament", None, "practice"),
        ("Create a revision worksheet on potions", None, "practice"),
        ("Design a mock test for chapter four", None, "practice"),
        ("Give me a practice question on the Unforgivable Curses", None, "practice"),
        ("Ask me a question about the Marauder's Map", None, "practice"),
        ("Quiz me on Horcruxes", None, "practice"),
        ("Test my knowledge of defensive spells", None, "practice"),
        ("Grade this answer: Harry used Expelliarmus.", None, "feedback"),
        ("Mark the student's response out of ten", None, "feedback"),
        ("Score this answer out of 10", None, "feedback"),
        ("Assess the essay", None, "feedback"),
        ("Give me feedback on my answer", None, "feedback"),
        ("I need an assessment of this answer", None, "feedback"),
        ("I need a grade for this answer", None, "feedback"),
        ("Can you grade this answer?", None, "feedback"),
        ("Any question", "Harry used Expelliarmus.", "feedback"),
    ],
)
def test_router_fixture(question, student_answer, expected):
    assert classify(question, student_answer=student_answer) == expected


def test_explicit_mode_wins():
    assert classify("What is a Horcrux?", requested_mode="practice") == "practice"
    assert classify("Generate a quiz", requested_mode="answer") == "answer"


def test_lesson_is_an_answer_path_hint():
    assert classify("What is a Boggart?", requested_mode="lesson") == "lesson"
    assert (
        classify("Who are you?", requested_mode="lesson", persona=True) == "meta"
    )
    assert (
        classify("Give me a practice question", requested_mode="lesson")
        == "practice"
    )
    assert (
        classify(
            "Grade this answer: Harry used Expelliarmus.",
            requested_mode="lesson",
        )
        == "feedback"
    )
    assert (
        classify("How are you feeling today?", requested_mode="lesson", persona=True)
        == "lesson"
    )
    assert (
        classify(
            "I feel stressed about the exam.",
            requested_mode="lesson",
            persona=True,
        )
        == "personal"
    )
    assert classify("Who are you?", requested_mode="lesson", persona=False) == "lesson"


def test_route_returns_a_state_update():
    state = {"question": "Who is the Head of Gryffindor House?"}
    assert route(state) == {"mode": "answer"}


@pytest.mark.parametrize(
    "question",
    [
        "Who is Professor Alistair Crane?",
        "Who is Professor Crane?",
        "Who is Alistair Crane?",
        "Who is Profesor Alister Crane?",
        "Who is Proffesor Alistair Crain?",
        "Who's Crane?",
    ],
)
def test_professor_name_variants_route_to_identity(question):
    assert classify(question, persona=True) == "meta"
    assert meta_topic(question) == "identity"


@pytest.mark.parametrize(
    "question",
    [
        "Tell me about Professor Crane",
        "Tell me about Prof. Crain",
        "What is Professor Crane's background?",
        "Professor Crane's story",
    ],
)
def test_professor_background_variants_route_to_professor(question):
    assert classify(question, persona=True) == "meta"
    assert meta_topic(question) == "professor"


def test_book_professors_and_persona_off_stay_on_the_answer_path():
    assert classify("Who is Professor Snape?", persona=True) == "answer"
    assert classify("Who is Professor Crane?", persona=False) == "answer"


def test_possessive_professor_questions_stay_on_the_answer_path():
    assert classify("Tell me about Professor Crane's assistant", persona=True) == "answer"
    assert classify("Who is Professor Crane's assistant?", persona=True) == "answer"
    assert classify("Tell me about cranes", persona=True) == "answer"
    assert classify("Tell me about cran", persona=True) == "answer"
    assert classify("Who is Professor Crane-Smith?", persona=True) == "answer"
    assert classify("Tell me about Professor Crane-Smith", persona=True) == "answer"


@pytest.mark.parametrize(
    "question",
    [
        "Tell me about Professor Snape's background",
        "Who is Professor McGonagall?",
        "Who is Professor Lupin?",
        "Who teaches Defense Against the Dark Arts?",
    ],
)
def test_book_questions_stay_on_the_answer_path(question):
    assert classify(question, persona=True) == "answer"


def test_book_context_does_not_override_persona_identity():
    # The books do not contain Crane; a setting question about him stays meta.
    assert classify("In the books, who is Professor Crane?", persona=True) == "meta"
    assert meta_topic("In the books, who is Professor Crane?") == "identity"


def test_professor_background_needs_persona():
    assert classify("Tell me about Professor Crane", persona=False) == "answer"


def test_persona_card_name_drives_the_identity_cue():
    from app.agent.persona import PERSONA

    assert classify(f"Who is {PERSONA.name}?", persona=True) == "meta"
    assert meta_topic(f"Who is {PERSONA.name}?") == "identity"
    assert classify(f"Tell me about {PERSONA.name}", persona=True) == "meta"
    assert meta_topic(f"Tell me about {PERSONA.name}") == "professor"
    assert classify(f"Who is {PERSONA.address}?", persona=True) == "meta"


@pytest.mark.parametrize(
    "question",
    [
        "What is DADA?",
        "What's DADA?",
        "What is Defence Against the Dark Arts?",
        "What is Defense Against the Dark Arts?",
        "What does DADA mean?",
        "What does DADA stand for?",
        "What does Defence Against the Dark Arts mean?",
        "What is DADA short for?",
        "What's DADA short for?",
        "What is the meaning of DADA?",
        "Define DADA",
        "Explain the Defence Against the Dark Arts",
        "What is the DADA subject?",
        "What is this subject?",
        "What is your subject?",
        "Tell me about DADA",
        "Tell me about Defence Against the Dark Arts",
    ],
)
def test_subject_definition_routes_to_meta(question):
    assert classify(question, persona=True) == "meta"
    assert meta_topic(question) == "subject"


def test_subject_definition_with_book_context_stays_answer():
    assert classify("What is DADA at Hogwarts?", persona=True) == "answer"


def test_subject_definition_needs_persona():
    assert classify("What is DADA?", persona=False) == "answer"


def test_scope_question_still_routes_to_scope():
    assert classify("What subjects do you teach?", persona=True) == "meta"
    assert meta_topic("What subjects do you teach?") == "scope"


def test_subject_curriculum_routes_to_lore():
    assert classify("What is the DADA curriculum?", persona=True) == "fact"


def test_subject_department_routes_to_lore():
    assert classify("What is the DADA department?", persona=True) == "fact"


def test_subject_possessive_forms_do_not_steal_other_topics():
    assert (
        classify("What is DADA's role in the Order of the Phoenix?", persona=True)
        == "answer"
    )
    assert (
        classify("What is DADA in the Department of Mysteries?", persona=True)
        == "answer"
    )
    assert classify("What is DADA's syllabus?", persona=True) == "policy"
    assert meta_topic("What is DADA's syllabus?") == "syllabus"
    assert classify("What is DADA's exam?", persona=True) == "policy"
    assert meta_topic("What is DADA's exam?") == "exam"
    assert classify("What is DADA's grading scale?", persona=True) == "policy"
    assert meta_topic("What is DADA's grading scale?") == "grading"
    assert classify("What is DADA's exam at Hogwarts?", persona=True) == "policy"
    assert classify("What is on the O.W.L. exam?", persona=True) == "policy"


def test_exam_room_questions_stay_on_the_answer_path():
    assert classify("What is the exam room?", persona=True) == "answer"
    assert (
        classify(
            "What is the exam room in the Department of Mysteries?",
            persona=True,
        )
        == "answer"
    )


def test_contract_gates_route_closed_facts_and_clarify():
    assert (
        classify(
            "where did you study when you are young",
            requested_mode="lesson",
            persona=True,
        )
        == "fact"
    )
    assert (
        classify(
            "Did you go to the exam?",
            requested_mode="lesson",
            persona=True,
        )
        == "policy"
    )
    assert (
        classify(
            "Where did you train as an Auror?",
            requested_mode="lesson",
            persona=True,
        )
        == "meta"
    )
    assert (
        classify(
            "what is included in DADA?", requested_mode="lesson", persona=True
        )
        == "clarify"
    )
    assert (
        classify("what does DADA cover?", requested_mode="lesson", persona=True)
        == "fact"
    )
    assert (
        classify("where is Ashcombe?", requested_mode="lesson", persona=True)
        == "fact"
    )
    assert (
        classify(
            "who is professor raman?",
            requested_mode="lesson",
            persona=True,
            subject="charms",
        )
        == "meta"
    )
    assert (
        classify(
            "what is charms?",
            requested_mode="lesson",
            persona=True,
            subject="charms",
        )
        == "meta"
    )
    assert (
        classify(
            "what does charms cover?",
            requested_mode="lesson",
            persona=True,
            subject="charms",
        )
        == "meta"
    )
    assert (
        classify("what is a boggart?", requested_mode="lesson", persona=True)
        == "lesson"
    )
    assert (
        classify(
            "who are you?",
            requested_mode="lesson",
            persona=False,
        )
        == "lesson"
    )


def test_route_sets_the_fact_ids_for_a_lore_fact():
    update = route(
        {
            "question": "Where is Ashcombe?",
            "requested_mode": "lesson",
            "subject": "dada",
            "persona_enabled": True,
        },
        persona=True,
    )
    assert update["mode"] == "fact"
    assert update["fact_ids"] == ["lore:school-001"]


def test_contract_gate_has_no_policy_leaks_or_authority_bleed():
    from pathlib import Path

    from app.agent.router import contract_decision
    from eval.routing.fixtures import load_routing_items

    items = load_routing_items(
        Path(__file__).resolve().parents[1]
        / "eval"
        / "routing"
        / "fixtures"
        / "contracts.jsonl"
    )
    terms = {"boggart", "dementor", "expelliarmus", "patronus", "curse"}
    for item in items:
        decision = contract_decision(
            item.utterance,
            subject="dada",
            requested_mode="lesson",
            teaching_terms=terms,
        )
        actual = decision.contract
        if item.contract == "policy":
            assert actual == "policy", item.item_id
        if item.contract in {"persona", "lore"}:
            assert actual not in {"lesson", "answer"}, item.item_id
            if item.fact_present:
                assert actual != "abstain", item.item_id
            if item.fact_ids:
                assert set(decision.fact_ids) & set(item.fact_ids), item.item_id
        if item.contract == "lesson":
            assert actual not in {"persona", "lore", "fact"}, item.item_id
        if item.contract == "abstain" and item.item_id != "abs-019":
            assert actual == "abstain", item.item_id


def test_explicit_and_auto_intents_beat_the_teaching_abstain():
    terms = {"boggart"}
    assert (
        classify(
            "I feel sad.",
            requested_mode="lesson",
            persona=True,
            teaching_terms=terms,
        )
        == "personal"
    )
    assert (
        classify(
            "Assess the essay",
            requested_mode="lesson",
            persona=True,
            teaching_terms=terms,
        )
        == "feedback"
    )
    assert (
        classify(
            "Generate five exam questions on Horcruxes",
            requested_mode="lesson",
            persona=True,
            teaching_terms=terms,
        )
        == "practice"
    )
    assert (
        classify(
            "What do you cover?",
            requested_mode="lesson",
            persona=True,
            teaching_terms=terms,
        )
        == "meta"
    )


def test_policy_does_not_steal_explicit_practice_or_feedback():
    assert classify("Ask me an exam question", persona=True) == "practice"
    assert classify("Grade my exam answer", persona=True) == "feedback"
    assert classify("Assess my exam essay", persona=True) == "feedback"
    assert classify("Can you mark my exam before I sit it?", persona=True) == "policy"


def test_auto_mode_is_subject_aware():
    assert (
        classify(
            "Who is Professor Crane?",
            persona=True,
            subject="charms",
        )
        == "answer"
    )
    assert (
        classify("What is DADA?", persona=True, subject="charms") == "answer"
    )
    assert (
        classify("Tell me about Professor Crane", subject="charms") == "answer"
    )
    assert (
        classify("Who is Professor Raman?", persona=True, subject="charms")
        == "meta"
    )


def test_unclassified_lesson_request_abstains():
    assert (
        classify(
            "What is the capital of France?",
            requested_mode="lesson",
            persona=True,
            teaching_terms={"boggart"},
        )
        == "abstain"
    )
    assert (
        classify(
            "What is a boggart?",
            requested_mode="lesson",
            persona=True,
            teaching_terms={"boggart"},
        )
        == "lesson"
    )


def test_exam_room_and_book_medical_asks_stay_on_the_book_path():
    terms = {"boggart"}
    assert (
        classify(
            "What is the exam room?",
            requested_mode="lesson",
            persona=True,
            teaching_terms=terms,
        )
        == "lesson"
    )
    assert (
        classify(
            "What medical advice did Madam Pomfrey give?",
            requested_mode="lesson",
            persona=True,
            teaching_terms=terms,
        )
        == "lesson"
    )


@pytest.mark.parametrize(
    "question",
    [
        "did you study in hogwarts?",
        "did you attend hogwarts?",
        "were you a student at hogwarts?",
        "have you studied at hogwarts?",
    ],
)
def test_education_paraphrases_route_to_the_persona_fact(question):
    update = route(
        {
            "question": question,
            "requested_mode": "lesson",
            "subject": "dada",
            "persona_enabled": True,
        },
        persona=True,
    )
    assert update["mode"] == "fact"
    assert update["fact_ids"] == ["persona:professor.education"]


@pytest.mark.parametrize(
    "question",
    [
        "Did you attend the school exam?",
        "Did you study at school for the exam?",
        "Did you study for the exam?",
    ],
)
def test_education_cues_do_not_steal_exam_questions(question):
    from app.agent.router import contract_decision

    decision = contract_decision(question, subject="dada", requested_mode="lesson")
    assert decision.contract == "policy"
    assert "persona:professor.education" not in decision.fact_ids
    assert classify(question, requested_mode="lesson", persona=True) == "policy"


@pytest.mark.parametrize(
    "question",
    [
        "For the exam, did you study at school?",
        "Did you study at school for the examination?",
        "Did you attend the school exams?",
        "Did you study at school for the O.W.L.s?",
    ],
)
def test_education_cues_do_not_steal_exam_synonyms(question):
    from app.agent.router import contract_decision

    decision = contract_decision(question, subject="dada", requested_mode="lesson")
    assert decision.contract == "policy"
    assert "persona:professor.education" not in decision.fact_ids


def test_meta_question_about_the_exam_is_policy_not_practice():
    from app.agent.router import contract_decision

    assert (
        classify(
            "Can I ask a question about exam?",
            requested_mode="lesson",
            persona=True,
        )
        == "policy"
    )
    decision = contract_decision(
        "Can I ask a question about exam?", subject="dada", requested_mode="lesson"
    )
    assert decision.contract == "policy"
    assert (
        classify(
            "Can I ask a question about the Marauder's Map?",
            requested_mode="lesson",
            persona=True,
        )
        in {"lesson", "answer"}
    )
    assert (
        classify(
            "Ask me a question about the Marauder's Map",
            requested_mode="lesson",
            persona=True,
        )
        == "practice"
    )
    for question in (
        "Can I ask a question about exams?",
        "Can I ask about tests?",
        "Can I ask about assessments?",
        "Can I ask about papers?",
        "Ask me about the exam",
        "Tell me about the exam",
        "Ask me about examinations",
        "Ask me about tests",
        "Ask me about assessments",
        "Ask me about papers",
    ):
        assert (
            classify(question, requested_mode="lesson", persona=True) == "policy"
        ), question


def test_practice_exam_variants_stay_practice_but_the_format_is_policy():
    for question in (
        "Give me a practice test",
        "Give me a practice exam",
        "Give me a practice paper",
        "Give me a practice exam questions",
    ):
        assert classify(question, requested_mode="lesson", persona=True) == "practice", question
    assert (
        classify(
            "Give me a practice exam format",
            requested_mode="lesson",
            persona=True,
        )
        == "policy"
    )
