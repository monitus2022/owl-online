import { useId, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { parseStudentName, setStudentName } from "../data/student";

// The first-run welcome, delivered by the Keeper of the Records. It is static
// copy: no model call, no persona card and no conversation with the Keeper.
// The name is required to pass; the intro screen is not. `/about` and
// `/privacy` stay reachable from here so the notice can be read first.
export function WelcomePage() {
  const [raw, setRaw] = useState("");
  const [error, setError] = useState<string | null>(null);
  const fieldId = useId();
  const hintId = `${fieldId}-hint`;
  const errorId = `${fieldId}-error`;

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
    <main className="welcome">
      <p className="kicker">Ashcombe Academy · The Keeper of the Records</p>
      <h1>Welcome to the Academy</h1>
      <div className="welcome-copy">
        <p>
          I keep the roll, the papers and the quiet of the library, and I am the
          first door every student passes through. The professors will meet you
          in their own rooms soon enough; before they can greet you properly,
          the ledger needs a name.
        </p>
        <p>
          Write the name you would like to be called — a first name is enough —
          and the professors will use it when they answer. It is kept only in
          this browser, never in a student record, and you can change it later
          from the foot of the page.
        </p>
      </div>
      <form className="welcome-form" onSubmit={onSubmit} noValidate>
        <label htmlFor={fieldId}>Your name</label>
        <p className="welcome-hint" id={hintId}>
          First name or the name you answer to, up to 40 characters.
        </p>
        <input
          id={fieldId}
          name="student-name"
          type="text"
          autoComplete="given-name"
          autoFocus
          maxLength={40}
          value={raw}
          aria-invalid={error !== null}
          aria-describedby={error ? `${hintId} ${errorId}` : hintId}
          onChange={(event) => {
            setRaw(event.target.value);
            if (error) setError(null);
          }}
        />
        {error && (
          <p className="welcome-error" id={errorId} role="alert">
            {error}
          </p>
        )}
        <button className="btn-primary" type="submit">
          Enter the Academy
        </button>
      </form>
      <p className="welcome-note">
        Not ready to be known yet? Read{" "}
        <Link to="/about">about the Academy</Link> or the{" "}
        <Link to="/privacy">privacy note</Link> first.
      </p>
    </main>
  );
}
