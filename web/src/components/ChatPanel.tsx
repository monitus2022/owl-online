import { useRef, useState } from "react";
import type { FormEvent } from "react";
import { askStream, ChatError } from "../api/chat";
import type { ChatMode, EvidenceReport, LessonScope } from "../api/chat";
import {
  abstainNote,
  chatCopy,
  chatGreeting,
  modeLabel,
  scopeNote,
} from "../copy";
import { startersFor } from "../data/subjects";
import type { Subject } from "../data/subjects";
import { stripCitationMarkers } from "../data/sources";
import { useStudentName } from "../data/student";
import { EvidenceInspector } from "./EvidenceInspector";
import { Silhouette } from "./Silhouette";
import { SourcePanel } from "./SourcePanel";

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
  retry?: string;
  evidence?: EvidenceReport;
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
  const studentName = useStudentName();
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

  async function send(raw: string, retryId?: number) {
    const text = raw.trim();
    if (text === "" || busy || !ready) return;
    setQuestion("");
    setBusy(true);

    let professorId: number;
    if (retryId !== undefined) {
      // Reuse the failed turn so the transcript shows one question and the
      // answer streams back into the same bubble. A request that already
      // reached the server may still appear once more in thread memory; this
      // is a UI retry, not an idempotent request.
      professorId = retryId;
      updateProfessor(professorId, () => ({
        id: professorId,
        role: "professor",
        text: "",
        retry: text,
      }));
    } else {
      const studentId = nextId.current++;
      professorId = nextId.current++;
      setMessages((current) => [
        ...current,
        { id: studentId, role: "student", text },
        { id: professorId, role: "professor", text: "", retry: text },
      ]);
    }

    let sawFinal = false;
    let sawError = false;
    try {
      for await (const streamEvent of askStream(
        text,
        subject.personaState,
        subject.apiSubject,
        lesson ? "lesson" : "auto",
        threadId,
        studentName,
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
          sawFinal = true;
          const data = streamEvent.data as {
            answer: string;
            citations?: string[];
            lore_citations?: string[];
            material_citations?: string[];
            typed_citations?: string[];
            scope?: LessonScope | null;
            abstained: boolean;
            mode?: ChatMode;
            evidence?: EvidenceReport | null;
          };
          const chips = [
            ...(data.citations ?? []),
            ...(data.lore_citations ?? []).map((id) => `lore:${id}`),
          ];
          const answer = typeof data.answer === "string" ? data.answer : "";
          const empty = answer.trim() === "";
          updateProfessor(professorId, (draft) => ({
            ...draft,
            text: empty
              ? data.abstained
                ? ""
                : "The Academy returned an empty answer. Please ask again."
              : answer,
            materials: data.material_citations ?? [],
            citations: chips,
            typedCitations: data.typed_citations ?? [],
            scope: data.scope ?? undefined,
            abstained: data.abstained,
            mode: data.mode ?? draft.mode,
            failed: empty && !data.abstained,
            evidence: import.meta.env.DEV
              ? (data.evidence ?? undefined)
              : undefined,
          }));
        } else if (streamEvent.name === "error" && !sawFinal) {
          sawError = true;
          const data = streamEvent.data as { detail?: unknown };
          const detail =
            typeof data.detail === "string"
              ? data.detail
              : "The professor's answer failed. Please try again.";
          updateProfessor(professorId, (draft) => ({
            ...draft,
            text: detail,
            failed: true,
          }));
        }
      }
      if (!sawFinal && !sawError) {
        // A clean close without a final event is a failed turn, not a finished
        // one: the placeholder must not survive the stream.
        updateProfessor(professorId, (draft) => ({
          ...draft,
          text:
            draft.text === ""
              ? "The Academy closed the answer early. Please ask again."
              : `${draft.text}\nThe Academy closed the answer early. Please ask again.`,
          failed: true,
        }));
      }
    } catch (error) {
      // A late read error after the final event does not invalidate a complete
      // answer, and a handled error event is already on screen.
      if (sawFinal || sawError) return;
      const detail =
        error instanceof ChatError
          ? error.message
          : "The connection to the Academy was lost mid-answer.";
      updateProfessor(professorId, (draft) => ({
        ...draft,
        text: draft.text === "" ? detail : `${draft.text}\n${detail}`,
        failed: true,
        retry:
          error instanceof ChatError && !error.retryable
            ? undefined
            : draft.retry,
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
              ? chatGreeting(subject, lesson, lessonFallback, vacant)
              : message.text;
          const modeIsLesson =
            message.mode === "lesson" ||
            (message.mode === "abstain" && message.scope === "abstained");
          const scope = message.scope ? scopeNote(message.scope) : null;
          // The model still emits its inline citation brackets; the verified
          // ids live in the payload and the Sources row, so the prose drops
          // the machine markers. Student text is never rewritten.
          const displayText =
            message.role === "professor"
              ? stripCitationMarkers(bodyText)
              : bodyText;
          const body = (
            <>
              {message.role === "professor" && message.mode && (
                <span className="mode-badge">{modeLabel(message.mode, subject.personaState)}</span>
              )}
              {modeIsLesson && scope && (
                <p className="scope-note">{scope}</p>
              )}
              <p
                className={message.failed ? "chat-text chat-failed" : "chat-text"}
                role={message.failed ? "alert" : undefined}
              >
                {displayText ||
                  (message.role === "professor"
                    ? message.abstained
                      ? ""
                      : "…"
                    : "")}
              </p>
              {message.failed &&
                message.retry &&
                index === messages.length - 1 && (
                  <button
                    type="button"
                    className="btn-quiet chat-retry"
                    onClick={() => void send(message.retry ?? "", message.id)}
                    disabled={busy || !ready}
                    aria-label={`${chatCopy.retry}: ${
                      message.retry.length > 60
                        ? `${message.retry.slice(0, 60)}…`
                        : message.retry
                    }`}
                  >
                    {chatCopy.retry}
                  </button>
                )}
              {message.role === "professor" && (
                <SourcePanel
                  subject={subject.apiSubject}
                  materials={message.materials}
                  citations={message.citations}
                  typedCitations={message.typedCitations}
                />
              )}
              {import.meta.env.DEV && message.evidence && (
                <EvidenceInspector evidence={message.evidence} />
              )}
              {message.abstained && (
                <p className="abstain-note">
                  {abstainNote(
                    subject.personaState,
                    modeIsLesson,
                    lessonFallback,
                  )}
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
              ? chatCopy.placeholder.preparing
              : vacant
                ? chatCopy.placeholder.vacant
                : chatCopy.placeholder.ready
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
          {busy ? chatCopy.thinking : chatCopy.ask}
        </button>
      </form>
    </section>
  );
}
