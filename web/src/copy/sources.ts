import { sharedCopy } from "./shared";

// Student-facing source labels. The exact book and chunk ids stay visible in
// the technical reference panel; this file owns the words around them.

export const sourceCopy = {
  rowLabel: "Passages",
  noteTitle: (label: string | null): string =>
    label !== null ? `From the department's notes: ${label}` : "From the department's notes",
  loading: "Fetching the note…",
  failed: "The note could not be opened.",
  meta: (topic: string): string => `${topic} · from the department's notes`,
  refsPrefix: "References:",
  details: "Exact references",
  loaded: "Note loaded.",
  retry: sharedCopy.retry,
} as const;
