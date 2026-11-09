"""Derived material selector for lesson mode.

A pack is a small, curated set (25 materials for DADA), so its retrieval layer
is derived rather than persisted: embed the material texts in memory at
startup, then score a question by cosine. The vectors are rebuilt from
`materials.jsonl` on every start, so they cannot drift from the pack
fingerprint, and there is no second index to validate or back up.

The corpus join via `Material.source_refs` stays the grounding check; this
module only chooses which reviewed materials a question is about. Measured on
the published DADA pack: the corpus-first projection reached the intended
material 83% at top-10 but ranked it first 42%, while this selector put it in
the top three 100% of the time on the same natural questions.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

from app.knowledge.materials import Material
from app.knowledge.packs import PackStore, SubjectPack
from app.knowledge.terms import content_terms, phrase_match_score
from app.providers.contracts import Embedder

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 3
# Calibrated for qwen3-embedding:0.6b on the DADA pack: related questions
# scored 0.598-0.791, off-topic 0.160-0.549. Recalibrate with the embedder.
DEFAULT_MIN_SCORE = 0.58


def _embedding_text(pack: SubjectPack, material: Material) -> str:
    """Title and aliases first: a concept name is the strongest signal."""
    concept = next(
        (c for c in pack.concepts if c.concept_id == material.concept), None
    )
    title = concept.title if concept is not None else material.concept
    aliases = " ".join(concept.aliases) if concept is not None else ""
    return f"{title}. {aliases}. {material.text}".strip()


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


@dataclass(frozen=True)
class SubjectVectors:
    """One subject's material ids and their derived vectors, in pack order."""

    subject: str
    material_ids: tuple[str, ...]
    vectors: tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class LessonSelector:
    """In-memory material selection over the published packs."""

    store: PackStore
    embedder: Embedder
    vectors: dict[str, SubjectVectors]
    # One-entry-per-question cache, bounded; lesson questions repeat far less
    # than corpus questions, but the convention is the same: cache embeddings
    # by model and input. The selector is tied to one embedder at build time.
    query_cache: dict[str, tuple[float, ...]] = field(
        default_factory=dict, compare=False
    )
    cache_size: int = 256

    @classmethod
    async def build(
        cls, store: PackStore, embedder: Embedder
    ) -> LessonSelector:
        """Embed every material once; subject-scoped at query time."""
        vectors: dict[str, SubjectVectors] = {}
        for subject in store.subjects():
            pack = store.get(subject)
            if pack is None or not pack.materials:
                continue
            documents = [_embedding_text(pack, m) for m in pack.materials]
            embedded = await embedder.embed(documents)
            if len(embedded) != len(documents):
                raise ValueError(
                    f"embedder returned {len(embedded)} vectors for "
                    f"{len(documents)} materials in {subject}"
                )
            dims = len(embedded[0])
            if dims == 0 or any(len(vector) != dims for vector in embedded):
                raise ValueError(f"inconsistent material vector dims in {subject}")
            vectors[subject] = SubjectVectors(
                subject=subject,
                material_ids=tuple(m.material_id for m in pack.materials),
                vectors=tuple(tuple(vector) for vector in embedded),
            )
            logger.info(
                "lesson selector: embedded %d materials for %s",
                len(documents),
                subject,
            )
        return cls(store=store, embedder=embedder, vectors=vectors)

    def subjects(self) -> tuple[str, ...]:
        return tuple(sorted(self.vectors))

    def select_lexical(
        self,
        question: str,
        *,
        subject: str,
        top_k: int = DEFAULT_TOP_K,
    ) -> list[Material]:
        """Curated concept-title and alias matches, for a weak embedding query.

        A comparison question such as "Compare Expelliarmus with Avifors"
        embeds poorly because the off-pack half dominates the vector. Matching
        the pack's reviewed concept vocabulary keeps the in-pack half in the
        prompt. Only full titles and aliases match: the generic word "charm"
        does not pull in "Disarming Charm".
        """
        pack = self.store.get(subject)
        if pack is None:
            return []
        question_terms = content_terms(question)
        scored: list[tuple[int, str, Material]] = []
        for material in pack.materials:
            concept = next(
                (c for c in pack.concepts if c.concept_id == material.concept),
                None,
            )
            if concept is None:
                continue
            score = 0
            for phrase in (concept.title, *concept.aliases):
                score += phrase_match_score(phrase, question_terms)
            if score:
                scored.append((score, material.material_id, material))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [material for _, _, material in scored[: max(1, top_k)]]

    async def select(
        self,
        question: str,
        *,
        subject: str,
        top_k: int = DEFAULT_TOP_K,
        min_score: float = DEFAULT_MIN_SCORE,
    ) -> list[Material]:
        """The top materials for a question, highest cosine first.

        No vector store, no threshold rule beyond the optional floor: at this
        size an exhaustive scan is the whole index.
        """
        vectors = self.vectors.get(subject)
        pack = self.store.get(subject)
        if vectors is None or pack is None:
            return []
        query_vector = self.query_cache.get(question)
        if query_vector is None:
            embedded = await self.embedder.embed([question])
            if not embedded:
                raise ValueError("embedder returned no vector for the question")
            query_vector = tuple(embedded[0])
            if vectors.vectors and len(query_vector) != len(vectors.vectors[0]):
                raise ValueError(
                    f"query vector has {len(query_vector)} dims, "
                    f"materials have {len(vectors.vectors[0])} for {subject}"
                )
            if len(self.query_cache) >= self.cache_size:
                self.query_cache.pop(next(iter(self.query_cache)))
            self.query_cache[question] = query_vector
        scored = [
            (_cosine(query_vector, vector), material_id)
            for vector, material_id in zip(
                vectors.vectors, vectors.material_ids, strict=True
            )
        ]
        scored.sort(key=lambda item: (-item[0], item[1]))
        # The floor applies to the best match, not to each item: a strong top
        # hit may still have weaker (but useful) companions, while a weak top
        # hit means the pack does not cover the question.
        if not scored or scored[0][0] < min_score:
            return []
        selected: list[Material] = []
        for _, material_id in scored[: max(1, top_k)]:
            material = pack.find_material(material_id)
            if material is not None:
                selected.append(material)
        return selected
