import type { ReactNode } from "react";
import { Facade } from "./Facade";

// The academy front: facade, motto line, school name and the one-line promise.
// The first-run gate and the front page share it, so the building reads the
// same before and after the student is named; each supplies its own next step.
// `full` keeps the old full-size facade for the front page; the gate uses the
// smaller size so the ledger and its button stay above the fold.
export function AcademyFront({
  children,
  full = false,
}: {
  children: ReactNode;
  full?: boolean;
}) {
  return (
    <main className={full ? "gate gate-full" : "gate"}>
      <Facade className="gate-facade" />
      <p className="kicker">Est. 2008 · The Cotswolds</p>
      <h1 className="school-name">Ashcombe Academy of Magic</h1>
      <p className="gate-tag">
        The revision rooms. Ask a question, sit a practice paper, and every
        answer cites the books.
      </p>
      {children}
    </main>
  );
}
