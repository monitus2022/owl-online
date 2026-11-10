import { Link } from "react-router-dom";

// The privacy note (#180). Static by contract: no API calls. The full policy
// is docs/privacy.md; this page states the user-facing facts and the choices
// that exist before accounts (#35).

export function PrivacyPage() {
  return (
    <main className="about">
      <nav className="crumbs" aria-label="Breadcrumb">
        <Link to="/">The gate</Link>
        <span aria-hidden="true"> / </span>
        <span aria-current="page">Privacy</span>
      </nav>
      <h1>Privacy and retention</h1>

      <section aria-labelledby="privacy-stored">
        <h2 id="privacy-stored">What is stored</h2>
        <ul>
          <li>
            Chat is ephemeral. The transcript lives in your browser tab; the
            API does not persist it as a chat record. Corpus-only answers are
            cached in process memory for up to an hour; the cache clears on
            restart and has no per-session key.
          </li>
          <li>
            Usage logs record the session id, intent, model, cache flag, token
            counts, cost and latency. They do not record the prompt or answer
            text.
          </li>
          <li>
            Traces record the request id, span names, timings, counts, cited
            retrieved chunk and lore ids, and a prompt hash with its length. They do not
            record the prompt or answer text.
          </li>
          <li>
            Exam attempts record the paper, the questions you saw, your
            answers, the grade and the session id in the local SQLite store.
            Graded attempts appear under "Your papers".
          </li>
        </ul>
      </section>

      <section aria-labelledby="privacy-retention">
        <h2 id="privacy-retention">How long it is kept</h2>
        <ul>
          <li>
            The session cookie lasts 24 hours. After it expires the browser is
            issued a new session id; old attempts remain until they are deleted
            or pruned.
          </li>
          <li>
            Attempts are kept until you delete them or the operator prunes them
            with the documented retention script. The default manual window is
            90 days.
          </li>
          <li>
            Traces are process logs with a size cap and one rotated file;
            usage logs follow the host log rotation. They contain no prompt or
            answer text.
          </li>
        </ul>
      </section>

      <section aria-labelledby="privacy-providers">
        <h2 id="privacy-providers">Model providers</h2>
        <p>
          Prompts and the retrieved excerpts go to the configured provider:
          OpenRouter for open-weight models, or Amazon Bedrock in the deployed
          region. The project does not train models on your data. The provider
          processes the request under its own terms, so check that policy if
          you need a formal guarantee.
        </p>
      </section>

      <section aria-labelledby="privacy-cookies">
        <h2 id="privacy-cookies">Cookies and requests</h2>
        <p>
          The only cookie is <code>owl_session</code>: a signed, HttpOnly
          session id used for rate limits and to keep your attempts private to
          your session. It is SameSite=None with Secure on HTTPS so the Pages
          frontend can call the API; there are no analytics or advertising
          cookies.
        </p>
      </section>

      <section aria-labelledby="privacy-choices">
        <h2 id="privacy-choices">Your choices</h2>
        <ul>
          <li>
            Export: <code>GET /v1/attempts</code> returns the graded attempts
            for the current session.
          </li>
          <li>
            Delete: <code>DELETE /v1/attempts</code> deletes the current
            session's attempts. It does not clear the in-memory answer cache or
            the operator-managed judge cache. Clearing cookies starts a new
            session; the old attempts remain until the operator prunes them.
          </li>
          <li>
            Accounts, cross-device history and a per-user delete/export path
            wait on auth (#35).
          </li>
        </ul>
      </section>

      <p>
        The full policy, including the cookie/CORS/CSRF review, is in{" "}
        <code>docs/privacy.md</code> in the project repository.
      </p>
    </main>
  );
}
