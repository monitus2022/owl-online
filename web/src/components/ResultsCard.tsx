import { BAND_LABELS } from "../api/exams";
import type { StoredAttempt } from "../api/results";

// Best-so-far card, read from the session-scoped store. The wording stays
// honest about the browser session and the absence of accounts (#35).
export function ResultsCard({
  best,
  failed = false,
}: {
  best: StoredAttempt | null;
  failed?: boolean;
}) {
  if (failed) {
    return (
      <p className="results-card results-empty">
        The paper records could not be read right now.
      </p>
    );
  }
  if (!best) {
    return (
      <p className="results-card results-empty">
        No papers marked for this department in this browser session yet.
      </p>
    );
  }
  if (best.band === null || best.total === null) {
    return (
      <p className="results-card results-empty">
        A paper is waiting for examiner review.
      </p>
    );
  }
  const date = new Date(best.gradedAt);
  return (
    <p className="results-card">
      Best so far in this browser session:{" "}
      <strong>
        {BAND_LABELS[best.band]} ({best.total}/{best.max})
      </strong>{" "}
      — {date.toLocaleDateString()}
    </p>
  );
}
