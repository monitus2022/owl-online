import { useEffect, useRef, useState } from "react";
import { BAND_LABELS } from "../api/exams";
import { resultsStore } from "../api/results";
import type { StoredAttempt } from "../api/results";
import type { Subject } from "../data/subjects";
import { BandStrip, bandTone } from "./BandStrip";

// Per-venue paper history, straight from the session-scoped ResultsStore. The
// best mark is read from the store's own best(), never recomputed here, so this
// surface cannot disagree with the noticeboard or the store.

export function HistoryPanel({ subject, active }: { subject: Subject; active: boolean }) {
  const [attempts, setAttempts] = useState<StoredAttempt[] | null>(null);
  const [best, setBest] = useState<StoredAttempt | null>(null);
  const [failed, setFailed] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [clearError, setClearError] = useState<string | null>(null);
  const [cleared, setCleared] = useState(0);
  const clearRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!active) return;
    let live = true;
    setFailed(false);
    Promise.all([
      resultsStore.history(subject.apiSubject),
      resultsStore.best(subject.apiSubject),
    ])
      .then(([all, top]) => {
        if (live) {
          setAttempts(all);
          setBest(top);
        }
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, [active, subject.apiSubject]);

  const isBest = (attempt: StoredAttempt): boolean =>
    best !== null &&
    attempt.band !== null &&
    best.band !== null &&
    attempt.total !== null &&
    best.total !== null &&
    attempt.id === best.id &&
    attempt.gradedAt === best.gradedAt;

  async function clearAll() {
    setClearing(true);
    setClearError(null);
    try {
      const deleted = await resultsStore.clear();
      setAttempts([]);
      setBest(null);
      setCleared(deleted);
      setConfirmClear(false);
    } catch {
      setClearError(
        "The papers could not be deleted. They are still stored for this session.",
      );
    } finally {
      setClearing(false);
    }
  }

  return (
    <section className="history" aria-label="Your papers">
      <h2>Your papers</h2>
      <div className="notice notice-mock">
        Practice marks, kept for this browser session. School accounts
        (#35) will move this history to the Academy.
      </div>
      <div aria-live="polite">
        {failed && (
          <p className="history-empty">
            The paper records for this browser session could not be read.
            Nothing is lost by trying again; if it keeps failing, the drawer
            stays shut.
          </p>
        )}
        {!failed && attempts === null && (
          <p className="history-empty">Fetching the records…</p>
        )}
        {!failed && attempts !== null && attempts.length === 0 && (
          <p className="history-empty">
            {cleared > 0
              ? `Deleted ${cleared} paper${cleared === 1 ? "" : "s"}. The drawer is empty.`
              : "The drawer is empty: no papers have been marked for this department in this browser session yet. Sit one in the exam room."}
          </p>
        )}
      </div>
      {!failed && attempts && attempts.length > 0 && (
        <>
          <BandStrip attempts={attempts} />
          <ol className="history-list" role="list">
            {attempts.map((attempt, index) => (
              <li
                key={`${attempt.id}:${attempt.gradedAt}`}
                className="history-row"
              >
                <span className="history-index">{attempts.length - index}</span>
                <span className="history-date">{new Date(attempt.gradedAt).toLocaleDateString()}</span>
                <span className={`band-chip ${attempt.band ? `cell-${bandTone(attempt.band)}` : "band-none"}`}>
                  {attempt.band ? BAND_LABELS[attempt.band] : "review"}
                </span>
                <span className="history-marks">
                  {attempt.total === null ? "review" : `${attempt.total}/${attempt.max}`}
                </span>
                {isBest(attempt) && <span className="history-best">best</span>}
              </li>
            ))}
          </ol>
        </>
      )}
      {!failed && attempts !== null && (
        <div className="history-actions">
          <button
            className="btn-quiet"
            type="button"
            ref={clearRef}
            onClick={() => {
              setClearError(null);
              setConfirmClear(true);
            }}
          >
            Clear all papers
          </button>
        </div>
      )}
      {confirmClear && (
        <div className="history-confirm">
          <p role="alert">
            Delete every paper in this browser session, including any ungraded
            paper? This cannot be undone.
          </p>
          {clearError && (
            <p className="history-error" role="alert">
              {clearError}
            </p>
          )}
          <div className="history-actions">
            <button
              className="btn-primary"
              type="button"
              onClick={() => void clearAll()}
              disabled={clearing}
            >
              {clearing ? "Deleting…" : "Delete them"}
            </button>
            <button
              className="btn-quiet"
              type="button"
              onClick={() => {
                setConfirmClear(false);
                setClearError(null);
                clearRef.current?.focus();
              }}
              disabled={clearing}
            >
              Keep them
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
