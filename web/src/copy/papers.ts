// Student-facing paper history, noticeboard and best-mark copy.

export const papersCopy = {
  history: {
    heading: "Your papers",
    notice:
      "Marks are kept for this visit to the Academy and shown for this department. A school account will one day keep them across terms.",
    failed:
      "The paper records could not be read. Nothing is lost by trying again; if it keeps failing, the drawer stays shut.",
    loading: "Fetching the records…",
    empty:
      "The drawer is empty: no papers have been marked for this department yet. Sit one in the exam room.",
    deleted: (count: number): string =>
      `Deleted ${count} paper${count === 1 ? "" : "s"}. The drawer is empty.`,
    clear: "Clear all papers",
    clearConfirm:
      "Delete every paper from this visit, including any ungraded paper? This cannot be undone.",
    deleting: "Deleting…",
    delete: "Delete them",
    keep: "Keep them",
    deleteFailed:
      "The papers could not be deleted. They are still stored for this visit.",
    kept: "kept",
    best: "best",
  },
  results: {
    failed: "The paper records could not be read right now.",
    empty:
      "No paper has been marked for this department yet. Sit one in the exam room.",
    keptBack: "A paper was kept back; it carries no final band.",
    bestPrefix: "Best so far this visit:",
  },
  progress: {
    heading: "The noticeboard",
    notice:
      "Practice marks are kept for this visit until school accounts arrive.",
    checking: "checking the records…",
    unreadable: "the records could not be read",
    best: (label: string, total: number, max: number): string =>
      `best: ${label} (${total}/${max})`,
    keptBack: "a paper was kept back",
    furnished: "the room is furnished, no papers sat yet",
    closed: "the door is closed",
  },
} as const;
