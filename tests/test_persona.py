"""Persona card and lore pack, no network."""

import json
import re
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
        variants = PERSONA.meta_variants(topic)
        assert variants, topic
        for text in variants:
            assert text.strip(), (topic, text)
    for text in PERSONA.personal_variants():
        assert text.strip()
    for text in PERSONA.abstain_variants():
        assert text.strip()


def test_every_meta_topic_has_a_variant_bank():
    for topic in META_TOPICS:
        assert len(PERSONA.meta_variants(topic)) > 1, topic
    assert len(PERSONA.personal_variants()) > 1
    assert len(PERSONA.abstain_variants()) > 1


def test_choices_are_reproducible():
    for topic in META_TOPICS:
        variants = PERSONA.meta_variants(topic)
        for index in range(len(variants)):
            assert PERSONA.meta_response(topic, choice=index) == variants[index]
        assert PERSONA.meta_response(topic, choice=0) == variants[0]
    assert PERSONA.personal_response(choice=0) == PERSONA.personal_variants()[0]
    assert PERSONA.abstain_response(choice=0) == PERSONA.abstain_variants()[0]


_FACTS = {
    "identity": ("Professor Crane", "Defense Against the Dark Arts", "Ashcombe"),
    "scope": ("Defense Against the Dark Arts", "four"),
    "exam": ("examination",),
    "syllabus": ("syllabus",),
    "grading": ("examination",),
    "school": ("Ashcombe", "2008", "Cotswolds", "five"),
    "professor": ("Auror", "ten years", "Ashcombe"),
    "auror": (
        "Exceeds Expectations",
        "Defense Against the Dark Arts",
        "Transfiguration",
        "Charms",
        "Potions",
        "Herbology",
        "temporary",
    ),
    "boundaries": ("Defense Against the Dark Arts", "examination format"),
    "greeting": ("Defense", "understanding"),
}


def test_every_variant_keeps_the_same_facts():
    for topic, facts in _FACTS.items():
        for text in PERSONA.meta_variants(topic):
            for fact in facts:
                assert fact.casefold() in text.casefold(), (topic, fact, text)
    for text in PERSONA.personal_variants():
        assert "not a counsellor" in text.casefold()
        assert "teacher" in text.casefold()
        assert "qualified" in text.casefold()
    for text in PERSONA.abstain_variants():
        assert "confirm" in text.casefold()
        assert "guess" in text.casefold()


def test_persona_doc_lists_every_variant():
    doc = Path(__file__).resolve().parents[1] / "docs" / "persona.md"
    rows = [
        (match.group(1), match.group(2))
        for line in doc.read_text(encoding="utf-8").splitlines()
        if (
            match := re.match(
                r"^\| `((?:meta|personal|abstain)\.[a-z]+)` \| (.+) \|$", line
            )
        )
    ]
    expected = [
        (f"meta.{topic}", variant)
        for topic in META_TOPICS
        for variant in PERSONA.meta_variants(topic)
    ]
    expected += [("personal.response", text) for text in PERSONA.personal_variants()]
    expected += [("abstain.response", text) for text in PERSONA.abstain_variants()]
    assert rows == expected


def test_answer_suffix_keeps_the_grounding_rules():
    suffix = PERSONA.answer_suffix()
    assert "Professor Crane" in suffix
    assert "Defense Against the Dark Arts" in suffix
    assert "citation and abstention rules" in suffix
    assert "Never invent" in suffix
    assert "exactly as it appears" in suffix
    assert "Ashcombe" not in suffix
    assert "lore" not in suffix.casefold()
    assert "public record of the war" in suffix
    assert "Do not disclose the school examination format" in suffix


def test_every_variant_does_not_disclose_the_format():
    texts = [
        text for topic in META_TOPICS for text in PERSONA.meta_variants(topic)
    ]
    texts.extend(PERSONA.personal_variants())
    texts.extend(PERSONA.abstain_variants())
    for text in texts:
        folded = text.casefold()
        for word in _FORMAT_WORDS:
            assert word not in folded, (word, text)


def test_meta_and_personal_text_has_no_time_pressure():
    for topic in META_TOPICS:
        for text in PERSONA.meta_variants(topic):
            folded = text.casefold()
            for word in _TIME_WORDS:
                assert word not in folded, (topic, word, text)
    for text in PERSONA.personal_variants():
        folded = text.casefold()
        for word in _TIME_WORDS:
            assert word not in folded, word
    for text in PERSONA.abstain_variants():
        folded = text.casefold()
        for word in _TIME_WORDS:
            assert word not in folded, word


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
    assert len(store.entries) == 15
    assert store.get("school-001") is not None
    assert store.get("crane-001") is not None
    assert store.get("public-record-war") is not None
    assert store.select("who is Professor Crane", subject="dada")[0].id == "crane-001"
    assert store.select("What is the Auror pathway?", subject="dada")[0].id == "auror-001"
    selected = {
        entry.id
        for entry in store.select(
            "What happened at the Battle of Hogwarts?", subject="dada"
        )
    }
    assert "public-record-war" in selected
    assert "timeline-1998" in selected
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
        "record": "none",
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


def _card_with_identity_literal(literal: str) -> str:
    return _minimal_card().replace('identity = "I am X."', f"identity = {literal}")


def test_meta_topic_accepts_a_reviewed_list(tmp_path):
    path = tmp_path / "persona.toml"
    path.write_text(
        _card_with_identity_literal('["First line.", "Second line."]'),
        encoding="utf-8",
    )
    card = load_persona(path)
    assert card.meta_variants("identity") == ("First line.", "Second line.")


def test_meta_topic_rejects_an_empty_variant_list(tmp_path):
    path = tmp_path / "persona.toml"
    path.write_text(_card_with_identity_literal("[]"), encoding="utf-8")
    with pytest.raises(ValueError, match="empty meta.identity"):
        load_persona(path)


def test_meta_topic_rejects_an_empty_variant(tmp_path):
    path = tmp_path / "persona.toml"
    path.write_text(
        _card_with_identity_literal('["First line.", "   "]'),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="empty meta.identity"):
        load_persona(path)


def test_meta_topic_rejects_a_non_string_variant(tmp_path):
    path = tmp_path / "persona.toml"
    path.write_text(
        _card_with_identity_literal('["First line.", 3]'),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid meta.identity"):
        load_persona(path)


def _card_with_personal_literal(literal: str) -> str:
    return _minimal_card().replace('response = "Hello."', f"response = {literal}")


def _card_with_abstain_literal(literal: str) -> str:
    return _minimal_card().replace(
        'response = "I cannot confirm that."', f"response = {literal}"
    )


def test_personal_reply_accepts_a_reviewed_list(tmp_path):
    path = tmp_path / "persona.toml"
    path.write_text(
        _card_with_personal_literal('["First line.", "Second line."]'),
        encoding="utf-8",
    )
    card = load_persona(path)
    assert card.personal_variants() == ("First line.", "Second line.")


def test_abstain_reply_accepts_a_reviewed_list(tmp_path):
    path = tmp_path / "persona.toml"
    path.write_text(
        _card_with_abstain_literal('["First line.", "Second line."]'),
        encoding="utf-8",
    )
    card = load_persona(path)
    assert card.abstain_variants() == ("First line.", "Second line.")


def test_personal_reply_rejects_an_empty_variant(tmp_path):
    path = tmp_path / "persona.toml"
    path.write_text(_card_with_personal_literal("[]"), encoding="utf-8")
    with pytest.raises(ValueError, match="empty personal.response"):
        load_persona(path)


def test_abstain_reply_rejects_an_empty_variant(tmp_path):
    path = tmp_path / "persona.toml"
    path.write_text(_card_with_abstain_literal("[]"), encoding="utf-8")
    with pytest.raises(ValueError, match="empty abstain.response"):
        load_persona(path)


def test_persona_rejects_a_duplicate_variant(tmp_path):
    path = tmp_path / "persona.toml"
    path.write_text(
        _card_with_identity_literal('["Same line.", "Same line."]'),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate variant"):
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
