import { sharedCopy } from "./shared";

// Student-facing venue chrome: the room tabs, the notes-missing banner and the
// closed-department card.

export const venueCopy = {
  tabs: {
    chat: "Ask the professor",
    exam: "Exam room",
    papers: sharedCopy.yourPapers,
  },
  packMissing:
    "The department's notes are not in this room yet; I will answer from the reference books until they arrive.",
  soonTitle: "The classroom is being furnished",
  soonBody: (blurb: string): string =>
    `${blurb} This department opens when its papers are ready.`,
} as const;
