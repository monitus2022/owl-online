// Human-facing source labels for chat citations.
//
// The server returns citation ids: material ids such as
// `dada-dark-creatures-boggarts-counter`, book chunk ids such as
// `b3-c07-0041`, and typed citations such as `lesson:...`, `persona:...`,
// `lore:...` and `policy:script:...`. The chat shows a readable Sources row
// built from those ids and keeps the exact strings under "Source details".
// No verification or contract changes here: this module only decides what a
// student reads.

const SUBJECT_PREFIXES = new Set([
  "dada",
  "charms",
  "potions",
  "transfiguration",
  "herbology",
]);

const CHUNK_ID = /^b(\d+)-c(\d+)-[a-z0-9]+$/i;

// The citation formats the model is allowed to emit inline. The final payload
// remains the authority; this only removes the brackets from the prose.
const INLINE_MARKER =
  /\[(?:b\d+-c\d+-[a-z0-9]+|mat:[^\]]+|lore:[^\]]+|lesson:[^\]]+|persona:[^\]]+|policy:script:[^\]]+)\]\s*/gi;

function titleCase(id: string): string {
  return id
    .split(/[-_.]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function humanizeMaterialId(id: string): string {
  const parts = id.split("-").filter(Boolean);
  if (parts.length > 1 && SUBJECT_PREFIXES.has(parts[0])) parts.shift();
  if (parts.length === 0) return id;
  // The pack ids are subject-topic-concept-facet. Without the pack metadata,
  // join the words before the last two so a hyphenated topic such as
  // "dark-creatures" reads as one phrase.
  const groups =
    parts.length > 2
      ? [parts.slice(0, -2), parts.slice(-2, -1), parts.slice(-1)]
      : parts.map((part) => [part]);
  return groups
    .map((group) => {
      const phrase = group.join(" ");
      return phrase.charAt(0).toUpperCase() + phrase.slice(1);
    })
    .join(" · ");
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// The authored pack prose carries inline grounding refs such as
// "[b3-c07-0041]". The note panel already lists each ref as Book/Chapter plus
// the exact chunk id, so the reading surface drops the inline copies and
// leaves the provenance line intact. Only the material's own refs are
// removed, so an unrelated bracketed token survives.
export function stripChunkRefs(text: string, ids: string[]): string {
  const unique = Array.from(new Set(ids.filter(Boolean)));
  if (unique.length === 0) return text;
  const union = unique.map(escapeRegExp).join("|");
  // A ref glued to the next word keeps the space before it; a ref that stands
  // as its own token takes the space with it, so "most [id], and" reads
  // "most, and" rather than "most , and".
  const glued = new RegExp(`\\[(?:${union})\\](?=\\p{L})`, "giu");
  const standing = new RegExp(`\\s*\\[(?:${union})\\]`, "giu");
  const stripped = text.replace(glued, "").replace(standing, "");
  if (stripped === text) return text;
  // Adjacent refs can leave a comma in front of another punctuation mark.
  // Only the comma/semicolon artifact is collapsed, so a legitimate colon or
  // ellipsis elsewhere in the note is left alone.
  let cleaned = stripped;
  for (let pass = 0; pass < 4; pass += 1) {
    const next = cleaned.replace(/[,;]\s*(?=[,.;:!?])/g, "");
    if (next === cleaned) break;
    cleaned = next;
  }
  return cleaned.replace(/[ \t]{2,}/g, " ").trim();
}

export function bookLabel(book: number | string, chapter: number | string): string {
  return `Book ${Number(book)}, Chapter ${Number(chapter)}`;
}

function chapterLabel(id: string): { key: string; label: string } | null {
  const match = CHUNK_ID.exec(id);
  if (!match) return null;
  const book = String(Number(match[1]));
  const chapter = String(Number(match[2]));
  return {
    key: `chapter:${book}:${chapter}`,
    label: bookLabel(book, chapter),
  };
}

export interface SourceInput {
  materials?: string[];
  citations?: string[];
  typedCitations?: string[];
}

export interface SourceChip {
  key: string;
  label: string;
  // Present only for a reviewed material id; the UI makes these clickable.
  materialId?: string;
}

// The readable row: material breadcrumb, one chip per cited chapter, lore
// entries, and a plain label for a persona note or a policy nameplate. Typed
// lesson citations point at the material and chapter already shown, so they
// are kept out of the row and preserved under Source details.
export function sourceChips({
  materials = [],
  citations = [],
  typedCitations = [],
}: SourceInput): SourceChip[] {
  const chips = new Map<string, SourceChip>();
  const add = (key: string, label: string, materialId?: string) => {
    if (!chips.has(key)) chips.set(key, { key, label, materialId });
  };

  for (const id of materials) {
    add(`mat:${id}`, humanizeMaterialId(id), id);
  }

  for (const citation of citations) {
    if (citation.startsWith("lore:")) {
      const id = citation.slice(5);
      add(`lore:${id}`, `Lore · ${titleCase(id)}`);
      continue;
    }
    const chapter = chapterLabel(citation);
    if (chapter) add(chapter.key, chapter.label);
    else add(`cite:${citation}`, titleCase(citation) || citation);
  }

  for (const citation of typedCitations) {
    if (citation.startsWith("persona:")) {
      add("persona", "Professor's note");
    } else if (citation.startsWith("policy:script:")) {
      add("policy", "Academy policy");
    } else if (citation.startsWith("lore:")) {
      const id = citation.slice(5);
      add(`lore:${id}`, `Lore · ${titleCase(id)}`);
    }
    // `lesson:` citations are the material and chapter ids above.
  }

  return [...chips.values()];
}

export function stripCitationMarkers(text: string): string {
  return text
    .replace(INLINE_MARKER, "")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/[ \t]+([.,;:!?])/g, "$1")
    // "fear. [id]." leaves the sentence and the citation's final stop behind.
    .replace(/(^|[^.])\s*\.\s*\.\s*$/g, "$1.")
    .trim();
}

export interface RawSourceGroup {
  label: string;
  ids: string[];
}

// The exact identifiers behind the disclosure, grouped so they stay
// inspectable without becoming the main reading surface.
export function rawSourceGroups({
  materials = [],
  citations = [],
  typedCitations = [],
}: SourceInput): RawSourceGroup[] {
  const groups: RawSourceGroup[] = [];
  if (materials.length > 0) {
    groups.push({ label: "Material ids", ids: materials });
  }
  const chunks = citations.filter((id) => !id.startsWith("lore:"));
  if (chunks.length > 0) {
    groups.push({ label: "Book chunk ids", ids: chunks });
  }
  const lore = citations
    .filter((id) => id.startsWith("lore:"))
    .map((id) => id.slice(5));
  if (lore.length > 0) {
    groups.push({ label: "Lore ids", ids: lore });
  }
  if (typedCitations.length > 0) {
    groups.push({ label: "Typed citations", ids: typedCitations });
  }
  return groups;
}
