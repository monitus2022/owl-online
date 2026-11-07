import { BAND_LABELS } from "../api/exams";
import type { StoredAttempt } from "../api/results";

// Best-so-far card. Local and provisional until the server keeps attempt
// history (auth is #35); the wording must stay honest about that.
export function ResultsCard({ best }: { best: StoredAttempt | null }) {
  if (!best) {
    return (
      <p className="results-card results-empty">
        No papers marked for this department on this device yet.
      </p>
    );
  }
  const date = new Date(best.gradedAt);
  return (
    <p className="results-card">
      Best so far on this device:{" "}
      <strong>
        {BAND_LABELS[best.band]} ({best.total}/{best.max})
      </strong>{" "}
      — {date.toLocaleDateString()}
    </p>
  );
}
