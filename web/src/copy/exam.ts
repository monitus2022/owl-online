// Student-facing exam room and returned-paper copy.

// The rubric ids are internal shape, not student-facing words.
const CRITERION_LABELS: Record<string, string> = {
  correctness: "Facts and accuracy",
  completeness: "Coverage and explanation",
};

export function criterionLabel(id: string): string {
  return CRITERION_LABELS[id] ?? id.replace(/[_-]+/g, " ");
}

export const examCopy = {
  idleNotice: (subject: string): string =>
    `A practice paper from the ${subject} department. There is no clock and no expiry: take as long as you need. The result is provisional and is not an official O.W.L. record.`,
  takePaper: "Take a paper",
  anotherPaper: "Another paper",
  backToRoom: "Back to the room",
  gradingNotice:
    "The professor is at the desk with your parchment. The quick questions are checked straight away; the written answers are read against the department's marking notes.",
  gradingNote: "The professor will return your parchment in a few seconds.",
  returned: "Paper returned",
  keptNotice:
    "The department has kept some answers back. This copy carries no final band.",
  keptTotal: "Kept back — no final total",
  practiceNotice:
    "Practice result. The marks and band are the department's; the expected answer and the professor's note are returned with your parchment.",
  marks: (marks: number, max: number): string => `${marks}/${max}`,
  questionMarks: (marks: number): string => `[${marks} marks]`,
  keptMark: "kept",
  needsReview:
    "The department has kept this answer back; this copy carries no final band.",
  noteLabel: "The professor's note:",
  expected: "The expected answer",
  correct: "The correct answer",
  paperMeta: (
    questions: number,
    marks: number,
    timed: boolean,
    minutes: number,
  ): string =>
    `${questions} questions · ${marks} marks · ${
      timed ? `suggested ${minutes} minutes` : "untimed practice"
    }`,
  untimedNote:
    "This is an untimed practice paper; you can finish it whenever you are ready.",
  progress: (answered: number, total: number): string =>
    `${answered} of ${total} answered`,
  blankWarning: (blank: number): string =>
    `${blank} question${blank === 1 ? "" : "s"} left blank. Send the paper anyway?`,
  send: "Send to the examiners",
  sendAnyway: "Send anyway",
  keepWorking: "Keep working",
  abandon: "Abandon paper",
  paperNotLoaded: "The paper could not be loaded.",
  abandonFailed:
    "The paper could not be discarded. You can clear it from Your papers.",
  errors: {
    paperGone: "This paper is no longer available. Start a new one.",
    dailyLimit:
      "You have sat as many papers as the department allows today. Come back tomorrow.",
    examinersAway:
      "The examiners are not at their desk right now. Try again later.",
    unreachable: "The exam room could not reach the examiners. Try again.",
  },
} as const;
