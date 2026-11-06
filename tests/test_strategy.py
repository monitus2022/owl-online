"""Deterministic retrieval strategy cues, no network."""

from pathlib import Path

import pytest

from app.pipeline.retrieve.strategy import classify_retrieval_strategy
from eval.harness import load_aggregation

FIXTURE = (
    Path(__file__).resolve().parents[1] / "eval" / "fixtures" / "aggregation.jsonl"
)


@pytest.mark.parametrize(
    "question",
    [
        "Who teaches Defense Against the Dark Arts in each of the seven books?",
        "What role does Dobby play in each book he appears in?",
        "Which books mention Quidditch?",
        "In which books does the Order of the Phoenix appear?",
        "How does Sirius Black's role change across the books he appears in?",
        "Which Minister for Magic is prominent in every book?",
        "List all seven books in order.",
    ],
)
def test_coverage_cues_choose_multi_book(question):
    decision = classify_retrieval_strategy(question)
    assert decision.is_multi_book
    assert decision.reason.startswith(("coverage_cue:", "multiple_book_numbers:"))


@pytest.mark.parametrize(
    "question",
    [
        "What are the three Unforgivable Curses?",
        "What are the four Hogwarts houses?",
        "What are the three Deathly Hallows?",
        "What are the two schools that visit for the Triwizard Tournament?",
        "What are the four Triwizard champions?",
    ],
)
def test_plural_counts_without_coverage_cues_stay_single_hop(question):
    decision = classify_retrieval_strategy(question)
    assert decision.name == "single_hop"
    assert decision.reason.startswith("plural_count_without_coverage_cue:")


def test_explicit_multiple_book_numbers_win_first():
    decision = classify_retrieval_strategy("Compare book 2 and book 6.")
    assert decision.name == "multi_book"
    assert decision.reason == "multiple_book_numbers:2"
    assert decision.cues == ("2", "6")


def test_no_cue_stays_single_hop():
    decision = classify_retrieval_strategy("What is the name of the bank?")
    assert decision.name == "single_hop"
    assert decision.reason == "no_coverage_cue"


@pytest.mark.parametrize(
    "question",
    [
        "We walked across the lake.",
        "They looked at each other.",
        "Every day is different.",
        "Which book does the Chamber of Secrets appear in?",
        "In which book does the Chamber appear?",
        "How do Ron and Hermione care for each other?",
        "What does each of the three tasks involve?",
        "Every one of the Weasley children is red-haired.",
        "List all the spells Hermione uses in book 3.",
        "All seven Weasley children are red-haired.",
    ],
)
def test_ordinary_phrases_do_not_trigger_coverage(question):
    assert classify_retrieval_strategy(question).name == "single_hop"


@pytest.mark.parametrize(
    "question",
    [
        "Across all seven books, who teaches Defense Against the Dark Arts?",
        "List all seven books in order.",
        "For each book, who is headmaster?",
        "Per book, who is headmaster?",
        "Every one of the books has a title.",
    ],
)
def test_narrow_book_phrases_choose_multi_book(question):
    assert classify_retrieval_strategy(question).name == "multi_book"


def test_a_book_list_counts_every_number():
    decision = classify_retrieval_strategy("Compare books 2, 4 and 7.")
    assert decision.name == "multi_book"
    assert decision.reason == "multiple_book_numbers:3"
    assert decision.cues == ("2", "4", "7")


def test_fixture_precision_and_recall_are_perfect_for_the_measured_cues():
    items = load_aggregation(FIXTURE)
    true_positive = false_positive = false_negative = 0
    for item in items:
        predicted = classify_retrieval_strategy(item.question).is_multi_book
        actual = item.kind == "multi_book"
        true_positive += predicted and actual
        false_positive += predicted and not actual
        false_negative += not predicted and actual
    assert true_positive == 10
    assert false_positive == 0
    assert false_negative == 0
