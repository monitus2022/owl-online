"""Exam serving API tests: sampling, view, grading and limits (#193)."""

from __future__ import annotations

import json
import sqlite3

from fastapi.testclient import TestClient

from app.api.runtime import Runtime
from app.config import Settings
from app.exam.bank import ExamBank
from app.main import _parse_paper_id, create_app
from app.storage.exam_store import ExamStore
from eval.exam.fixtures import build_bank


class _Retriever:
    async def retrieve(self, query: str, top_k: int):
        return []


class _ChatLlm:
    async def generate(self, system: str, prompt: str, *, context=None) -> str:
        return ""

    def stream(self, system: str, prompt: str, *, context=None):
        async def gen():
            yield ""

        return gen()


class _Judge:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, system: str, prompt: str, *, context=None) -> str:
        self.calls += 1
        data = json.loads(prompt)
        results = {}
        for question in data["questions"]:
            evidence = question["evidence"][0]["chunk_id"]
            results[question["item_id"]] = {
                "criteria": [
                    {
                        "criterion_id": "correctness",
                        "awarded": 4,
                        "max_marks": 4,
                        "reason": "Correct.",
                    },
                    {
                        "criterion_id": "completeness",
                        "awarded": 4,
                        "max_marks": 4,
                        "reason": "Complete.",
                    },
                ],
                "total": 8,
                "feedback": "Complete.",
                "evidence_ids": [evidence],
            }
        return json.dumps({"results": results})

    async def aclose(self) -> None:
        return None

    def stream(self, system: str, prompt: str, *, context=None):
        async def gen():
            yield ""

        return gen()


def _bank_6_4() -> ExamBank:
    bank, _, _, _ = build_bank()
    mcq = bank.items[0]
    short = bank.items[1]
    mcqs = [
        mcq.model_copy(
            update={"item_id": f"dada-mcq-{index:03d}", "prompt": f"Sample MCQ {index}?"}
        )
        for index in range(1, 7)
    ]
    shorts = [
        short.model_copy(
            update={
                "item_id": f"dada-short-{index:03d}",
                "prompt": f"Sample short answer {index}?",
            }
        )
        for index in range(1, 5)
    ]
    manifest = bank.manifest.model_copy(
        update={"mcq_count": 6, "short_answer_count": 4}
    )
    return ExamBank(manifest=manifest, items=[*mcqs, *shorts])


def _setup(tmp_path) -> tuple[ExamStore, _Judge]:
    store = ExamStore(tmp_path / "exams.db")
    store.replace_bank(_bank_6_4())
    return store, _Judge()


def _client(
    store: ExamStore, judge: _Judge, settings: Settings | None = None
) -> TestClient:
    runtime = Runtime(
        retriever=_Retriever(),
        llm=_ChatLlm(),
        exam_store=store,
        exam_judge=judge,
    )
    app = create_app(
        settings or Settings(exam_attempts_per_day_anonymous=3),
        runtime=runtime,
    )
    return TestClient(app)


def _start(client: TestClient) -> tuple[dict, dict]:
    papers = client.get("/v1/exams").json()
    assert len(papers) == 1
    paper = papers[0]
    response = client.post(f"/v1/exams/{paper['paper_id']}/attempts")
    assert response.status_code == 201
    return paper, response.json()


def _answers(view: dict) -> list[dict]:
    answers = []
    for question in view["questions"]:
        if question["kind"] == "mcq":
            answers.append(
                {
                    "item_id": question["item_id"],
                    "option_id": question["options"][0]["option_id"],
                }
            )
        else:
            answers.append(
                {
                    "item_id": question["item_id"],
                    "answer_text": "A sample student answer.",
                }
            )
    return answers


def test_exams_lists_the_paper(tmp_path) -> None:
    store, judge = _setup(tmp_path)
    with _client(store, judge) as client:
        papers = client.get("/v1/exams").json()
    assert len(papers) == 1
    paper = papers[0]
    assert paper["paper_id"] == "dada-1.0.0"
    assert paper["subject"] == "dada"
    assert paper["question_count"] == 10
    assert paper["mcq_count"] == 6
    assert paper["short_answer_count"] == 4
    assert paper["marks"] == 50
    assert paper["duration_minutes"] == 60
    assert paper["title"]


def test_attempt_view_hides_answers_and_is_stable(tmp_path) -> None:
    store, judge = _setup(tmp_path)
    with _client(store, judge) as client:
        paper, view = _start(client)
        assert paper["paper_id"] == view["paper_id"]
        assert view["marks"] == 50
        assert len(view["questions"]) == 10
        mcqs = [question for question in view["questions"] if question["kind"] == "mcq"]
        shorts = [
            question for question in view["questions"] if question["kind"] == "short_answer"
        ]
        assert len(mcqs) == 6
        assert len(shorts) == 4
        for question in mcqs:
            assert len(question["options"]) == 4
            assert len({option["option_id"] for option in question["options"]}) == 4
            assert "correct_option_id" not in question
        text = json.dumps(view)
        assert "correct_option_id" not in text
        assert "model_answer" not in text
        assert "rubric" not in text
        assert "evidence" not in text
        again = client.get(f"/v1/attempts/{view['attempt_id']}")
        assert again.status_code == 200
        assert again.json() == view


def test_grade_scores_and_is_idempotent(tmp_path) -> None:
    store, judge = _setup(tmp_path)
    with _client(store, judge) as client:
        _, view = _start(client)
        response = client.post(
            f"/v1/attempts/{view['attempt_id']}/grade",
            json={"answers": _answers(view)},
        )
        assert response.status_code == 200
        grade = response.json()
        assert grade["attempt_id"] == view["attempt_id"]
        assert grade["max_marks"] == 50
        assert grade["needs_review"] is False
        assert grade["band"] in {"O", "E", "A", "P", "D", "T"}
        assert len(grade["questions"]) == 10
        short_grades = [
            question
            for question in grade["questions"]
            if question["kind"] == "short_answer"
        ]
        assert len(short_grades) == 4
        assert all(question["marks_awarded"] == 8 for question in short_grades)
        assert all(question["model_answer"] for question in short_grades)
        assert judge.calls == 1
        again = client.post(
            f"/v1/attempts/{view['attempt_id']}/grade",
            json={"answers": _answers(view)},
        )
        assert again.status_code == 200
        assert again.json() == grade
        assert judge.calls == 1
        still = client.get(f"/v1/attempts/{view['attempt_id']}").json()
        assert "correct_option_id" not in json.dumps(still)


def test_attempt_limit_returns_429(tmp_path) -> None:
    store, judge = _setup(tmp_path)
    with _client(store, judge) as client:
        paper, _ = _start(client)
        for _ in range(2):
            response = client.post(f"/v1/exams/{paper['paper_id']}/attempts")
            assert response.status_code == 201
        limited = client.post(f"/v1/exams/{paper['paper_id']}/attempts")
        assert limited.status_code == 429
        assert limited.headers["Retry-After"]


def test_grade_rejects_an_unserved_option(tmp_path) -> None:
    store, judge = _setup(tmp_path)
    with _client(store, judge) as client:
        _, view = _start(client)
        mcq = next(
            question for question in view["questions"] if question["kind"] == "mcq"
        )
        response = client.post(
            f"/v1/attempts/{view['attempt_id']}/grade",
            json={"answers": [{"item_id": mcq["item_id"], "option_id": "z"}]},
        )
        assert response.status_code == 400


def test_grade_rejects_a_wrong_answer_shape(tmp_path) -> None:
    store, judge = _setup(tmp_path)
    with _client(store, judge) as client:
        _, view = _start(client)
        mcq = next(
            question for question in view["questions"] if question["kind"] == "mcq"
        )
        short = next(
            question
            for question in view["questions"]
            if question["kind"] == "short_answer"
        )
        mcq_text = client.post(
            f"/v1/attempts/{view['attempt_id']}/grade",
            json={
                "answers": [
                    {"item_id": mcq["item_id"], "answer_text": "Riddikulus"}
                ]
            },
        )
        assert mcq_text.status_code == 400
        short_option = client.post(
            f"/v1/attempts/{view['attempt_id']}/grade",
            json={
                "answers": [
                    {
                        "item_id": short["item_id"],
                        "option_id": short["item_id"],
                    }
                ]
            },
        )
        assert short_option.status_code == 400


def test_unknown_paper_and_attempt_are_404(tmp_path) -> None:
    store, judge = _setup(tmp_path)
    with _client(store, judge) as client:
        assert client.post("/v1/exams/nope/attempts").status_code == 404
        assert client.get("/v1/attempts/nope").status_code == 404


def test_no_exam_store_returns_empty_and_503() -> None:
    runtime = Runtime(retriever=_Retriever(), llm=_ChatLlm())
    app = create_app(Settings(), runtime=runtime)
    with TestClient(app) as client:
        assert client.get("/v1/exams").json() == []
        assert client.post("/v1/exams/dada-1.0.0/attempts").status_code == 503
        assert client.get("/v1/attempts/nope").status_code == 503


def test_paper_id_parses_hyphenated_subjects_and_versions() -> None:
    assert _parse_paper_id("dada-1.0.0") == ("dada", "1.0.0")
    assert _parse_paper_id("care-of-magical-creatures-1.0.0") == (
        "care-of-magical-creatures",
        "1.0.0",
    )
    assert _parse_paper_id("dada-1.0.0-rc1") == ("dada", "1.0.0-rc1")


def test_grade_persists_submitted_answers(tmp_path) -> None:
    store, judge = _setup(tmp_path)
    with _client(store, judge) as client:
        _, view = _start(client)
        answers = _answers(view)
        response = client.post(
            f"/v1/attempts/{view['attempt_id']}/grade",
            json={"answers": answers},
        )
        assert response.status_code == 200
        with sqlite3.connect(store.path) as conn:
            row = conn.execute(
                "SELECT answers_json FROM attempts WHERE attempt_id = ?",
                (view["attempt_id"],),
            ).fetchone()
        assert row is not None
        saved = json.loads(row[0])
        assert {answer["item_id"] for answer in saved} == {
            question["item_id"] for question in view["questions"]
        }


def test_attempt_ip_limit_returns_429(tmp_path) -> None:
    store, judge = _setup(tmp_path)
    settings = Settings(
        exam_attempts_per_day_anonymous=3,
        exam_attempts_per_day_ip=2,
    )
    with _client(store, judge, settings) as client:
        paper, _ = _start(client)
        assert (
            client.post(f"/v1/exams/{paper['paper_id']}/attempts").status_code
            == 201
        )
        limited = client.post(f"/v1/exams/{paper['paper_id']}/attempts")
        assert limited.status_code == 429
        assert limited.headers["Retry-After"]
