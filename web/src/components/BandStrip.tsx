import type { Band } from "../api/exams";
import type { StoredAttempt } from "../api/results";

// Presentation tone per O-W-L band: pass (O/E/A), warn (P/D), fail (T).
// The canonical grading rule itself is deterministic and lives server-side
// when #41 lands; this is only colour mapping.
export function bandTone(band: Band): "pass" | "warn" | "fail" {
  if (band === "O" || band === "E" || band === "A") return "pass";
  if (band === "T") return "fail";
  return "warn";
}

// The last results as a strip of band cells, newest first. Decorative-adjacent
// but readable: each cell carries the marks and date as its accessible name.
export function BandStrip({ attempts }: { attempts: StoredAttempt[] }) {
  if (attempts.length === 0) return null;
  const shown = attempts.slice(0, 12);
  return (
    <ol className="band-strip" aria-label="Last papers, newest first">
      {shown.map((attempt) => (
        <li
          key={attempt.id + attempt.gradedAt}
          className={`band-cell cell-${bandTone(attempt.band)}`}
          title={`${attempt.total}/${attempt.max} - ${new Date(attempt.gradedAt).toLocaleDateString()}`}
          aria-label={`${attempt.total} of ${attempt.max} on ${new Date(attempt.gradedAt).toLocaleDateString()}, band ${attempt.band}`}
        >
          {attempt.band}
        </li>
      ))}
    </ol>
  );
}
