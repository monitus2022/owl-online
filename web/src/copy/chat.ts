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
    return `Welcome to the ${subject.name} revision room. Answers come from the department's notes, and nothing beyond them is guessed. No professor has been appointed to this department yet.`;
  }
  if (lesson) {
    const outside = lessonFallback
      ? "If a question falls outside them, I will answer from the reference books and tell you when I have done so."
      : "If a question falls outside the notes, I will say so rather than guess.";
    return subject.personaState === "live"
      ? `Welcome to the ${subject.name} revision room. I teach from the department's own notes; ask about the set topics, or say the word if you want to be tested. ${outside}`
      : `Welcome to the ${subject.name} revision room. I can answer from the department's notes. ${outside}`;
  }
  return subject.personaState === "live"
    ? `Welcome to the ${subject.name} revision room. Ask ${subject.professor} about the reference books, or say the word if you want to be tested.`
    : "Welcome to the revision room. Ask the professor about the reference books. Every answer will show the passages it rests on, and nothing beyond them is guessed.";
}

export function scopeNote(scope: LessonScope): string | null {
  if (scope === "in_pack") {
    return "I have drawn this from the department's notes. The passages below show where it comes from; they are a guide to the sources, not a check of every sentence.";
  }
  if (scope === "mixed") {
    return "I have drawn part of this from the department's notes and part from the reference books. The passages below show where it comes from; they are a guide to the sources, not a check of every sentence.";
  }
  if (scope === "off_pack") {
    return "From the reference books";
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
        ? "The professor could not find this in the department's notes or the reference books, so he will not guess."
        : "The professor could not find this in the department's notes, so he will not guess.";
    }
    return "The professor could not find this in the reference books, so he will not guess.";
  }
  if (lesson) {
    return lessonFallback
      ? "The department's notes and the reference books could not confirm this, and nothing is guessed."
      : "The department's notes could not confirm this, and nothing is guessed.";
  }
  return "The reference books could not confirm this, and nothing is guessed.";
}

export const chatCopy = {
  placeholder: {
    preparing: "Preparing the room…",
    vacant: "Ask about the reference books…",
    ready: "Ask the professor…",
  },
  ask: "Ask",
  thinking: "Thinking…",
  retry: sharedCopy.retry,
} as const;
