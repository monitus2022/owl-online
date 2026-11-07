import type { Band } from "./exams";

// Result records. Until auth (#35) and the server-side attempt store exist,
// records live in localStorage and are provisional: the UI labels them as
// such and must not present them as an official history. The interface is
// deliberately async so an HttpResultsStore can replace it without touching
// the components.

export interface StoredAttempt {
  id: string;
  subject: string;
  paperId: string;
  total: number;
  max: number;
  band: Band;
  gradedAt: string;
}

export interface ResultsStore {
  save(attempt: StoredAttempt): Promise<void>;
  history(subject: string): Promise<StoredAttempt[]>;
  best(subject: string): Promise<StoredAttempt | null>;
}

const KEY = "owl.reco…y.v1";

function readAll(): StoredAttempt[] {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as StoredAttempt[]) : [];
  } catch {
    return [];
  }
}

class LocalStorageResultsStore implements ResultsStore {
  async save(attempt: StoredAttempt): Promise<void> {
    const all = readAll();
    all.push(attempt);
    try {
      localStorage.setItem(KEY, JSON.stringify(all));
    } catch {
      // Device-local records are best-effort: quota or private mode must
      // not break the flow that produced them.
    }
  }

  async history(subject: string): Promise<StoredAttempt[]> {
    return readAll()
      .filter((attempt) => attempt.subject === subject)
      .sort((a, b) => b.gradedAt.localeCompare(a.gradedAt));
  }

  async best(subject: string): Promise<StoredAttempt | null> {
    const attempts = await this.history(subject);
    if (attempts.length === 0) return null;
    return attempts.reduce((top, attempt) =>
      attempt.total * top.max > top.total * attempt.max ? attempt : top,
    );
  }
}

export const resultsStore: ResultsStore = new LocalStorageResultsStore();
