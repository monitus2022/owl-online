import { useRef, useState } from "react";
import type { FormEvent } from "react";
import { askStream, ChatError } from "../api/chat";
import type { ChatMode } from "../api/chat";
import type { Subject } from "../data/subjects";
import { Silhouette } from "./Silhouette";

// Chat with the professor. The transcript is session-local: the API is
// stateless until threads land (#30), so earlier turns are context for the
// reader, not sent to the model. Model output is rendered as plain text only —
// never HTML — per the project rule.

interface Message {
  id: number;
  role: "student" | "professor";
  text: string;
  mode?: ChatMode;
  citations?: string[];
  abstained?: boolean;
  failed?: boolean;
}

const MODE_LABELS: Record<ChatMode, string> = {
  answer: "Answer",
  practice: "Practice",
  feedback: "Feedback",
  meta: "Professor",
  personal: "Professor",
};

export function ChatPanel({ subject }: { subject: Subject }) {
  const responder = subject.personaState === "live" ? "the professor" : "the owl";
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 0,
      role: "professor",
      text:
        subject.personaState === "live"
          ? `Welcome to the ${subject.name} revision room. Ask ${subject.professor} about the set texts, or say the word if you want to be tested.`
          : `Welcome to the revision room. Ask about the set texts - grounded answers cite the books, and if the owl cannot confirm something it will say so plainly. The department's professor voice is still in rehearsal.`,
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
    if (text === "" || busy) return;
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
      for await (const streamEvent of askStream(text)) {
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
            citations: string[];
            lore_citations?: string[];
            abstained: boolean;
            mode?: ChatMode;
          };
          const chips = [
            ...data.citations,
            ...(data.lore_citations ?? []).map((id) => `lore:${id}`),
          ];
          updateProfessor(professorId, (draft) => ({
            ...draft,
            text: data.answer,
            citations: chips,
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
    <section className="chat" aria-label={`Chat with ${responder}`}>
      <ol className="chat-log">
        {messages.map((message, index) => {
          const thinking =
            busy && index === messages.length - 1 && message.role === "professor";
          const body = (
            <>
              {message.role === "professor" && message.mode && (
                <span className="mode-badge">{MODE_LABELS[message.mode]}</span>
              )}
              <p className={message.failed ? "chat-text chat-failed" : "chat-text"}>
                {message.text || (message.role === "professor" ? "…" : "")}
              </p>
              {message.citations && message.citations.length > 0 && (
                <ul className="citation-chips">
                  {message.citations.map((citation) => (
                    <li key={citation}>{citation}</li>
                  ))}
                </ul>
              )}
              {message.abstained && (
                <p className="abstain-note">
                  {subject.personaState === "live"
                    ? "The professor could not ground this in the texts, so he will not guess."
                    : "The owl could not ground this in the books, and will not guess."}
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
          placeholder={`Ask ${responder}…`}
          maxLength={1000}
          autoComplete="off"
          disabled={busy}
          aria-label="Your question"
        />
        <button type="submit" disabled={busy || question.trim() === ""}>
          {busy ? "Thinking…" : "Ask"}
        </button>
      </form>
    </section>
  );
}
