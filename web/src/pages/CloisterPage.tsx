import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { resultsStore } from "../api/results";
import type { StoredAttempt } from "../api/results";
import { Door } from "../components/Door";
import { ProgressBoard } from "../components/ProgressBoard";
import { SUBJECTS } from "../data/subjects";

// The cloister: one door per department, and the noticeboard below with the
// device-local best mark for each. Departments open as their subject packs
// and professors land, so the closed doors are honest placeholders, not
// half-built pages.
export function CloisterPage() {
  const [bests, setBests] = useState<Record<string, StoredAttempt | null | undefined>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let live = true;
    Promise.all(
      SUBJECTS.map(async (subject) => {
        try {
          return [subject.slug, await resultsStore.best(subject.slug)] as const;
        } catch {
          // undefined = unreadable drawer for this department, distinct from
          // null = genuinely no records; the board words them differently.
          return [subject.slug, undefined] as const;
        }
      }),
    ).then((entries) => {
      if (live) {
        setBests(Object.fromEntries(entries));
        setLoading(false);
      }
    });
    return () => {
      live = false;
    };
  }, []);

  return (
    <main className="cloister">
      <nav className="crumbs" aria-label="Breadcrumb">
        <Link to="/">The gate</Link>
        <span aria-hidden="true"> / </span>
        <span>The cloister</span>
      </nav>
      <h1>The Cloister</h1>
      <p className="section-lead">
        Five departments, one per founder. Each door leads to that
        department&rsquo;s classroom.
      </p>
      <ul className="door-row" role="list">
        {SUBJECTS.map((subject) => (
          <Door key={subject.slug} subject={subject} />
        ))}
      </ul>
      <ProgressBoard bests={bests} loading={loading} />
    </main>
  );
}
