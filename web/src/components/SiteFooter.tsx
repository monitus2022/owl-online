// The shared footer: rights and attribution, on every page, at the document
// level beside the routed pages. The wording mirrors the project's source
// policy (docs/workplan.md): the wizarding world belongs to its creator and
// publishers, this project distributes no source text, and secondary
// references such as the Lexicon are attributed links, never copied prose.
import { Link } from "react-router-dom";
export function SiteFooter() {
  return (
    <footer className="site-footer">
      <p>
        The Harry Potter works, their characters, spells and institutions, are
        the creation of J.K. Rowling and are copyright of their respective
        rights holders. Ashcombe Academy is an original, non-commercial fan
        study project about the seven novels: it is not affiliated with or
        endorsed by the rights holders, it distributes no source text, and its
        academy, professors and papers are original creations.
      </p>
      <p>
        With thanks to{" "}
        <a
          href="https://www.hp-lexicon.org"
          target="_blank"
          rel="noopener noreferrer"
        >
          The Harry Potter Lexicon
        </a>{" "}
        (opens in a new tab), used as a discovery and cross-checking aid with
        attribution; it is not the source of this project&rsquo;s canon or of
        any exam content.
      </p>
      <p className="footer-nav">
        <Link to="/about">About the Academy</Link>
        <span aria-hidden="true"> / </span>
        <Link to="/privacy">Privacy and retention</Link>
      </p>
    </footer>
  );
}
