import { useRef, useState } from "react";
import type { FormEvent } from "react";
import { askStream, ChatError } from "../api/chat";
import type { ChatMode, LessonScope } from "../api/chat";
import type { PersonaState, Subject } from "../data/subjects";
import { Silhouette } from "./Silhouette";

// Chat. Every affordance addresses the professor; the greeting, abstention
// note and status copy follow the department's personaState. The transcript
// is session-local: the API is stateless until threads land (#30), so
// earlier turns are context for the reader, not sent to the model. Model
// output is rendered as plain text only — never HTML — per the project rule.

interface Message {
  id: number;
  role: "student" | "professor";
  text: string;
  mode?: ChatMode;
  citations?: string[];
  materials?: string[];
  scope?: LessonScope;
  abstained?: boolean;
  failed?: boolean;
}

const MODE_LABELS: Record<ChatMode, string> = {
  answer: "Answer",
  practice: "Practice",
  feedback: "Feedback",
  meta: "Office note",
  personal: "Office note",
  lesson: "Lesson",
  fact: "Office note",
  clarify: "Office note",
};

// The server emits meta and personal only when OWL_PERSONA is on. The badge
// reads "Professor" when the venue's API-derived persona state is live; the
// static subject value is only the fallback when /v1/subjects is unreachable.
function modeLabel(mode: ChatMode, personaState: PersonaState): string {
  if (
    (mode === "meta" || mode === "personal" || mode === "fact") &&
    personaState === "live"
  ) {
    return "Professor";
  }
  return MODE_LABELS[mode];
}

function welcome(
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

export function ChatPanel({
  subject,
  lesson,
  lessonFallback,
  ready,
}: {
  subject: Subject;
  lesson: boolean;
  lessonFallback: boolean;
  ready: boolean;
}) {
  const vacant = subject.professor === "Professor not yet appointed";
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 0,
      role: "professor",
      text: "",
    },
  ]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const nextId = useRef(1);

  function updateProfessor(id: number, patch: (draft: Message) => Message) {
    setMessages((current) =>
      current.map((message) => (message.id === id ? patch(message) : message)),
    );
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (text === "" || busy || !ready) return;
    setQuestion("");
    setBusy(true);

    const studentId = nextId.current++;
    const professorId = nextId.current++;
    setMessages((current) => [
      ...current,
      { id: studentId, role: "student", text },
      { id: professorId, role: "professor", text: "" },
    ]);

    try {
      for await (const streamEvent of askStream(
        text,
        subject.personaState,
        subject.apiSubject,
        lesson ? "lesson" : "auto",
      )) {
        if (streamEvent.name === "mode") {
          const data = streamEvent.data as { mode: ChatMode };
          updateProfessor(professorId, (draft) => ({ ...draft, mode: data.mode }));
        } else if (streamEvent.name === "token") {
          const data = streamEvent.data as { text: string };
          updateProfessor(professorId, (draft) => ({
            ...draft,
            text: draft.text + data.text,
          }));
        } else if (streamEvent.name === "reset") {
          updateProfessor(professorId, (draft) => ({ ...draft, text: "" }));
        } else if (streamEvent.name === "final") {
          const data = streamEvent.data as {
            answer: string;
            citations?: string[];
            lore_citations?: string[];
            material_citations?: string[];
            scope?: LessonScope | null;
            abstained: boolean;
            mode?: ChatMode;
          };
          const chips = [
            ...(data.citations ?? []),
            ...(data.lore_citations ?? []).map((id) => `lore:${id}`),
          ];
          updateProfessor(professorId, (draft) => ({
            ...draft,
            text: data.answer,
            materials: data.material_citations ?? [],
            citations: chips,
            scope: data.scope ?? undefined,
            abstained: data.abstained,
            mode: data.mode ?? draft.mode,
          }));
        } else if (streamEvent.name === "error") {
          const data = streamEvent.data as { detail: string };
          updateProfessor(professorId, (draft) => ({
            ...draft,
            text: data.detail,
            failed: true,
          }));
        }
      }
    } catch (error) {
      const detail =
        error instanceof ChatError
          ? error.message
          : "The connection to the Academy was lost mid-answer.";
      updateProfessor(professorId, (draft) => ({
        ...draft,
        text: draft.text === "" ? detail : `${draft.text}\n${detail}`,
        failed: true,
      }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      className="chat"
      aria-label={vacant ? "Chat with the department" : "Chat with the professor"}
    >
      <ol className="chat-log">
        {messages.map((message, index) => {
          const thinking =
            busy && index === messages.length - 1 && message.role === "professor";
          // The first turn is the room greeting: derive it at render time so
          // the API's persona/lesson flags, which arrive after mount, are
          // reflected without rewriting transcript state.
          const bodyText =
            message.id === 0
              ? welcome(subject, lesson, lessonFallback, vacant)
              : message.text;
          const modeIsLesson = message.mode === "lesson";
          const body = (
            <>
              {message.role === "professor" && message.mode && (
                <span className="mode-badge">{modeLabel(message.mode, subject.personaState)}</span>
              )}
              {modeIsLesson &&
                (message.scope === "mixed" || message.scope === "off_pack") && (
                  <p className="scope-note">
                    {message.scope === "mixed"
                      ? "Department notes and set texts"
                      : "Set texts"}
                  </p>
                )}
              <p className={message.failed ? "chat-text chat-failed" : "chat-text"}>
                {bodyText || (message.role === "professor" ? "…" : "")}
              </p>
              {message.materials && message.materials.length > 0 && (
                <div className="citation-group">
                  <span className="citation-label">Lesson notes</span>
                  <ul className="citation-chips">
                    {message.materials.map((material) => (
                      <li key={material}>{material}</li>
                    ))}
                  </ul>
                </div>
              )}
              {message.citations && message.citations.length > 0 && (
                <div className="citation-group">
                  {message.materials && message.materials.length > 0 && (
                    <span className="citation-label">Set texts</span>
                  )}
                  <ul className="citation-chips">
                    {message.citations.map((citation) => (
                      <li key={citation}>{citation}</li>
                    ))}
                  </ul>
                </div>
              )}
              {message.abstained && (
                <p className="abstain-note">
                  {subject.personaState === "live"
                    ? modeIsLesson
                      ? lessonFallback
                        ? "The professor could not ground this in the department's notes or the set texts, so he will not guess."
                        : "The professor could not ground this in the department's notes, so he will not guess."
                      : "The professor could not ground this in the texts, so he will not guess."
                    : modeIsLesson
                      ? lessonFallback
                        ? "The reviewed notes and the set texts could not confirm this, and nothing is guessed."
                        : "The reviewed notes could not confirm this, and nothing is guessed."
                      : "The texts could not confirm this, and nothing is guessed."}
                </p>
              )}
            </>
          );
          return (
            <li key={message.id} className={`chat-turn chat-${message.role}`}>
              {message.role === "professor" ? (
                <div className="professor-line">
                  <Silhouette
                    variant={subject.professorVariant}
                    thinking={thinking}
                  />
                  <div className="turn-body">{body}</div>
                </div>
              ) : (
                body
              )}
            </li>
          );
        })}
      </ol>
      <form className="chat-form" onSubmit={submit}>
        <input
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder={
            !ready
              ? "Preparing the room…"
              : vacant
                ? "Ask about the set texts…"
                : "Ask the professor…"
          }
          maxLength={1000}
          autoComplete="off"
          disabled={busy || !ready}
          aria-label="Your question"
        />
        <button
          type="submit"
          disabled={busy || !ready || question.trim() === ""}
        >
          {busy ? "Thinking…" : "Ask"}
        </button>
      </form>
    </section>
  );
}
