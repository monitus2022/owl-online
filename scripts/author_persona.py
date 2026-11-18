"""Author one professor persona from a brief.

Commands:
  generate  draft a card with a pinned model, never a live card
  validate  check a draft against its brief and the shared spine
  check     check every briefed card and provenance pair (CI)
  publish   write a reviewed draft to the live card path

The runtime never calls a model. See docs/persona-authoring.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.agent.persona_authoring import (  # noqa: E402
    PersonaAuthoringError,
    build_prompt,
    build_provenance,
    check_authoring,
    generate_card,
    load_brief,
    load_provenance,
    prompt_sha256,
    render_card,
    sha256_file,
    validate_card_file,
    validate_generated,
)
from app.config import settings  # noqa: E402
from app.providers.factory import make_llm  # noqa: E402

PERSONAS = REPO_ROOT / "config" / "personas"
BRIEFS = PERSONAS / "briefs"
DRAFTS = PERSONAS / "drafts"
PROVENANCE = PERSONAS / "provenance"
SPINE = PERSONAS / "spine.toml"


def _brief_path(subject: str, override: str | None) -> Path:
    return Path(override) if override else BRIEFS / f"{subject}.toml"


def _card_path(subject: str) -> Path:
    return PERSONAS / f"{subject}.toml"


def _draft_path(subject: str, override: str | None) -> Path:
    return Path(override) if override else DRAFTS / f"{subject}.toml"


def _provenance_path(subject: str) -> Path:
    return PROVENANCE / f"{subject}.json"


def _report(problems: list[str], warnings: list[str]) -> int:
    for warning in warnings:
        print(f"warning: {warning}")
    for problem in problems:
        print(f"error: {problem}")
    if problems:
        return 1
    print("persona authoring check passed")
    return 0


def command_generate(args: argparse.Namespace) -> int:
    brief_path = _brief_path(args.subject, args.brief)
    brief = load_brief(brief_path)
    if brief.subject != args.subject:
        raise PersonaAuthoringError(
            f"brief subject {brief.subject!r} does not match --subject {args.subject!r}"
        )
    spine_text = SPINE.read_text(encoding="utf-8")
    system, user = build_prompt(brief, spine_text)
    if args.dry_run:
        print(system)
        print("\n--- USER ---\n")
        print(user)
        return 0
    llm = make_llm(
        args.provider,
        model=args.model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )
    generated = asyncio.run(generate_card(brief, llm, spine_text=spine_text))
    problems = validate_generated(brief, generated)
    if problems:
        return _report(problems, [])

    draft_path = _draft_path(args.subject, args.out)
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(render_card(generated), encoding="utf-8")
    problems = validate_card_file(brief, draft_path)
    if problems:
        return _report(problems, [])
    model_name = args.model or getattr(llm, "name", args.provider)
    provenance = build_provenance(
        brief=brief,
        brief_path=brief_path,
        card_path=draft_path,
        provider=args.provider,
        model=str(model_name),
        temperature=args.temperature,
        prompt_sha=prompt_sha256(system, user),
    )
    provenance_path = draft_path.with_suffix(".json")
    provenance_path.write_text(
        json.dumps(provenance, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"draft: {draft_path}")
    print(f"provenance: {provenance_path}")
    print(
        f"review it, then run: python scripts/author_persona.py publish "
        f"--subject {brief.subject} --reviewer <name>"
    )
    return 0


def command_validate(args: argparse.Namespace) -> int:
    brief = load_brief(_brief_path(args.subject, args.brief))
    if brief.subject != args.subject:
        raise PersonaAuthoringError(
            f"brief subject {brief.subject!r} does not match --subject {args.subject!r}"
        )
    card_path = Path(args.card) if args.card else _card_path(args.subject)
    problems = validate_card_file(brief, card_path)
    return _report(problems, [])


def command_check(args: argparse.Namespace) -> int:
    problems, warnings = check_authoring(REPO_ROOT, strict=args.strict)
    return _report(problems, warnings)


def command_publish(args: argparse.Namespace) -> int:
    if args.subject == "dada":
        raise PersonaAuthoringError(
            "dada is the standalone seed card; the merged pipeline does not publish it"
        )
    brief = load_brief(_brief_path(args.subject, args.brief))
    if brief.subject != args.subject:
        raise PersonaAuthoringError(
            f"brief subject {brief.subject!r} does not match --subject {args.subject!r}"
        )
    draft_path = _draft_path(args.subject, args.draft)
    if not draft_path.exists():
        raise PersonaAuthoringError(f"missing draft: {draft_path}")
    problems = validate_card_file(brief, draft_path)
    if problems:
        return _report(problems, [])

    provenance_path = draft_path.with_suffix(".json")
    provenance = load_provenance(provenance_path)
    if provenance.get("subject") != brief.subject:
        raise PersonaAuthoringError("draft provenance subject does not match the brief")
    if provenance.get("brief_sha256") != sha256_file(_brief_path(args.subject, args.brief)):
        raise PersonaAuthoringError("draft provenance brief hash does not match")
    if provenance.get("card_sha256") != sha256_file(draft_path):
        raise PersonaAuthoringError("draft provenance card hash does not match")

    card_path = _card_path(args.subject)
    card_path.parent.mkdir(parents=True, exist_ok=True)
    card_path.write_text(draft_path.read_text(encoding="utf-8"), encoding="utf-8")
    provenance["card"] = str(card_path)
    provenance["card_sha256"] = sha256_file(card_path)
    provenance["reviewed_by"] = args.reviewer
    provenance["reviewed_at"] = datetime.now(UTC).isoformat()
    final_path = _provenance_path(args.subject)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.write_text(
        json.dumps(provenance, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"published card: {card_path}")
    print(f"provenance: {final_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Brief-driven authoring for professor persona cards.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    generate = commands.add_parser("generate", help="draft a card from a brief")
    generate.add_argument("--subject", required=True)
    generate.add_argument("--brief", default=None)
    generate.add_argument("--out", default=None)
    generate.add_argument(
        "--provider",
        choices=("openrouter", "bedrock"),
        default=settings.provider,
    )
    generate.add_argument("--model", default=None)
    generate.add_argument("--temperature", type=float, default=0.3)
    generate.add_argument("--max-tokens", type=int, default=4000)
    generate.add_argument(
        "--dry-run",
        action="store_true",
        help="print the pinned prompt without calling a model",
    )
    generate.set_defaults(func=command_generate)

    validate = commands.add_parser("validate", help="check a card against its brief")
    validate.add_argument("--subject", required=True)
    validate.add_argument("--brief", default=None)
    validate.add_argument("--card", default=None)
    validate.set_defaults(func=command_validate)

    check = commands.add_parser("check", help="check every briefed card")
    check.add_argument("--strict", action="store_true")
    check.set_defaults(func=command_check)

    publish = commands.add_parser("publish", help="publish a reviewed draft")
    publish.add_argument("--subject", required=True)
    publish.add_argument("--reviewer", required=True)
    publish.add_argument("--brief", default=None)
    publish.add_argument("--draft", default=None)
    publish.set_defaults(func=command_publish)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except PersonaAuthoringError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
