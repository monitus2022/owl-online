"""Knowledge layer: authored setting facts and subject-knowledge packs."""

from app.knowledge.lore import (
    LORE_SELECTION_VERSION,
    LoreEntry,
    LoreStore,
    load_lore,
)
from app.knowledge.materials import Material, ReferenceLink, SourceRef, chunk_text_hash
from app.knowledge.packs import (
    Concept,
    PackManifest,
    PackValidation,
    SubjectPack,
    Topic,
    index_chunks,
    load_subject_pack,
    pack_fingerprint,
    validate_pack,
    write_subject_pack,
)

__all__ = [
    "LORE_SELECTION_VERSION",
    "Concept",
    "LoreEntry",
    "LoreStore",
    "Material",
    "PackManifest",
    "PackValidation",
    "ReferenceLink",
    "SourceRef",
    "SubjectPack",
    "Topic",
    "chunk_text_hash",
    "index_chunks",
    "load_lore",
    "load_subject_pack",
    "pack_fingerprint",
    "validate_pack",
    "write_subject_pack",
]
