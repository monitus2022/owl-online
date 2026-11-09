import { apiBase } from "./base";
import type { Band } from "./exams";

// Result records are session-scoped on the server (#206). The browser sends the
// signed owl_session cookie with credentials: "include"; the API returns only
// this session's graded attempts. Local storage is deliberately not used: the
// server already persists the grade, and a second browser must not inherit it.

export interface StoredAttempt {
  id: string;
  subject: string;
  paperId: string;
  total: number | null;
  max: number;
  band: Band | null;
  gradedAt: string;
  needsReview: boolean;
}

export interface ResultsStore {
  save(attempt: StoredAttempt): Promise<void>;
  history(subject: string): Promise<StoredAttempt[]>;
  best(subject: string): Promise<StoredAttempt | null>;
}

interface ApiAttemptSummary {
  attempt_id: string;
  paper_id: string;
  subject: string;
  version: string;
  created_at: string;
  graded_at: string;
  total: number | null;
  max_marks: number;
  band: Band | null;
  needs_review: boolean;
}

function isResolved(
  attempt: StoredAttempt,
): attempt is StoredAttempt & { total: number; band: Band } {
  return (
    !attempt.needsReview && attempt.total !== null && attempt.band !== null
  );
}

class HttpResultsStore implements ResultsStore {
  async save(_attempt: StoredAttempt): Promise<void> {
    // The server writes the grade when the attempt is submitted. The
    // interface keeps save() so a future offline store can still implement it.
  }

  async history(subject: string): Promise<StoredAttempt[]> {
    let response: Response;
    try {
      response = await fetch(
        `${apiBase()}/v1/attempts?subject=${encodeURIComponent(subject)}`,
        { credentials: "include" },
      );
    } catch {
      throw new Error("The paper records could not be reached.");
    }
    if (!response.ok) {
      throw new Error(`The paper records could not be read (${response.status}).`);
    }
    const attempts = (await response.json()) as ApiAttemptSummary[];
    return attempts.map((attempt) => ({
      id: attempt.attempt_id,
      subject: attempt.subject,
      paperId: attempt.paper_id,
      total: attempt.total,
      max: attempt.max_marks,
      band: attempt.band,
      gradedAt: attempt.graded_at,
      needsReview: attempt.needs_review,
    }));
  }

  async best(subject: string): Promise<StoredAttempt | null> {
    const attempts = await this.history(subject);
    const resolved = attempts.filter(isResolved);
    if (resolved.length === 0) return null;
    return resolved.reduce((top, attempt) =>
      attempt.total * top.max > top.total * attempt.max ? attempt : top,
    );
  }
}

export const resultsStore: ResultsStore = new HttpResultsStore();
