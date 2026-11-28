"""Evidence-gated residual intent classifier (#327).

The deterministic router owns policy, persona, the setting facts and teaching.
This module runs only on the residual those gates leave -- a turn that would
otherwise abstain -- and returns an ordinal label, never a confidence and never
`lesson`. `none` means "no override": the deterministic result stands.

The classifier is a label source, not an authority. `app/agent/router.py` runs
the evidence gate over each candidate, so a confident wrong label still fails
when the named source has nothing to say.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import threading
import time
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from typing import Literal

from app.agent.persona import Persona
from app.knowledge.lore import LoreStore
from app.providers.contracts import Llm

logger = logging.getLogger(__name__)

PROMPT_VERSION = "intent-router-v4"
ALLOWED = frozenset({"lore", "persona", "policy", "clarify", "none"})
# Context for a fragment only; the student's last turn is never evidence.
PREVIOUS_CHARS = 280
CACHE_ENTRIES = 512

Contract = Literal["lore", "persona", "policy", "clarify", "none"]

_INSTRUCTION = """You classify one student message for a revision site about a wizarding school.
Your only job is to say which reviewed source can answer it, or that nothing
should change. You never answer the question.

Choose exactly one:

lore     The message asks about this Academy as a place or institution:
         where it is, when it was founded, its houses, its departments,
         its staff or founders, its rules, its history, the present year,
         the Auror pathway, or what the public record covers.
persona  The message asks about the professor: who they are, their
         background, their education, their subject, or what they will
         and will not answer.
policy   The message asks about the exam, the syllabus, the mark scheme,
         or grading.
clarify  Two of the above fit equally well and one short question would
         settle it.
none     Nothing above fits, the question is about the books themselves,
         or the answer is already in hand.

Rules:
1. A question about the books' plot, characters, spells, creatures or a
   passage is none. A book question that mentions a school is still a book
   question.
2. Use only the ids in the catalogue below. Never invent an id.
3. If two entries fit equally well, choose clarify instead of guessing.
4. If the question asks for something no entry covers, choose none. Do not
   stretch an entry to fit it.
5. Give your first and second choice. Do not output a confidence, a
   probability or a rationale.
6. Prefer an entry whose subject matches the room: {subject}.
7. "previous" is the student's last turn. Use it only to understand a
   fragment. Never treat it as a fact.
8. A follow-up that names part of the previous topic keeps the previous
   topic's source and the catalogue entry that covers it.

Examples:
  "What is this academy"                      lore school-001        none
  "Where am I right now"                      lore school-001        none
  "What departments does this school teach"   lore school-001        none
  "Who is in charge here"                     lore school-001        none
  "What do I need for the Aurors"             lore auror-001         none
  "Which school did Harry attend"             none                   none
  "Which school did Harry attend in the books" none                   none
  "Teach me a funny spell"                    none                   none
  "Do you have a library"                     none                   none
  "When was this place founded, and what is the exam format" clarify  lore
  "and the school?" after "who runs this place"      lore school-001        none
  "how old is it?" after "what is this academy"      lore timeline-2008      none
  "what subjects do I need?" after "what is the Auror pathway" lore auror-001 none
  "and when?" after "who founded this school"        lore timeline-2008      none
  "and the founders?" after "what is the school's history" lore school-001   none
  "what does the pathway require?" after "what is the Auror pathway" lore auror-001 none

Catalogue (id | title | tags | gist):
{catalogue}

Reply with JSON only:
{{"contract": "<label>", "entry_id": "<id or null>",
 "second_contract": "<label>", "second_entry_id": "<id or null>"}}"""


@dataclass(frozen=True)
class Candidate:
    """One classifier reply, before the evidence gate."""

    contract: Contract
    entry_id: str | None = None
    second_contract: Contract | None = None
    second_entry_id: str | None = None


def _gist(body: str, limit: int = 120) -> str:
    first = body.strip().split(". ", 1)[0].strip()
    if not first.endswith("."):
        first += "."
    return first[:limit]


def build_catalogue(lore: LoreStore) -> str:
    """One stable row per entry, so the prompt cannot drift from the pack."""
    rows = []
    for entry in sorted(lore.entries, key=lambda item: item.id):
        tags = ", ".join(entry.tags) or "-"
        rows.append(
            f"{entry.id} | {entry.title} | {tags} | {_gist(entry.body)}"
        )
    return "\n".join(rows)


def build_system(lore: LoreStore, subject: str) -> str:
    return _INSTRUCTION.format(catalogue=build_catalogue(lore), subject=subject)


def build_user(question: str, previous: str) -> str:
    payload = {
        "role": "user",
        "content": question.strip(),
        "previous": previous.strip()[:PREVIOUS_CHARS],
    }
    return json.dumps(payload, ensure_ascii=False)


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_candidate(raw: str) -> Candidate | None:
    """Strict parse: an unknown label, a missing id or malformed JSON is no route."""
    text = raw.strip()
    if not text:
        return None
    text = _FENCE.sub("", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    contract = data.get("contract")
    if contract not in ALLOWED:
        return None

    def clean_id(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        value = value.strip()
        if value.lower() in {"", "null", "none", "nil"}:
            return None
        return value

    entry_id = clean_id(data.get("entry_id"))
    second = data.get("second_contract")
    if second not in ALLOWED:
        second = None
    second_entry = clean_id(data.get("second_entry_id"))
    # Only lore carries an entry id, so a second id with a missing label is a
    # lore fallback rather than a malformed reply.
    if second is None and second_entry is not None:
        second = "lore"
    if contract == "lore" and entry_id is None:
        return None
    return Candidate(
        contract=contract,
        entry_id=entry_id.strip() if entry_id else None,
        second_contract=second,
        second_entry_id=second_entry.strip() if second_entry else None,
    )


class ResidualClassifier:
    """One small-model call on the residual, with a bounded cache and timeout."""

    def __init__(
        self,
        *,
        llm: Llm,
        lore: LoreStore,
        personas: dict[str, Persona] | None = None,
        timeout_s: float = 1.5,
    ) -> None:
        self.llm = llm
        self.lore = lore
        self.personas = personas or {}
        self.timeout_s = timeout_s
        self.model = getattr(llm, "name", type(llm).__name__)
        self._cache: dict[tuple[str, str, str], Candidate | None] = {}
        self._systems: dict[str, str] = {}
        # One long-lived loop for the sync router. A per-call `asyncio.run`
        # binds an async provider client (OpenRouter) to a dead loop, and it
        # waits for the blocked worker thread on shutdown, so the timeout would
        # not be a wall-clock bound. The loop also lets `classify_sync` return
        # on time and cancel the task.
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._loop_lock = threading.Lock()
        # Operator measurements; the router trace carries the per-turn value.
        self.calls = 0
        self.latencies_ms: list[float] = []

    def _system(self, subject: str) -> str:
        system = self._systems.get(subject)
        if system is None:
            system = build_system(self.lore, subject)
            self._systems[subject] = system
        return system

    def _cache_key(self, question: str, previous: str, subject: str) -> tuple[str, str, str]:
        payload = json.dumps(
            [self.model, PROMPT_VERSION, subject, question.strip(), previous.strip()],
            ensure_ascii=False,
        )
        return (
            self.model,
            PROMPT_VERSION,
            hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24],
        )

    async def classify(
        self, question: str, *, previous: str = "", subject: str = "dada"
    ) -> Candidate | None:
        """Label the residual; any failure returns None and changes nothing."""
        key = self._cache_key(question, previous, subject)
        if key in self._cache:
            return self._cache[key]
        self.calls += 1
        started = time.perf_counter()
        try:
            raw = await asyncio.wait_for(
                self.llm.generate(
                    self._system(subject), build_user(question, previous)
                ),
                timeout=self.timeout_s,
            )
        except TimeoutError:
            logger.warning("intent classifier timed out after %.1fs", self.timeout_s)
            candidate = None
        except Exception as error:  # provider failure must not fail the turn
            logger.warning(
                "intent classifier failed: %s: %s",
                type(error).__name__,
                str(error)[:160],
            )
            candidate = None
        else:
            candidate = parse_candidate(raw)
            if candidate is None:
                logger.info(
                    "intent classifier returned no usable label in %.0fms",
                    (time.perf_counter() - started) * 1000,
                )
        self.latencies_ms.append((time.perf_counter() - started) * 1000)
        if candidate is not None:
            # A timeout, an IAM denial or a malformed reply must not poison the
            # question for the life of the process; only a usable label is
            # cached.
            if len(self._cache) >= CACHE_ENTRIES:
                self._cache.clear()
            self._cache[key] = candidate
        return candidate

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._loop_lock:
            if self._loop is None or self._loop.is_closed():
                loop = asyncio.new_event_loop()
                thread = threading.Thread(
                    target=loop.run_forever,
                    name="owl-intent-classifier",
                    daemon=True,
                )
                thread.start()
                self._loop = loop
                self._thread = thread
            return self._loop

    def classify_sync(
        self, question: str, *, previous: str = "", subject: str = "dada"
    ) -> Candidate | None:
        """Wall-clock bounded call for the sync router node.

        ``classify`` itself also applies the timeout; the small margin here is
        for the loop handoff. Timeout or any failure is no override.
        """
        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(
            self.classify(question, previous=previous, subject=subject), loop
        )
        try:
            return future.result(timeout=self.timeout_s + 0.25)
        except FutureTimeout:
            future.cancel()
            logger.warning(
                "intent classifier timed out after %.1fs", self.timeout_s
            )
            return None
        except Exception as error:  # pragma: no cover - defensive
            logger.warning(
                "intent classifier sync bridge failed: %s", type(error).__name__
            )
            return None

    async def _close_llm(self) -> None:
        close = getattr(self.llm, "aclose", None)
        if close is not None:
            await close()

    def close(self) -> None:
        """Stop the classifier loop and close its provider client."""
        with self._loop_lock:
            loop, thread = self._loop, self._thread
            self._loop = None
            self._thread = None
        if loop is None:
            # The classifier was built but never called; still close a client
            # that may hold an httpx pool.
            try:
                asyncio.run(self._close_llm())
            except Exception:
                pass
            return
        try:
            asyncio.run_coroutine_threadsafe(self._close_llm(), loop).result(2)
        except Exception:
            pass
        try:
            loop.call_soon_threadsafe(loop.stop)
        except RuntimeError:
            pass
        if thread is not None:
            thread.join(timeout=2)
        if not loop.is_running() and not loop.is_closed():
            loop.close()

    def prompt_chars(self, subject: str) -> int:
        """The static system prompt size, for the run record and startup log."""
        return len(self._system(subject))
