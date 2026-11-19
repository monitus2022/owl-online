import { useId, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { AcademyFront } from "../components/AcademyFront";
import { parseStudentName, setStudentName } from "../data/student";

// The first-run gate, delivered by the Keeper of the Records. The facade, the
// school name and the one-line promise come first, so a new visitor sees what
// the academy is before being asked for anything; the name form sits inside
// that poster as the Keeper's ledger. The copy is static: no model call, no
// persona card and no conversation with the Keeper. `/about` and `/privacy`
// stay reachable from here so the notice can be read first.
export function WelcomePage() {
  const [raw, setRaw] = useState("");
  const [error, setError] = useState<string | null>(null);
  const fieldId = useId();
  const hintId = `${fieldId}-hint`;
  const errorId = `${fieldId}-error`;
  const keeperId = `${fieldId}-keeper`;

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const parsed = parseStudentName(raw);
    if (!parsed.ok) {
      setError(parsed.error);
      return;
    }
    // Storing the name unlocks the routes; the current URL is kept, so a deep
    // link opens the intended page once the ledger has the name.
    setStudentName(parsed.name);
  }

  return (
    <AcademyFront>
      <section className="porch" aria-labelledby={keeperId}>
        <p className="ledger-rule" aria-hidden="true">
          <span>Ledger of new readers</span>
          <span>No. 001</span>
        </p>
        <div className="porch-head">
          <span className="keeper-seal" aria-hidden="true">
            K
          </span>
          <div>
            <h2 className="porch-title" id={keeperId}>
              The Keeper of the Records
            </h2>
            <p className="porch-line">
              “The ledger needs a name before the professors can greet you
              properly.”
            </p>
          </div>
        </div>
        <form className="porch-form" onSubmit={onSubmit} noValidate>
          <label htmlFor={fieldId}>Your name</label>
          <input
            id={fieldId}
            name="student-name"
            type="text"
            autoComplete="given-name"
            autoFocus
            maxLength={40}
            placeholder="e.g. Mira"
            value={raw}
            aria-invalid={error !== null}
            aria-describedby={error ? `${hintId} ${errorId}` : hintId}
            onChange={(event) => {
              setRaw(event.target.value);
              if (error) setError(null);
            }}
          />
          <p className="porch-hint" id={hintId}>
            A first name is enough. It stays in this browser, never in a
            student record.
          </p>
          {error && (
            <p className="porch-error" id={errorId} role="alert">
              {error}
            </p>
          )}
          <button className="btn-primary" type="submit">
            Enter the grounds
          </button>
        </form>
      </section>
      <p className="gate-note">
        Not ready to be known? Read{" "}
        <Link to="/about">about the Academy</Link> or the{" "}
        <Link to="/privacy">privacy note</Link>.
      </p>
    </AcademyFront>
  );
}
