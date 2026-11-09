import { apiBase } from "./base";

// GET /v1/subjects, the backend contract in docs/api.md. The response owns
// availability (which packs are published) and the two live flags; the static
// subject list in src/data/ keeps the presentation metadata (professor,
// accent, crest, blurb) because those are not API data.

export interface SubjectSummary {
  subject: string;
  title: string;
  tier: string;
  version: string;
  status: string;
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
  persona: boolean;
}

export async function fetchSubjects(): Promise<SubjectsPayload> {
  const response = await fetch(`${apiBase()}/v1/subjects`, {
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(`subjects request failed: ${response.status}`);
  }
  const payload = (await response.json()) as Partial<SubjectsPayload>;
  return {
    subjects: Array.isArray(payload.subjects) ? payload.subjects : [],
    lesson: Boolean(payload.lesson),
    lesson_subject:
      typeof payload.lesson_subject === "string" ? payload.lesson_subject : "",
    persona: Boolean(payload.persona),
  };
}
