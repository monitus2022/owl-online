"""Persona authoring: briefs, prompts, drafts, provenance and checks."""

from __future__ import annotations

import asyncio
import json
import tomllib
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agent.persona import SPINE_PATH, load_persona_merged
from app.agent.persona_authoring import (
    GeneratedPersona,
    PersonaAuthoringError,
    PersonaBrief,
    build_prompt,
    build_provenance,
    check_authoring,
    generate_card,
    load_brief,
    parse_generated,
    prompt_sha256,
    render_card,
    sha256_file,
    validate_card_file,
    validate_generated,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_BRIEF = REPO_ROOT / "config" / "personas" / "examples" / "charms.toml"


def _brief() -> PersonaBrief:
    return load_brief(EXAMPLE_BRIEF)


def _generated_data(brief: PersonaBrief) -> dict[str, object]:
    name = brief.name
    return {
        "identity": {
            "name": brief.name,
            "address": brief.address,
            "role": brief.role,
            "subject": brief.subject_title,
        },
        "register": {"stance": brief.stance},
        "meta": {
            "identity": [
                f"I am {name}, and I teach Charms at Ashcombe Academy.",
                f"You have found {name}, the Charms professor at Ashcombe.",
                f"{name}, at your service; Charms is my department.",
            ],
            "scope": [
                "Charms covers the principles and careful practice of charm-work.",
                "This department studies charm theory, movement and safe practice.",
                "We work on the reasons behind a charm before its performance.",
            ],
            "subject": [
                "Charms is the study of making an object do something it would not do by itself.",
                "In Charms we learn the principle, the movement and the safe result.",
                "Charms is precise work: the intention, the wand and the object must agree.",
            ],
            "professor": [
                f"I am {name}, and I teach the upper forms here.",
                "My department is Charms, and I have taught it since the school opened.",
                f"I am {name}; my work is to make charm theory usable.",
            ],
            "boundaries": [
                "I use only the reviewed notes and the set texts, and I do not guess.",
                "If the notes and the set texts do not support a point, I leave it unanswered.",
                "I will not invent a charm or a rule beyond the reviewed material.",
            ],
            "greeting": [
                "Welcome. Bring me the part of the charm you cannot yet explain.",
                "Good to see you. We will start with the principle, not the flourish.",
                "You are here to learn the craft. That is the right place to begin.",
            ],
        },
        "personal": [
            "I am glad you told me. I am your teacher, not a counsellor, "
            "so my help stops at the work.",
            "Thank you for saying so. My role is the work; if this is serious, "
            "please speak to someone qualified.",
            "I hear you. I can help with the course, but not beyond it; "
            "please seek proper support if needed.",
        ],
        "abstain": [
            "I cannot confirm that from the reviewed notes or the set texts, and I will not guess.",
            "That is beyond what the notes and the set texts support; I will leave it unanswered.",
            "I do not have the evidence for that in the notes or the set texts, "
            "and I will not invent it.",
        ],
        "facts": dict(brief.facts),
        "templates": dict(brief.templates),
    }


def _generated(brief: PersonaBrief) -> GeneratedPersona:
    return GeneratedPersona.model_validate(_generated_data(brief))


def _write_card(root: Path, brief: PersonaBrief) -> Path:
    card_path = root / "config" / "personas" / f"{brief.subject}.toml"
    card_path.parent.mkdir(parents=True, exist_ok=True)
    card_path.write_text(render_card(_generated(brief)), encoding="utf-8")
    return card_path


def _write_brief(root: Path, brief: PersonaBrief) -> Path:
    brief_path = root / "config" / "personas" / "briefs" / f"{brief.subject}.toml"
    brief_path.parent.mkdir(parents=True, exist_ok=True)
    brief_path.write_text(EXAMPLE_BRIEF.read_text(encoding="utf-8"), encoding="utf-8")
    return brief_path


def _write_provenance(
    root: Path, brief: PersonaBrief, brief_path: Path, card_path: Path
) -> Path:
    system, user = build_prompt(
        brief, SPINE_PATH.read_text(encoding="utf-8")
    )
    provenance = build_provenance(
        brief=brief,
        brief_path=brief_path,
        card_path=card_path,
        provider="openrouter",
        model="test/model",
        temperature=0.3,
        prompt_sha=prompt_sha256(system, user),
        spine_path=SPINE_PATH,
    )
    provenance["reviewed_by"] = "Test Reviewer"
    provenance["reviewed_at"] = "2026-11-18T00:00:00+00:00"
    path = root / "config" / "personas" / "provenance" / f"{brief.subject}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    return path


def test_brief_accepts_the_complete_example():
    brief = _brief()
    assert brief.subject == "charms"
    assert brief.name == "Professor Elowen Vane"
    assert len(brief.background) == 3
    assert brief.facts["study_place"] == "Hogwarts"


def test_brief_rejects_a_canon_staff_name():
    data = _brief().model_dump()
    data["name"] = "Professor Snape"
    data["address"] = "Professor Snape"
    with pytest.raises(ValidationError):
        PersonaBrief.model_validate(data)


def test_brief_rejects_a_template_with_a_missing_fact():
    data = _brief().model_dump()
    data["templates"] = {
        "professor.education": "I studied at {missing_fact}.",
    }
    with pytest.raises(ValidationError):
        PersonaBrief.model_validate(data)


def test_prompt_contains_the_spine_brief_and_output_schema():
    brief = _brief()
    spine = SPINE_PATH.read_text(encoding="utf-8")
    system, user = build_prompt(brief, spine)
    assert "Ashcombe Academy of Magic" in user
    assert brief.name in user
    assert "scope" in user
    assert "Return JSON" in user
    assert "Do not change the shared exam" in user
    assert prompt_sha256(system, user) != ""


def test_parse_generated_accepts_a_code_fence():
    brief = _brief()
    payload = json.dumps(_generated_data(brief))
    parsed = parse_generated(f"```json\n{payload}\n```")
    assert parsed.identity["name"] == brief.name


def test_draft_round_trips_through_the_merged_loader(tmp_path):
    brief = _brief()
    card_path = _write_card(tmp_path, brief)
    persona = load_persona_merged(card_path, SPINE_PATH)
    assert persona.name == brief.name
    assert persona.address == brief.address
    assert persona.role == brief.role
    assert persona.subject == brief.subject_title
    assert persona.stance == brief.stance
    for key, value in brief.facts.items():
        assert persona.facts[key] == value
    for key, value in brief.templates.items():
        assert persona.templates[key] == value
    assert persona.meta["scope"] == tuple(_generated_data(brief)["meta"]["scope"])


def test_generate_card_with_a_fake_llm(tmp_path):
    brief = _brief()

    class FakeLlm:
        name = "fake/authoring"

        async def generate(self, system, prompt, *, context=None):
            return json.dumps(_generated_data(brief))

    generated = asyncio.run(
        generate_card(
            brief,
            FakeLlm(),
            spine_text=SPINE_PATH.read_text(encoding="utf-8"),
        )
    )
    assert validate_generated(brief, generated) == []
    card_path = _write_card(tmp_path, brief)
    assert validate_card_file(brief, card_path) == []


def test_parse_generated_ignores_trailing_prose_with_a_brace():
    brief = _brief()
    payload = json.dumps(_generated_data(brief)) + "\nDone, with a trailing }."
    parsed = parse_generated(payload)
    assert parsed.identity["name"] == brief.name


def test_render_card_escapes_quotes_backslashes_newlines_and_unicode(tmp_path):
    brief = _brief()
    data = _generated_data(brief)
    data["meta"]["greeting"][0] = 'A "quoted" line \\ with a newline\nand café.'
    text = render_card(GeneratedPersona.model_validate(data))
    parsed = tomllib.loads(text)
    assert parsed["meta"]["greeting"][0] == 'A "quoted" line \\ with a newline\nand café.'


def test_validate_generated_rejects_identity_and_fact_drift():
    brief = _brief()
    data = _generated_data(brief)
    data["identity"]["name"] = "Professor Someone Else"
    data["facts"] = {**brief.facts, "study_place": "Beauxbatons"}
    problems = validate_generated(brief, GeneratedPersona.model_validate(data))
    assert any("identity" in problem for problem in problems)
    assert any("facts" in problem for problem in problems)


def test_validate_generated_rejects_placeholders_and_banned_wording():
    brief = _brief()
    data = _generated_data(brief)
    data["meta"]["greeting"][0] = "As an AI, I can help with that."
    data["personal"][0] = "TODO: write the personal response."
    problems = validate_generated(brief, GeneratedPersona.model_validate(data))
    assert any("mentions 'as an ai'" in problem for problem in problems)
    assert any("placeholder" in problem for problem in problems)


def test_validate_card_file_rejects_a_missing_card(tmp_path):
    brief = _brief()
    problems = validate_card_file(brief, tmp_path / "missing.toml")
    assert problems


def test_check_without_briefs_is_a_warning(tmp_path):
    problems, warnings = check_authoring(tmp_path)
    assert problems == []
    assert any("no persona briefs" in warning for warning in warnings)


def test_check_names_the_legacy_cards_on_the_real_repo():
    problems, warnings = check_authoring(REPO_ROOT)
    assert problems == []
    text = " ".join(warnings)
    for subject in ("dada", "charms", "potions", "transfiguration", "herbology"):
        assert subject in text


def test_strict_fails_when_no_briefs_exist(tmp_path):
    problems, _ = check_authoring(tmp_path, strict=True)
    assert any("no persona briefs" in problem for problem in problems)


def test_check_accepts_a_complete_fixture_and_rejects_drift(tmp_path):
    brief = _brief()
    brief_path = _write_brief(tmp_path, brief)
    card_path = _write_card(tmp_path, brief)
    _write_provenance(tmp_path, brief, brief_path, card_path)

    problems, warnings = check_authoring(tmp_path)
    assert problems == []
    assert warnings == []

    # A late human edit invalidates the recorded card hash.
    card_path.write_text(
        card_path.read_text(encoding="utf-8") + "\n# late edit\n",
        encoding="utf-8",
    )
    problems, _ = check_authoring(tmp_path)
    assert any("card hash drifted" in problem for problem in problems)
    assert sha256_file(card_path) != json.loads(
        (tmp_path / "config" / "personas" / "provenance" / "charms.json").read_text()
    )["card_sha256"]


def test_check_rejects_missing_provenance(tmp_path):
    brief = _brief()
    _write_brief(tmp_path, brief)
    _write_card(tmp_path, brief)
    problems, _ = check_authoring(tmp_path)
    assert any("missing provenance" in problem for problem in problems)


def _draft_fixture(
    root: Path, brief: PersonaBrief
) -> tuple[Path, Path, Path, Path]:
    brief_path = _write_brief(root, brief)
    draft_path = root / "config" / "personas" / "drafts" / f"{brief.subject}.toml"
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(render_card(_generated(brief)), encoding="utf-8")
    system, user = build_prompt(
        brief, SPINE_PATH.read_text(encoding="utf-8")
    )
    provenance = build_provenance(
        brief=brief,
        brief_path=brief_path,
        card_path=draft_path,
        provider="openrouter",
        model="test/model",
        temperature=0.3,
        prompt_sha=prompt_sha256(system, user),
        spine_path=SPINE_PATH,
    )
    draft_provenance = draft_path.with_suffix(".json")
    draft_provenance.write_text(json.dumps(provenance), encoding="utf-8")
    card_path = root / "config" / "personas" / f"{brief.subject}.toml"
    final_provenance = (
        root
        / "config"
        / "personas"
        / "provenance"
        / f"{brief.subject}.json"
    )
    return brief_path, draft_path, card_path, final_provenance


def test_publish_card_writes_only_after_validation(tmp_path):
    from app.agent.persona_authoring import publish_card

    brief = _brief()
    brief_path, draft_path, card_path, final_provenance = _draft_fixture(
        tmp_path, brief
    )
    problems = publish_card(
        brief_path=brief_path,
        draft_path=draft_path,
        draft_provenance_path=draft_path.with_suffix(".json"),
        card_path=card_path,
        provenance_path=final_provenance,
        reviewer="Test Reviewer",
        spine_path=SPINE_PATH,
    )
    assert problems == []
    assert card_path.exists()
    provenance = json.loads(final_provenance.read_text(encoding="utf-8"))
    assert provenance["reviewed_by"] == "Test Reviewer"
    assert provenance["card_sha256"] == sha256_file(card_path)


def test_publish_card_refuses_a_blank_reviewer_and_leaves_the_card(tmp_path):
    from app.agent.persona_authoring import publish_card

    brief = _brief()
    brief_path, draft_path, card_path, final_provenance = _draft_fixture(
        tmp_path, brief
    )
    problems = publish_card(
        brief_path=brief_path,
        draft_path=draft_path,
        draft_provenance_path=draft_path.with_suffix(".json"),
        card_path=card_path,
        provenance_path=final_provenance,
        reviewer="   ",
        spine_path=SPINE_PATH,
    )
    assert any("reviewer" in problem for problem in problems)
    assert not card_path.exists()


def test_publish_card_requires_replace_identity_for_a_different_professor(
    tmp_path,
):
    from app.agent.persona_authoring import publish_card

    brief = _brief()
    brief_path, draft_path, card_path, final_provenance = _draft_fixture(
        tmp_path, brief
    )
    other = _generated_data(brief)
    other["identity"] = {
        **other["identity"],
        "name": "Professor Other",
        "address": "Professor Other",
    }
    card_path.parent.mkdir(parents=True, exist_ok=True)
    card_path.write_text(
        render_card(GeneratedPersona.model_validate(other)), encoding="utf-8"
    )
    problems = publish_card(
        brief_path=brief_path,
        draft_path=draft_path,
        draft_provenance_path=draft_path.with_suffix(".json"),
        card_path=card_path,
        provenance_path=final_provenance,
        reviewer="Test Reviewer",
        spine_path=SPINE_PATH,
    )
    assert any("different professor" in problem for problem in problems)
    assert "Professor Other" in card_path.read_text(encoding="utf-8")


def test_publish_card_refuses_an_example_brief(tmp_path):
    from app.agent.persona_authoring import publish_card

    problems = publish_card(
        brief_path=EXAMPLE_BRIEF,
        draft_path=tmp_path / "draft.toml",
        draft_provenance_path=tmp_path / "draft.json",
        card_path=tmp_path / "live.toml",
        provenance_path=tmp_path / "provenance.json",
        reviewer="Test Reviewer",
        spine_path=SPINE_PATH,
    )
    assert any("briefs" in problem for problem in problems)


def test_invalid_draft_leaves_the_live_card_untouched(tmp_path):
    from app.agent.persona_authoring import publish_card

    brief = _brief()
    brief_path, draft_path, card_path, final_provenance = _draft_fixture(
        tmp_path, brief
    )
    card_path.parent.mkdir(parents=True, exist_ok=True)
    live_text = render_card(_generated(brief))
    card_path.write_text(live_text, encoding="utf-8")
    draft_path.write_text(
        draft_path.read_text(encoding="utf-8")
        + "\n[boundaries]\nfacts = \"Anything goes.\"\n",
        encoding="utf-8",
    )
    problems = publish_card(
        brief_path=brief_path,
        draft_path=draft_path,
        draft_provenance_path=draft_path.with_suffix(".json"),
        card_path=card_path,
        provenance_path=final_provenance,
        reviewer="Test Reviewer",
        spine_path=SPINE_PATH,
    )
    assert problems
    assert card_path.read_text(encoding="utf-8") == live_text


def test_provenance_prompt_and_spine_drift_are_rejected(tmp_path):
    from app.agent.persona_authoring import (
        load_provenance,
        provenance_problems,
    )

    brief = _brief()
    brief_path, draft_path, _, _ = _draft_fixture(tmp_path, brief)
    provenance_path = draft_path.with_suffix(".json")
    provenance = load_provenance(provenance_path)
    assert (
        provenance_problems(
            brief,
            provenance,
            brief_path,
            draft_path,
            SPINE_PATH,
            require_reviewer=False,
        )
        == []
    )
    provenance["prompt_sha256"] = "deadbeef"
    assert any(
        "prompt hash" in problem
        for problem in provenance_problems(
            brief,
            provenance,
            brief_path,
            draft_path,
            SPINE_PATH,
            require_reviewer=False,
        )
    )
    provenance["prompt_sha256"] = json.loads(
        provenance_path.read_text(encoding="utf-8")
    )["prompt_sha256"]
    provenance["spine_sha256"] = "deadbeef"
    assert any(
        "spine hash" in problem
        for problem in provenance_problems(
            brief,
            provenance,
            brief_path,
            draft_path,
            SPINE_PATH,
            require_reviewer=False,
        )
    )


def test_brief_contract_rejects_a_shared_spine_fact(tmp_path):
    from app.agent.persona_authoring import validate_brief_contract

    data = _brief().model_dump()
    data["facts"] = {**data["facts"], "study_place": "Durmstrang"}
    problems = validate_brief_contract(
        PersonaBrief.model_validate(data), SPINE_PATH
    )
    assert any("study_place" in problem for problem in problems)


def test_card_delta_rejects_a_boundaries_override(tmp_path):
    from app.agent.persona_authoring import validate_card_delta

    brief = _brief()
    card_path = _write_card(tmp_path, brief)
    card_path.write_text(
        card_path.read_text(encoding="utf-8")
        + "\n[boundaries]\nfacts = \"Anything goes.\"\n",
        encoding="utf-8",
    )
    problems = validate_card_delta(card_path, SPINE_PATH)
    assert any("boundaries" in problem for problem in problems)


def test_canon_check_does_not_flag_ordinary_sprout_or_vector():
    from app.agent.persona_authoring import _variants_problems

    assert _variants_problems(
        "meta.greeting",
        [
            "The seedlings sprout in the greenhouse every spring.",
            "A vector carries the direction and the length together.",
            "The lesson begins with a careful observation.",
        ],
    ) == []
    assert any(
        "canon" in problem
        for problem in _variants_problems(
            "meta.greeting",
            [
                "Professor Sprout tends the greenhouses.",
                "A vector carries the direction and the length together.",
                "The lesson begins with a careful observation.",
            ],
        )
    )


def test_draft_target_stays_under_drafts():
    from scripts.author_persona import DRAFTS, PERSONAS, _draft_target

    assert _draft_target(DRAFTS / "charms.toml") == DRAFTS / "charms.toml"
    for path in (
        PERSONAS / "charms.toml",
        PERSONAS / "spine.toml",
        DRAFTS / "charms.json",
    ):
        with pytest.raises(PersonaAuthoringError):
            _draft_target(path)


def test_sha256_file_normalizes_windows_line_endings(tmp_path):
    lf = tmp_path / "lf.toml"
    crlf = tmp_path / "crlf.toml"
    lf.write_bytes(b"name = 'Vane'\n")
    crlf.write_bytes(b"name = 'Vane'\r\n")
    assert sha256_file(lf) == sha256_file(crlf)


def test_publish_requires_a_reviewer():
    from scripts.author_persona import build_parser

    with pytest.raises(SystemExit):
        build_parser().parse_args(["publish", "--subject", "charms"])


def test_publish_path_is_not_the_draft_path():
    # The CLI's publish contract: a live card path is separate from the draft.
    from scripts.author_persona import _card_path, _draft_path

    assert _card_path("charms") != _draft_path("charms", None)
