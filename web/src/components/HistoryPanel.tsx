import { useEffect, useRef, useState } from "react";
import { BAND_LABELS } from "../api/exams";
import { resultsStore } from "../api/results";
import type { StoredAttempt } from "../api/results";
import { papersCopy } from "../copy";
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
      setClearError(papersCopy.history.deleteFailed);
    } finally {
      setClearing(false);
    }
  }

  return (
    <section className="history" aria-label="Your papers">
      <h2>{papersCopy.history.heading}</h2>
      <div className="notice notice-mock">{papersCopy.history.notice}</div>
      <div aria-live="polite">
        {failed && (
          <p className="history-empty">{papersCopy.history.failed}</p>
        )}
        {!failed && attempts === null && (
          <p className="history-empty">{papersCopy.history.loading}</p>
        )}
        {!failed && attempts !== null && attempts.length === 0 && (
          <p className="history-empty">
            {cleared > 0
              ? papersCopy.history.deleted(cleared)
              : papersCopy.history.empty}
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
                  {attempt.band ? BAND_LABELS[attempt.band] : papersCopy.history.kept}
                </span>
                <span className="history-marks">
                  {attempt.total === null
                    ? papersCopy.history.kept
                    : `${attempt.total}/${attempt.max}`}
                </span>
                {isBest(attempt) && (
                  <span className="history-best">{papersCopy.history.best}</span>
                )}
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
            {papersCopy.history.clear}
          </button>
        </div>
      )}
      {confirmClear && (
        <div className="history-confirm">
          <p role="alert">{papersCopy.history.clearConfirm}</p>
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
              {clearing
                ? papersCopy.history.deleting
                : papersCopy.history.delete}
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
              {papersCopy.history.keep}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
