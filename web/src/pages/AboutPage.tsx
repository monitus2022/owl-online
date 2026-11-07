import { Link } from "react-router-dom";

// The about page. Static by contract: no API calls, no invented facts.
// Every claim here traces to docs/persona.md (the school and the founders),
// docs/workplan.md (the canon anchors, the adapted paper format, the source
// policy) or docs/api.md (grounding and the honest-degradation behaviour).
// The canon-versus-adapted split stays visible, per the format-spec rule:
// the UI must never claim our papers are the exact papers from the books.

export function AboutPage() {
  return (
    <main className="about">
      <nav className="crumbs" aria-label="Breadcrumb">
        <Link to="/">The gate</Link>
        <span aria-hidden="true"> / </span>
        <span>About the Academy</span>
      </nav>
      <h1>About the Academy</h1>

      <section aria-labelledby="about-school">
        <h2 id="about-school">The school</h2>
        <p>
          Ashcombe Academy of Magic is a small wizarding school in the
          Cotswolds, founded in 2008 by five former Aurors who fought at the
          Battle of Hogwarts. There are no houses. There are five
          departments, one per founder: Defence Against the Dark Arts,
          Potions, Transfiguration, Charms and Herbology.
        </p>
        <p>
          Defence Against the Dark Arts is taught by Professor Alistair
          Crane, who fought at the Battle as a student and served about ten
          years in the Auror Office before co-founding the school. The other
          four departments open as their classrooms are furnished and their
          professors take the post.
        </p>
        <p>
          The academy, its founders and its professors are original
          creations of this study project, not characters from the books.
        </p>
      </section>

      <section aria-labelledby="about-letters">
        <h2 id="about-letters">The letters O to T</h2>
        <p>
          In the books, Ordinary Wizarding Level results are graded on a
          letter scale: Outstanding, Exceeds Expectations and Acceptable
          are passes; Poor, Dreadful and Troll are not. It is the scale the
          wizarding world hires against - the Auror Office asks for
          Exceeds Expectations or better in five subjects including
          Defence, Transfiguration, Charms, Potions and Herbology.
        </p>
        <p>
          This site borrows the scale. Your marks are banded against the
          same six letters so the revision feels like the real thing, and
          the pass line sits where the books put it.
        </p>
      </section>

      <section aria-labelledby="about-papers">
        <h2 id="about-papers">How our papers differ from the canon</h2>
        <p>
          The books describe O.W.L.s as theory papers plus a separate
          practical, sat over roughly two weeks under external examiners.
          Ashcombe&rsquo;s practice papers are an adaptation, not that
          examination:
        </p>
        <ul>
          <li>ten questions per paper, one subject at a time;</li>
          <li>multiple choice and short answer only;</li>
          <li>
            a practical section written as a simulation - incantation, wand
            movement, intended effect and counter-measure - because no
            website can watch you cast;
          </li>
          <li>
            no deadlines and no clock: the student sets the pace, and a
            paper is a revision tool, not a verdict.
          </li>
        </ul>
        <p>
          When the real exam bank ships, papers will be generated offline
          from validated subject materials - every question citing the book
          passages it came from, totals computed deterministically, and a
          separate examiner model for written work. Until then, the exam
          room runs on a demonstration bank and says so on every screen.
        </p>
      </section>

      <section aria-labelledby="about-truth">
        <h2 id="about-truth">What is real, what is demonstration</h2>
        <table className="truth-table">
          <thead>
            <tr>
              <th scope="col">Surface</th>
              <th scope="col">Status</th>
              <th scope="col">What that means</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Chat answers</td>
              <td className="truth-real">Real</td>
              <td>
                Retrieved from the seven novels and cited by chunk id; a
                citation that does not resolve is stripped, and when
                nothing supports an answer the system says it cannot
                confirm rather than guessing.
              </td>
            </tr>
            <tr>
              <td>Practice and feedback</td>
              <td className="truth-real">Real, formative</td>
              <td>
                The conversation asks and marks practice questions on the
                spot. They are grounded in the books but ephemeral: they
                are not bank questions and they count for nothing.
              </td>
            </tr>
            <tr>
              <td>Exam papers and marks</td>
              <td className="truth-demo">Demonstration</td>
              <td>
                A mock client runs a small original demo bank and grades
                on this device until the validated exam bank and the
                grading service ship.
              </td>
            </tr>
            <tr>
              <td>Paper history and noticeboard</td>
              <td className="truth-demo">Device-local</td>
              <td>
                Records live in this browser only. School accounts will
                move them to the Academy, and until then the UI labels
                them provisional.
              </td>
            </tr>
            <tr>
              <td>The professor&rsquo;s voice</td>
              <td className="truth-demo">In rehearsal</td>
              <td>
                Every room addresses the professor, and the answer you get
                today comes from the grounded engine in a plain voice. The
                persona layer is finished but not yet switched on at the
                served endpoint.
              </td>
            </tr>
            <tr>
              <td>Four closed departments</td>
              <td className="truth-not">Not built yet</td>
              <td>
                Potions, Transfiguration, Charms and Herbology open when
                their subject packs pass validation - a door is never half
                taught.
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <section aria-labelledby="about-sources">
        <h2 id="about-sources">Sources and the no-invention promise</h2>
        <p>
          Book facts come only from the seven novels, quoted as short
          passages with citation marks in the [b4-c25-0075] style: book,
          chapter, chunk. Setting facts about Ashcombe cite the
          academy&rsquo;s own lore pack. Secondary references - like The
          Harry Potter Lexicon, credited in the footer - are discovery and
          cross-checking aids, never the source of a fact, a question or a
          mark. The source text is copyrighted and is not distributed
          here; only original code, questions and metrics are published.
        </p>
        <p>
          If this page or any screen ever contradicts itself, trust the
          labelled state on that screen: demonstration means
          demonstration.
        </p>
      </section>
    </main>
  );
}
