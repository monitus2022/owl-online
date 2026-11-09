import type { Band } from "../api/exams";
import type { StoredAttempt } from "../api/results";

// Presentation tone per O-W-L band. The canon grants exactly two tiers -
// O/E/A pass, P/D/T fail (docs/workplan.md, HBP5) - so the colour split does
// too. T stays distinct from P/D through its label, not a softer colour.
const BAND_TONES: Record<Band, "pass" | "fail"> = {
  O: "pass",
  E: "pass",
  A: "pass",
  P: "fail",
  D: "fail",
  T: "fail",
};

export function bandTone(band: Band): "pass" | "fail" {
  return BAND_TONES[band];
}

function formatDay(attempt: StoredAttempt): string {
  return new Date(attempt.gradedAt).toLocaleDateString();
}

// The last results as a strip of band cells, newest first. Each cell's
// marks and date are real text for assistive tech (the letter alone is
// decorative); the list role is restored because list-style removal drops it
// in Safari/VoiceOver.
export function BandStrip({ attempts }: { attempts: StoredAttempt[] }) {
  const resolved = attempts.filter(
    (attempt): attempt is StoredAttempt & { band: Band; total: number } =>
      !attempt.needsReview && attempt.band !== null && attempt.total !== null,
  );
  if (resolved.length === 0) return null;
  const shown = resolved.slice(0, 12);
  return (
    <ol
      className="band-strip"
      role="list"
      aria-label={`Last ${shown.length} of ${resolved.length} papers, newest first`}
    >
      {shown.map((attempt) => (
        <li
          key={`${attempt.id}:${attempt.gradedAt}`}
          className={`band-cell cell-${bandTone(attempt.band)}`}
        >
          <span aria-hidden="true">{attempt.band}</span>
          <span className="visually-hidden">
            {attempt.total} of {attempt.max} on {formatDay(attempt)}
          </span>
        </li>
      ))}
    </ol>
  );
}
