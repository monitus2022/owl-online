import type { Band } from "../api/exams";
import { BAND_LABELS } from "../api/exams";

// The O–T seal. Bands are computed from marks by the grader's own
// deterministic rule; this component only renders the result.
export function BandSeal({ band, percentage }: { band: Band; percentage: number }) {
  return (
    <div className="seal" role="img" aria-label={`Grade: ${BAND_LABELS[band]}`}>
      <svg viewBox="0 0 96 96" aria-hidden="true">
        <circle className="seal-ring" cx="48" cy="48" r="44" />
        <circle className="seal-inner" cx="48" cy="48" r="34" />
        <text className="seal-letter" x="48" y="60" textAnchor="middle">
          {band}
        </text>
      </svg>
      <p className="seal-label">{BAND_LABELS[band]}</p>
      <p className="seal-percent">{Math.round(percentage * 100)}%</p>
    </div>
  );
}
