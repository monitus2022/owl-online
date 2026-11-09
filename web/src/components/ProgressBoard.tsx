import type { CSSProperties } from "react";
import { BAND_LABELS } from "../api/exams";
import type { StoredAttempt } from "../api/results";
import { SUBJECTS } from "../data/subjects";
import { bandTone } from "./BandStrip";

// A department's best is null when the drawer is genuinely empty and
// undefined when it could not be read; the two get different copy.
type BestState = StoredAttempt | null | undefined;

// The cloister noticeboard: best band per department, read from the same
// device-local store as the venue history. Empty states are honest and in
// the room metaphor: a closed door, an unfurnished classroom, or a best
// mark once papers have been sat.
export function ProgressBoard({
  bests,
  loading,
}: {
  bests: Record<string, BestState>;
  loading: boolean;
}) {
  return (
    <section className="progress" aria-label="Department noticeboard">
      <h2>The noticeboard</h2>
      <div className="notice notice-mock">
        Practice marks recorded on this device only until school
        accounts arrive (#35).
      </div>
      <ul className="progress-grid" role="list" aria-live="polite">
        {SUBJECTS.map((subject) => {
          const best = bests[subject.slug];
          let state: string;
          if (loading) {
            state = "checking the records…";
          } else if (best === undefined) {
            state = "the records could not be read";
          } else if (best) {
            state = `best: ${BAND_LABELS[best.band]} (${best.total}/${best.max})`;
          } else if (subject.status === "open") {
            state = "the room is furnished, no papers sat yet";
          } else {
            state = "the door is closed";
          }
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
