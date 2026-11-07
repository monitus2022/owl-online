import { Link } from "react-router-dom";

// The catch-all. An unmatched address is just the end of the corridor: no
// error theatrics, no invented rooms - a way back and nothing else.
export function NotFoundPage() {
  return (
    <main className="notfound">
      <h1>The corridor ends here</h1>
      <p>
        There is no room at this address. The gate, the cloister and the about
        page all lead back to ground you know.
      </p>
      <ul className="notfound-links">
        <li>
          <Link to="/">The gate</Link>
        </li>
        <li>
          <Link to="/cloister">The cloister</Link>
        </li>
        <li>
          <Link to="/about">About the Academy</Link>
        </li>
      </ul>
    </main>
  );
}
