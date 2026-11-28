import type { CSSProperties } from "react";
import { BAND_LABELS } from "../api/exams";
import type { StoredAttempt } from "../api/results";
import { papersCopy } from "../copy";
import { SUBJECTS } from "../data/subjects";
import { bandTone } from "./BandStrip";

// A department's best is null when the drawer is genuinely empty and
// undefined when it could not be read; the two get different copy.
type BestState = StoredAttempt | null | undefined;

// The cloister noticeboard: best band per department, read from the same
// session-scoped store as the venue history. Empty states are honest and in
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
      <h2>{papersCopy.progress.heading}</h2>
      <div className="notice notice-mock">{papersCopy.progress.notice}</div>
      <ul className="progress-grid" role="list" aria-live="polite">
        {SUBJECTS.map((subject) => {
          const best = bests[subject.slug];
          let state: string;
          if (loading) {
            state = papersCopy.progress.checking;
          } else if (best === undefined) {
            state = papersCopy.progress.unreadable;
          } else if (best) {
            state =
              best.band && best.total !== null
                ? papersCopy.progress.best(
                    BAND_LABELS[best.band],
                    best.total,
                    best.max,
                  )
                : papersCopy.progress.keptBack;
          } else if (subject.status === "open") {
            state = papersCopy.progress.furnished;
          } else {
            state = papersCopy.progress.closed;
          }
          return (
            <li
              key={subject.slug}
              className="progress-row"
              style={{ "--accent": subject.accent } as CSSProperties}
            >
              <span
                className={
                  best && best.band
                    ? `band-chip cell-${bandTone(best.band)}`
                    : "band-chip band-none"
                }
                aria-hidden="true"
              >
                {best && best.band ? best.band : "—"}
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
