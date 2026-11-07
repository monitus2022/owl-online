import { useEffect, useState } from "react";
import { BAND_LABELS } from "../api/exams";
import { resultsStore } from "../api/results";
import type { StoredAttempt } from "../api/results";
import type { Subject } from "../data/subjects";
import { BandStrip, bandTone } from "./BandStrip";

// Per-venue paper history, straight from the ResultsStore. Records are
// device-local and provisional until school accounts land (#35) - the copy
// must keep saying so, and an empty or unreadable store says so honestly.
export function HistoryPanel({ subject, active }: { subject: Subject; active: boolean }) {
  const [attempts, setAttempts] = useState<StoredAttempt[] | null>(null);

  useEffect(() => {
    if (!active) return;
    let live = true;
    resultsStore
      .history(subject.slug)
      .then((all) => {
        if (live) setAttempts(all);
      })
      .catch(() => {
        if (live) setAttempts([]);
      });
    return () => {
      live = false;
    };
  }, [active, subject.slug]);

  const bestKey =
    attempts && attempts.length > 0
      ? attempts.reduce((top, a) =>
          a.max > 0 && top.max > 0 && a.total * top.max > top.total * a.max ? a : top,
        )
      : null;

  return (
    <section className="history" aria-label="Your papers">
      <h2>Your papers</h2>
      <div className="notice notice-mock">
        Marks are recorded on this device only. School accounts (#35) will move
        this history to the Academy.
      </div>
      {attempts === null && <p className="history-empty">Fetching the records…</p>}
      {attempts && attempts.length === 0 && (
        <p className="history-empty">
          The drawer is empty: no papers have been marked for this department on
          this device yet. Sit one in the exam room.
        </p>
      )}
      {attempts && attempts.length > 0 && (
        <>
          <BandStrip attempts={attempts} />
          <ol className="history-list">
            {attempts.map((attempt, index) => {
              const sameAsBest =
                bestKey &&
                attempt.id === bestKey.id &&
                attempt.gradedAt === bestKey.gradedAt;
              return (
                <li key={attempt.id + attempt.gradedAt} className="history-row">
                  <span className="history-index">{attempts.length - index}</span>
                  <span className="history-date">
                    {new Date(attempt.gradedAt).toLocaleDateString()}
                  </span>
                  <span className={`band-chip cell-${bandTone(attempt.band)}`}>
                    {BAND_LABELS[attempt.band]}
                  </span>
                  <span className="history-marks">
                    {attempt.total}/{attempt.max}
                  </span>
                  {sameAsBest && <span className="history-best">best</span>}
                </li>
              );
            })}
          </ol>
        </>
      )}
    </section>
  );
}
