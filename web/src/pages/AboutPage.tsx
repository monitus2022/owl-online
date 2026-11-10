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
        <span aria-current="page">About the Academy</span>
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
          four departments have their own reviewed professor cards. All five
          departments are now open with published packs and exam banks.
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
          wizarding world hires against. For Aurors the record is precise:
          five N.E.W.T.s, nothing below Exceeds Expectations, a high
          standard in Defence specifically, and Transfiguration, Charms and
          Potions as the advised companions - canon leaves the fifth
          subject to the candidate. That Ashcombe teaches the advised set
          plus Herbology is the academy&rsquo;s own lore, not a claim from
          the books.
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
          The books describe O.W.L.s as theory papers plus, for applicable
          subjects, a separate practical, sat over roughly two weeks under
          external examiners. Ashcombe&rsquo;s practice papers are an
          adaptation, not that examination:
        </p>
        <ul>
          <li>ten questions per paper, one subject at a time;</li>
          <li>six multiple-choice questions at 3 marks and four short answers at
            8 marks, 50 marks in total;</li>
          <li>
            every question comes from that subject's published bank and cites
            the reviewed material and book passages behind it; each bank is
            authored offline, not generated in the exam room;
          </li>
          <li>
            the paper carries a suggested 60 minutes but keeps no clock: the
            student sets the pace. It is a practice paper, not the official
            examination, and counts for nothing.
          </li>
        </ul>
        <p>
          The server keeps the MCQ key, scores objective answers by code and
          sends the short answers to a pinned examiner model against the stored
          rubric. Totals and bands are computed deterministically. A result is
          a practice mark, not an official O.W.L. record.
        </p>
      </section>

      <section aria-labelledby="about-truth">
        <h2 id="about-truth">What is real, what is demonstration</h2>
        <table className="truth-table">
          <caption className="visually-hidden">
            Site surfaces, their status, and what each status means
          </caption>
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
                nothing supports an answer, the plain voice says it cannot
                answer from the books.
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
              <td className="truth-real">Real, practice</td>
              <td>
                The exam room serves a paper sampled from the subject's published
                bank. The server keeps the MCQ key, scores objective answers by
                code and sends the short answers to a pinned judge; totals and
                bands are deterministic. A result is practice, not an official
                O.W.L. record.
              </td>
            </tr>
            <tr>
              <td>Paper history and noticeboard</td>
              <td className="truth-demo">Session-scoped</td>
              <td>
                Records are kept on the server for this browser session
                (24 hours). Accounts (#35) will carry them across devices,
                and until then the UI labels them provisional.
              </td>
            </tr>
            <tr>
              <td>The professor&rsquo;s voice</td>
              <td className="truth-real">Live for the five cards</td>
              <td>
                Each of the five departments has a reviewed professor card.
                All five departments are open with published packs and
                exam banks. The API reports the live card and lesson subjects
                per room.
              </td>
            </tr>
            <tr>
              <td>No closed departments</td>
              <td className="truth-real">Live</td>
              <td>
                All five departments are open with published packs, exam banks
                and reviewed professor cards.
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
