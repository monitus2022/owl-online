"""Persona card and lore pack, no network."""

import json
from pathlib import Path

import pytest

from app.agent.persona import META_TOPICS, PERSONA, load_persona
from app.knowledge import load_lore

FIXTURE = Path(__file__).resolve().parents[1] / "eval" / "fixtures" / "lore"
_TIME_WORDS = ("deadline", "tomorrow", "next week", "hurry", "countdown", "tonight")
_FORMAT_WORDS = (
    "paper",
    "practical",
    "outstanding",
    "troll",
    "written",
    "demonstration",
    "mark scheme",
)


def test_persona_card_has_every_meta_topic():
    assert PERSONA.name
    assert PERSONA.address == "Professor Crane"
    assert PERSONA.subject == "Defense Against the Dark Arts"
    for topic in META_TOPICS:
        assert PERSONA.meta_response(topic), topic


def test_answer_suffix_keeps_the_grounding_rules():
    suffix = PERSONA.answer_suffix()
    assert "Professor Crane" in suffix
    assert "Defense Against the Dark Arts" in suffix
    assert "citation and abstention rules" in suffix
    assert "Never invent" in suffix
    assert "exactly as it appears" in suffix
    assert "Ashcombe" not in suffix
    assert "lore" not in suffix.casefold()
    assert "Do not disclose the school examination format" in suffix


def test_exam_syllabus_and_grading_do_not_disclose_format():
    for topic in ("exam", "syllabus", "grading"):
        text = PERSONA.meta_response(topic).casefold()
        for word in _FORMAT_WORDS:
            assert word not in text, (topic, word)


def test_meta_and_personal_text_has_no_time_pressure():
    for topic in META_TOPICS:
        text = PERSONA.meta_response(topic).casefold()
        for word in _TIME_WORDS:
            assert word not in text, (topic, word)
    personal = PERSONA.personal_response().casefold()
    for word in _TIME_WORDS:
        assert word not in personal, word


def test_persona_card_missing_topic_fails(tmp_path):
    data = {
        "identity": {
            "name": "X",
            "address": "Professor X",
            "role": "teacher",
            "school": "school",
            "subject": "DADA",
        },
        "register": {"tone": "formal", "pacing": "none", "stance": "serious"},
        "boundaries": {"facts": "none", "advice": "none", "canon": "none", "exam": "none"},
        "meta": {"identity": "I am X."},
        "personal": {"response": "Hello."},
    }
    path = tmp_path / "persona.toml"
    path.write_text(
        "\n".join(
            [
                "[identity]",
                *(f'{key} = "{value}"' for key, value in data["identity"].items()),
                "[register]",
                *(f'{key} = "{value}"' for key, value in data["register"].items()),
                "[boundaries]",
                *(f'{key} = "{value}"' for key, value in data["boundaries"].items()),
                "[meta]",
                'identity = "I am X."',
                "[personal]",
                'response = "Hello."',
                "[abstain]",
                'response = "I cannot confirm that."',
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing meta topics"):
        load_persona(path)


def test_lore_fixture_loads_and_selects_the_professor():
    store = load_lore(FIXTURE)
    assert len(store.entries) == 11
    assert store.get("school-001") is not None
    assert store.get("crane-001") is not None
    assert store.select("who is Professor Crane", subject="dada")[0].id == "crane-001"
    assert store.select("What is the Auror pathway?", subject="dada")[0].id == "auror-001"
    founders = {"crane-001", "vale-001", "hale-001", "raman-001", "ashby-001"}
    assert founders <= store.ids()
    assert {"timeline-1998", "timeline-2008", "timeline-2026"} <= store.ids()


def test_lore_rejects_an_unknown_tier(tmp_path):
    path = tmp_path / "lore.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "bad-001",
                "subject": "dada",
                "tier": "fan",
                "title": "Bad",
                "body": "Bad.",
                "source": "test",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="tier"):
        load_lore(path)


def test_lore_rejects_a_duplicate_id(tmp_path):
    row = {
        "id": "dup-001",
        "subject": "dada",
        "tier": "product",
        "title": "Dup",
        "body": "Dup.",
        "source": "test",
    }
    path = tmp_path / "lore.jsonl"
    path.write_text(
        json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="duplicate id"):
        load_lore(path)


def test_lore_rejects_an_invalid_id(tmp_path):
    path = tmp_path / "lore.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "Bad ID",
                "subject": "dada",
                "tier": "product",
                "title": "Bad",
                "body": "Bad.",
                "source": "test",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="id must be"):
        load_lore(path)


def test_lore_rejects_an_empty_body(tmp_path):
    path = tmp_path / "lore.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "empty-001",
                "subject": "dada",
                "tier": "product",
                "title": "Empty",
                "body": "   ",
                "source": "test",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="empty body"):
        load_lore(path)


def _minimal_card(meta_identity: str = "I am X.", boundaries: dict | None = None) -> str:
    lines = [
        "[identity]",
        'name = "X"',
        'address = "Professor X"',
        'role = "teacher"',
        'school = "school"',
        'subject = "DADA"',
        "[register]",
        'tone = "formal"',
        'pacing = "no pace"',
        'stance = "serious"',
        "[boundaries]",
    ]
    for key, value in (boundaries or {
        "facts": "none",
        "advice": "none",
        "canon": "none",
        "exam": "none",
    }).items():
        lines.append(f'{key} = "{value}"')
    topics = (
        "identity",
        "scope",
        "exam",
        "syllabus",
        "grading",
        "school",
        "professor",
        "auror",
        "boundaries",
        "greeting",
    )
    lines.append("[meta]")
    for topic in topics:
        value = meta_identity if topic == "identity" else f"{topic}."
        lines.append(f'{topic} = "{value}"')
    lines.extend(
        [
            "[personal]",
            'response = "Hello."',
            "[abstain]",
            'response = "I cannot confirm that."',
        ]
    )
    return "\n".join(lines)


def test_persona_card_missing_boundary_fails(tmp_path):
    path = tmp_path / "persona.toml"
    path.write_text(
        _minimal_card(boundaries={"facts": "none", "canon": "none", "exam": "none"}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing boundaries"):
        load_persona(path)


def test_persona_card_empty_meta_value_fails(tmp_path):
    path = tmp_path / "persona.toml"
    path.write_text(_minimal_card(meta_identity=""), encoding="utf-8")
    with pytest.raises(ValueError, match="empty meta.identity"):
        load_persona(path)


def test_lore_rejects_markdown_without_front_matter(tmp_path):
    directory = tmp_path / "lore"
    directory.mkdir()
    (directory / "bad.md").write_text("# no front matter\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing TOML front matter"):
        load_lore(directory)


def test_lore_rejects_markdown_with_an_empty_body(tmp_path):
    directory = tmp_path / "lore"
    directory.mkdir()
    (directory / "empty.md").write_text(
        "+++\n"
        'id = "empty-001"\n'
        'subject = "dada"\n'
        'tier = "product"\n'
        'title = "Empty"\n'
        'source = "test"\n'
        "+++\n\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="empty body"):
        load_lore(directory)


def test_lore_rejects_unterminated_markdown_front_matter(tmp_path):
    directory = tmp_path / "lore"
    directory.mkdir()
    (directory / "bad.md").write_text("+++\nid = \"x-001\"\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unterminated TOML front matter"):
        load_lore(directory)


def test_lore_rejects_invalid_markdown_toml(tmp_path):
    directory = tmp_path / "lore"
    directory.mkdir()
    (directory / "bad.md").write_text(
        "+++\nid = \n+++\n\nBody.\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="invalid TOML front matter"):
        load_lore(directory)


def test_lore_rejects_a_front_matter_body_key(tmp_path):
    directory = tmp_path / "lore"
    directory.mkdir()
    (directory / "bad.md").write_text(
        "+++\n"
        'id = "x-001"\n'
        'subject = "dada"\n'
        'tier = "product"\n'
        'title = "X"\n'
        'source = "test"\n'
        'body = "front matter"\n'
        "+++\n\nBody.\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="must not set body"):
        load_lore(directory)
