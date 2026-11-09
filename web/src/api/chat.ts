import { apiBase } from "./base";
import type { PersonaState } from "../data/subjects";

// Client for POST /ask/stream, the SSE contract in docs/api.md. The server
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
  | "lesson";

export interface FinalPayload {
  answer: string;
  citations: string[];
  lore_citations?: string[];
  material_citations?: string[];
  abstained: boolean;
  needs_input?: boolean;
  attempts?: number;
  mode?: ChatMode;
}

export type StreamEvent =
  | { name: "mode"; data: { mode: ChatMode } }
  | { name: "token"; data: { text: string } }
  | { name: "reset"; data: { reason?: string } }
  | { name: "final"; data: FinalPayload }
  | { name: "error"; data: { detail: string } }
  | { name: string; data: unknown };

export class ChatError extends Error {}

export async function* askStream(
  question: string,
  personaState: PersonaState,
  mode: "auto" | "lesson" = "auto",
): AsyncGenerator<StreamEvent> {
  let response: Response;
  try {
    response = await fetch(`${apiBase()}/ask/stream`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, mode }),
    });
  } catch {
    throw new ChatError("Could not reach the Academy. Is the server running?");
  }
  if (!response.ok || !response.body) {
    throw new ChatError(await problemMessage(response, personaState));
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
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
      yield { name, data: payload } as StreamEvent;
    }
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
