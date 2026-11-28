// Student-facing chat failure lines. The API clients keep the status logic;
// this file owns the words.

export const chatErrorCopy = {
  timeout: "The Academy did not answer in time. Please ask again.",
  unreachable: "The Academy is not answering. Please try again.",
  generic: "Something went wrong at the Academy. Please try again.",
  stalled: "The answer stalled. Please ask again.",
  rateLimited: (wait: number): string =>
    `Too many questions at once — the queue outside the office clears in ${wait} seconds.`,
  unavailable: "The Academy is unavailable right now. Please try again.",
  paused:
    "The school day is over. Lessons resume tomorrow; the exam rooms remain open.",
  staleNotes:
    "The notes for this room are not ready. Open the room again and ask once more.",
} as const;
