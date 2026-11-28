import type { ChatMode, LessonScope } from "../api/chat";
import type { PersonaState, Subject } from "../data/subjects";
import { sharedCopy } from "./shared";

// Student-facing room copy. The professor's scripted replies live in the
// persona cards; this file owns the shared chat chrome around them.

const MODE_LABELS: Record<ChatMode, string> = {
  answer: "Answer",
  practice: "Practice",
  feedback: "Feedback",
  meta: "Office note",
  personal: "Office note",
  lesson: "Lesson",
  fact: "Office note",
  clarify: "Office note",
  policy: "Office note",
  abstain: "Office note",
};

// The server emits meta, personal, fact, policy and abstain only when
// OWL_PERSONA is on. The badge reads "Professor" when the venue's API-derived
// persona state is live; the static subject value is only the fallback when
// /v1/subjects is unreachable.
export function modeLabel(
  mode: ChatMode,
  personaState: PersonaState,
): string {
  if (
    (mode === "meta" ||
      mode === "personal" ||
      mode === "fact" ||
      mode === "policy" ||
      mode === "abstain") &&
    personaState === "live"
  ) {
    return "Professor";
  }
  return MODE_LABELS[mode];
}

export function chatGreeting(
  subject: Subject,
  lesson: boolean,
  lessonFallback: boolean,
  vacant: boolean,
): string {
  if (vacant) {
    return `Welcome to the ${subject.name} revision room. Answers come from the department's reviewed notes, and nothing beyond them is guessed. No professor has been appointed for this department yet.`;
  }
  if (lesson) {
    const outside = lessonFallback
      ? "Questions outside the notes are answered from the set texts and labelled."
      : "Questions outside the notes are refused honestly.";
    return subject.personaState === "live"
      ? `Welcome to the ${subject.name} revision room. I teach from the department's reviewed notes; ask about the set topics, or say the word if you want to be tested. ${outside}`
      : `Welcome to the ${subject.name} revision room. Answers come from the department's reviewed notes. ${outside} The professor's voice is still in rehearsal.`;
  }
  return subject.personaState === "live"
    ? `Welcome to the ${subject.name} revision room. Ask ${subject.professor} about the set texts, or say the word if you want to be tested.`
    : "Welcome to the revision room. Ask the professor about the set texts — grounded answers cite the books, and nothing beyond them is guessed. The professor's voice is still in rehearsal.";
}

export function scopeNote(scope: LessonScope): string | null {
  if (scope === "in_pack") {
    return "Composed from the department notes. The sources below list the reviewed notes and the book passages they come from; they are not a sentence-level check.";
  }
  if (scope === "mixed") {
    return "Composed from the department notes and the set texts. The sources below are not a sentence-level check.";
  }
  if (scope === "off_pack") {
    return "Set texts";
  }
  return null;
}

export function abstainNote(
  personaState: PersonaState,
  lesson: boolean,
  lessonFallback: boolean,
): string {
  if (personaState === "live") {
    if (lesson) {
      return lessonFallback
        ? "The professor could not ground this in the department's notes or the set texts, so he will not guess."
        : "The professor could not ground this in the department's notes, so he will not guess.";
    }
    return "The professor could not ground this in the texts, so he will not guess.";
  }
  if (lesson) {
    return lessonFallback
      ? "The reviewed notes and the set texts could not confirm this, and nothing is guessed."
      : "The reviewed notes could not confirm this, and nothing is guessed.";
  }
  return "The texts could not confirm this, and nothing is guessed.";
}

export const chatCopy = {
  placeholder: {
    preparing: "Preparing the room…",
    vacant: "Ask about the set texts…",
    ready: "Ask the professor…",
  },
  ask: "Ask",
  thinking: "Thinking…",
  retry: sharedCopy.retry,
} as const;
