// Student-facing source labels. Book and material ids stay in the data layer;
// this file owns the words around them.

export const sourceCopy = {
  rowLabel: "Sources",
  noteTitle: (label: string | null): string =>
    label ? `Reviewed note: ${label}` : "Reviewed note",
  loading: "Fetching the reviewed note…",
  failed: "The reviewed note could not be opened.",
  meta: (topic: string, packVersion: string): string =>
    `${topic} · reviewed note · pack ${packVersion}`,
  refsPrefix: "Sources:",
  details: "Source details",
  loaded: "Reviewed note loaded.",
} as const;
