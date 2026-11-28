// Student-facing chat failure lines. The API clients keep the status logic;
// this file owns the words.

export const chatErrorCopy = {
  timeout: "The Academy did not answer in time. Please ask again.",
  unreachable: "Could not reach the Academy. Is the server running?",
  generic: "Something went wrong at the Academy. Please try again.",
  stalled: "The answer stalled. Please ask again.",
  rateLimited: (wait: number): string =>
    `Too many questions at once — the queue outside the office clears in ${wait} seconds.`,
  unavailable: "The Academy is unavailable right now. Please try again.",
  paused: (quiet: string, reason: string | null): string =>
    `${quiet} tonight — chat is briefly paused for the day${
      reason ? ` (${reason})` : ""
    }. The exam rooms are unaffected.`,
  quietProfessor: "The professor is resting",
  quietRooms: "The study rooms are quiet",
  staleNotes:
    "The teaching notes are no longer loaded for this room. Reload the room and ask again.",
} as const;
