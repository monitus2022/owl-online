import { BAND_LABELS } from "../api/exams";
import type { StoredAttempt } from "../api/results";
import { papersCopy } from "../copy";

// Best-so-far card, read from the session-scoped store. The wording stays
// honest about the visit and the absence of accounts (#35) without breaking
// the room metaphor.
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
        {papersCopy.results.failed}
      </p>
    );
  }
  if (!best) {
    return (
      <p className="results-card results-empty">
        {papersCopy.results.empty}
      </p>
    );
  }
  if (best.band === null || best.total === null) {
    return (
      <p className="results-card results-empty">
        {papersCopy.results.keptBack}
      </p>
    );
  }
  const date = new Date(best.gradedAt);
  return (
    <p className="results-card">
      {papersCopy.results.bestPrefix}{" "}
      <strong>
        {BAND_LABELS[best.band]} ({best.total}/{best.max})
      </strong>{" "}
      — {date.toLocaleDateString()}
    </p>
  );
}
