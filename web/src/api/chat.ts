import { apiBase } from "./base";
import type { PersonaState } from "../data/subjects";

// Client for POST /v1/chat/stream, the SSE contract in docs/api.md. The server
// routes answer/practice/feedback itself, so the UI sends one question and
// reads the `mode` event to learn which route it took. Status copy
// addresses the professor as the addressee in every state; only the 503
// consults personaState before using professor wording (voice live or not).

export type ChatMode =
  | "answer"
  | "practice"
  | "feedback"
  | "meta"
  | "personal"
  | "lesson"
  | "fact"
  | "clarify"
  | "policy"
  | "abstain";

export type LessonScope = "in_pack" | "mixed" | "off_pack" | "abstained";

export interface EvidenceChunk {
  id: string;
  book: number;
  chapter: number;
  score: number;
  text: string;
}

export interface EvidenceReport {
  chunks: EvidenceChunk[];
  prompt_sha256: string;
  prompt_chars: number;
  attempts: number;
  model_calls: number;
  abstained: boolean;
  abstain_reason: string | null;
  retry_reason: string | null;
  scope: string | null;
  selected_material_ids: string[];
  selection_scores: Record<string, number>;
  uncovered_terms: string[];
  multi_book: boolean;
}

export interface FinalPayload {
  answer: string;
  citations: string[];
  lore_citations?: string[];
  material_citations?: string[];
  typed_citations?: string[];
  citation_errors?: string[];
  scope?: LessonScope | null;
  abstained: boolean;
  needs_input?: boolean;
  attempts?: number;
  mode?: ChatMode;
  thread_id?: string;
  evidence?: EvidenceReport | null;
}

export type StreamEvent =
  | { name: "mode"; data: { mode: ChatMode } }
  | { name: "token"; data: { text: string } }
  | { name: "reset"; data: { reason?: string } }
  | { name: "final"; data: FinalPayload }
  | { name: "error"; data: { detail: string } }
  | { name: string; data: unknown };

export class ChatError extends Error {}

// A request that never reaches the stream, or a stream that stops producing
// data events, must not leave the chat on an ellipsis forever. The server may
// take a few seconds to retrieve and start the first token; after that, a long
// gap means the edge or the model stalled. Keep-alive comments do not count as
// progress: sse-starlette pings every 15 s while the server is blocked.
const FIRST_RESPONSE_TIMEOUT_MS = 20_000;
const STREAM_IDLE_TIMEOUT_MS = 30_000;

export async function* askStream(
  question: string,
  personaState: PersonaState,
  subject: string,
  mode: "auto" | "lesson" = "auto",
  threadId?: string,
  studentName?: string | null,
): AsyncGenerator<StreamEvent> {
  const controller = new AbortController();
  const firstResponse = window.setTimeout(
    () => controller.abort(),
    FIRST_RESPONSE_TIMEOUT_MS,
  );
  let response: Response;
  try {
    response = await fetch(`${apiBase()}/v1/chat/stream`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        mode,
        subject,
        thread_id: threadId,
        // Only present once the welcome has a name; anonymous API callers
        // send the same body as before.
        ...(studentName ? { student_name: studentName } : {}),
      }),
      signal: controller.signal,
    });
  } catch {
    if (controller.signal.aborted) {
      throw new ChatError("The Academy did not answer in time. Please ask again.");
    }
    throw new ChatError("Could not reach the Academy. Is the server running?");
  } finally {
    window.clearTimeout(firstResponse);
  }
  if (!response.ok || !response.body) {
    throw new ChatError(await problemMessage(response, personaState));
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let idle: number | undefined;

  function armIdle(): void {
    if (idle !== undefined) window.clearTimeout(idle);
    idle = window.setTimeout(() => controller.abort(), STREAM_IDLE_TIMEOUT_MS);
  }

  function disarmIdle(): void {
    if (idle !== undefined) {
      window.clearTimeout(idle);
      idle = undefined;
    }
  }

  armIdle();
  try {
    while (true) {
      let chunk: ReadableStreamReadResult<Uint8Array>;
      try {
        chunk = await reader.read();
      } catch (error) {
        if (controller.signal.aborted) {
          throw new ChatError("The answer stalled. Please ask again.");
        }
        throw error;
      }
      if (chunk.done) break;
      buffer += decoder.decode(chunk.value, { stream: true });
      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = frames.pop() ?? "";
      for (const frame of frames) {
        let name = "message";
        let data = "";
        for (const line of frame.split(/\r?\n/)) {
          if (line.startsWith("event: ")) name = line.slice(7).trim();
          else if (line.startsWith("data: ")) data += line.slice(6);
        }
        if (!data) continue;
        let payload: unknown;
        try {
          payload = JSON.parse(data);
        } catch {
          continue;
        }
        // A comment or keep-alive frame carries no data and must not reset the
        // clock; only a real event proves the stream is alive.
        armIdle();
        yield { name, data: payload } as StreamEvent;
      }
    }
  } finally {
    disarmIdle();
  }
}

// Chat degrades before it can exhaust the daily budget (docs/api.md limits),
// so failures read as in-world status lines, never as bare status codes.
async function problemMessage(
  response: Response,
  personaState: PersonaState,
): Promise<string> {
  let problem: { error?: string; reason?: string; retry_after?: number; detail?: string };
  try {
    problem = await response.json();
  } catch {
    problem = {};
  }
  if (response.status === 429) {
    const wait = problem.retry_after ?? 60;
    return `Too many questions at once — the queue outside the office clears in ${wait} seconds.`;
  }
  if (response.status === 503) {
    const reason = problem.reason ? ` (${problem.reason})` : "";
    const quiet =
      personaState === "live" ? "The professor is resting" : "The study rooms are quiet";
    return `${quiet} tonight — chat is briefly paused for the day${reason}. The exam rooms are unaffected.`;
  }
  if (problem.error) return problem.error;
  if (problem.detail) return problem.detail;
  return "Something went wrong at the Academy. Please try again.";
}
