import { Link } from "react-router-dom";

// The front gate. The facade is a stylised SVG — towers, gate arch, stars —
// so it themes, scales and prints without raster assets.
export function FrontPage() {
  return (
    <main className="front">
      <svg viewBox="0 0 640 320" className="facade" aria-hidden="true">
        <circle className="star" cx="80" cy="60" r="2" />
        <circle className="star" cx="160" cy="30" r="1.5" />
        <circle className="star" cx="260" cy="50" r="2" />
        <circle className="star" cx="380" cy="28" r="1.5" />
        <circle className="star" cx="500" cy="56" r="2" />
        <circle className="star" cx="580" cy="34" r="1.5" />
        <path
          className="facade-line"
          d="M40 300 V150 l18 -26 18 26 V120 l14 -20 14 20 v30 l18 -26 18 26 V300"
        />
        <path
          className="facade-line"
          d="M478 300 V150 l18 -26 18 26 V120 l14 -20 14 20 v30 l18 -26 18 26 V300"
        />
        <path
          className="facade-line"
          d="M180 300 V170 Q180 96 320 84 Q460 96 460 170 V300"
        />
        <path className="facade-line gate" d="M250 300 V205 Q250 150 320 142 Q390 150 390 205 V300" />
        <line className="facade-line" x1="320" y1="142" x2="320" y2="300" />
        <circle className="facade-line" cx="320" cy="60" r="10" />
        <path className="facade-line" d="M314 60 h12 M320 54 v12" />
      </svg>
      <p className="kicker">Est. 2008 · The Cotswolds</p>
      <h1 className="school-name">Ashcombe Academy of Magic</h1>
      <p className="school-tag">
        O.W.L. Online — the revision rooms. Ask questions, sit practice
        papers, and every answer cites the books.
      </p>
      <Link to="/cloister" className="btn-primary enter-btn">
        Enter the grounds
      </Link>
    </main>
  );
}
