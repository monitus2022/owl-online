import { Link } from "react-router-dom";
import { SiteFooter } from "../components/SiteFooter";
import { Door } from "../components/Door";
import { SUBJECTS } from "../data/subjects";

// The cloister: one door per department. Departments open as their subject
// packs and professors land, so the closed doors are honest placeholders,
// not half-built pages.
export function CloisterPage() {
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
      <ul className="door-row">
        {SUBJECTS.map((subject) => (
          <Door key={subject.slug} subject={subject} />
        ))}
      </ul>
      <SiteFooter />
    </main>
  );
}
