import { papersCopy } from "./papers";

// Student-facing venue chrome: the room tabs, the notes-missing banner and the
// closed-department card.

export const venueCopy = {
  tabs: {
    chat: "Ask the professor",
    exam: "Exam room",
    papers: papersCopy.history.heading,
  },
  packMissing:
    "The department's reviewed notes are not loaded on the server; answers come from the set texts until they are available.",
  soonTitle: "The classroom is being furnished",
  soonBody: (blurb: string): string =>
    `${blurb} This department opens when its exam bank is published.`,
  voiceInRehearsal: " — voice in rehearsal",
} as const;
