import { apiBase } from "./base";

// GET /v1/subjects, the backend contract in docs/api.md. The response supplies
// the published pack summaries and the live lesson/persona flags. The static
// subject list decides which departments are open/soon; this response does
// not override that product decision.
//
// The room must not wait for this call. Freshly loaded pages use the cached
// payload when there is one, and the venue opens on the static subject data
// after a short grace if the API is slow. A response that lands later still
// upgrades the lesson and persona flags.

export interface SubjectSummary {
  subject: string;
  title: string;
  tier: string;
  version: string;
  status: "draft" | "validated" | "published";
  built_at: string;
  fingerprint: string;
  topics: string[];
  concepts: number;
  materials: number;
}

export interface SubjectsPayload {
  subjects: SubjectSummary[];
  lesson: boolean;
  lesson_subject: string;
  lesson_subjects: string[];
  lesson_fallback: boolean;
  persona: boolean;
  persona_subject: string;
  persona_subjects: string[];
}

const SUBJECTS_TIMEOUT_MS = 5000;

const CACHE_KEY = "owl.subjects.v1";
// Pack and flag changes are rare, but a stale lesson flag would send
// `mode=lesson` to an API that has disabled it. A short cache still makes a
// venue-to-venue walk instant and limits the stale window to a minute.
const CACHE_TTL_MS = 60 * 1000;

interface CachedSubjects {
  saved_at: number;
  payload: SubjectsPayload;
}

function normalize(payload: Partial<SubjectsPayload>): SubjectsPayload {
  return {
    subjects: Array.isArray(payload.subjects) ? payload.subjects : [],
    lesson: Boolean(payload.lesson),
    lesson_subject:
      typeof payload.lesson_subject === "string" ? payload.lesson_subject : "",
    lesson_subjects: Array.isArray(payload.lesson_subjects)
      ? payload.lesson_subjects.filter(
          (item): item is string => typeof item === "string",
        )
      : [],
    lesson_fallback: payload.lesson_fallback !== false,
    persona: Boolean(payload.persona),
    persona_subject:
      typeof payload.persona_subject === "string" ? payload.persona_subject : "",
    persona_subjects: Array.isArray(payload.persona_subjects)
      ? payload.persona_subjects.filter(
          (item): item is string => typeof item === "string",
        )
      : [],
  };
}

export function readCachedSubjects(): SubjectsPayload | null {
  try {
    const raw = window.sessionStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<CachedSubjects>;
    if (
      typeof parsed.saved_at !== "number" ||
      parsed.saved_at > Date.now() ||
      Date.now() - parsed.saved_at > CACHE_TTL_MS ||
      parsed.payload === undefined
    ) {
      return null;
    }
    return normalize(parsed.payload);
  } catch {
    // A blocked or full store only loses the fast path.
    return null;
  }
}

function writeCachedSubjects(payload: SubjectsPayload): void {
  try {
    window.sessionStorage.setItem(
      CACHE_KEY,
      JSON.stringify({ saved_at: Date.now(), payload }),
    );
  } catch {
    // A blocked or full store only loses the fast path.
  }
}

export async function fetchSubjects(
  options: { timeoutMs?: number } = {},
): Promise<SubjectsPayload> {
  const controller = new AbortController();
  const timer = window.setTimeout(
    () => controller.abort(),
    options.timeoutMs ?? SUBJECTS_TIMEOUT_MS,
  );
  try {
    const response = await fetch(`${apiBase()}/v1/subjects`, {
      credentials: "include",
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error(`subjects request failed: ${response.status}`);
    }
    const payload = normalize(
      (await response.json()) as Partial<SubjectsPayload>,
    );
    writeCachedSubjects(payload);
    return payload;
  } finally {
    window.clearTimeout(timer);
  }
}
