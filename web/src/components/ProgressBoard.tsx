import type { CSSProperties } from "react";
import { BAND_LABELS } from "../api/exams";
import type { StoredAttempt } from "../api/results";
import { SUBJECTS } from "../data/subjects";
import { bandTone } from "./BandStrip";

// The cloister noticeboard: best band per department, read from the same
// device-local store as the venue history. Empty states are honest and in
// the room metaphor: a closed door, an unfurnished classroom, or a best
// mark once papers have been sat.
export function ProgressBoard({
  bests,
  loading,
}: {
  bests: Record<string, StoredAttempt | null>;
  loading: boolean;
}) {
  return (
    <section className="progress" aria-label="Department noticeboard">
      <h2>The noticeboard</h2>
      <div className="notice notice-mock">
        Marks are recorded on this device only until school accounts arrive (#35).
      </div>
      <ul className="progress-grid">
        {SUBJECTS.map((subject) => {
          const best = bests[subject.slug];
          const state = loading
            ? "checking the records…"
            : best
              ? `best: ${BAND_LABELS[best.band]} (${best.total}/${best.max})`
              : subject.status === "open"
                ? "the room is furnished, no papers sat yet"
                : "the door is closed";
          return (
            <li
              key={subject.slug}
              className="progress-row"
              style={{ "--accent": subject.accent } as CSSProperties}
            >
              <span
                className={
                  best
                    ? `band-chip cell-${bandTone(best.band)}`
                    : "band-chip band-none"
                }
                aria-hidden="true"
              >
                {best ? best.band : "—"}
              </span>
              <span className="progress-name">{subject.name}</span>
              <span className="progress-state">{state}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
