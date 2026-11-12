import { useRef, useState } from "react";
import type { FormEvent } from "react";
import { askStream, ChatError } from "../api/chat";
import type { ChatMode, LessonScope } from "../api/chat";
import { startersFor } from "../data/subjects";
import type { PersonaState, Subject } from "../data/subjects";
import { Silhouette } from "./Silhouette";

// Chat. Every affordance addresses the professor; the greeting, abstention
// note and status copy follow the department's personaState. Each venue keeps
// one anonymous thread in sessionStorage, so the API can resolve a follow-up
// against earlier turns; requests without a thread stay stateless. Model
// output is rendered as plain text only — never HTML — per the project rule.

interface Message {
  id: number;
  role: "student" | "professor";
  text: string;
  mode?: ChatMode;
  citations?: string[];
  typedCitations?: string[];
  materials?: string[];
  scope?: LessonScope;
  abstained?: boolean;
  failed?: boolean;
}

const THREAD_ID = /^[A-Za-z0-9_-]{8,64}$/;

function readThread(key: string): string | null {
  try {
    const existing = window.sessionStorage.getItem(key);
    return existing && THREAD_ID.test(existing) ? existing : null;
  } catch {
    return null;
  }
}

function writeThread(key: string, id: string): void {
  try {
    window.sessionStorage.setItem(key, id);
  } catch {
    // A blocked or full store still leaves the in-memory id usable.
  }
}

function newThreadId(): string {
  return typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `thread-${Date.now()}-${Math.random().toString(36).slice(2)}`;
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
  policy: "Office note",
  abstain: "Office note",
};

// The server emits meta, personal, fact, policy and abstain only when
// OWL_PERSONA is on. The badge reads "Professor" when the venue's API-derived
// persona state is live; the static subject value is only the fallback when
// /v1/subjects is unreachable.
function modeLabel(mode: ChatMode, personaState: PersonaState): string {
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
  const [threadId] = useState(() => {
    // One anonymous thread per venue in this tab. A reload keeps it in
    // sessionStorage; closing the tab starts a new thread.
    const key = `owl-thread-${subject.apiSubject}`;
    const id = readThread(key) ?? newThreadId();
    writeThread(key, id);
    return id;
  });

  function updateProfessor(id: number, patch: (draft: Message) => Message) {
    setMessages((current) =>
      current.map((message) => (message.id === id ? patch(message) : message)),
    );
  }

  async function send(raw: string) {
    const text = raw.trim();
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
        threadId,
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
            typed_citations?: string[];
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
            typedCitations: data.typed_citations ?? [],
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

  async function submit(event: FormEvent) {
    event.preventDefault();
    await send(question);
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
          const modeIsLesson =
            message.mode === "lesson" ||
            (message.mode === "abstain" && message.scope === "abstained");
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
              {message.typedCitations && message.typedCitations.length > 0 ? (
                <div className="citation-group">
                  <span className="citation-label">Citations</span>
                  <ul className="citation-chips">
                    {message.typedCitations.map((citation) => (
                      <li key={citation}>{citation}</li>
                    ))}
                  </ul>
                </div>
              ) : (
                message.citations &&
                message.citations.length > 0 && (
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
                )
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
      {messages.length === 1 && !vacant && (
        <div className="starter-chips" role="group" aria-label="Example questions">
          {startersFor(subject).map((prompt) => (
            <button
              key={prompt}
              type="button"
              className="starter-chip"
              disabled={busy || !ready}
              onClick={() => void send(prompt)}
            >
              {prompt}
            </button>
          ))}
        </div>
      )}
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
