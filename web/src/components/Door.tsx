import type { CSSProperties } from "react";
import { Link } from "react-router-dom";
import type { Subject } from "../data/subjects";
import { CrestInline } from "./Crest";

// A department door drawn in SVG so it stays theme-able with the subject
// accent, crisp at any size, and operable by keyboard as a plain link.
export function Door({ subject }: { subject: Subject }) {
  const closed = subject.status === "soon";
  return (
    <li className={`door-slot${closed ? " door-closed" : ""}`}>
      <Link
        to={`/venue/${subject.slug}`}
        className="door-link"
        style={{ "--accent": subject.accent } as CSSProperties}
        aria-label={
          closed
            ? `${subject.plaque} ${subject.name} — the department is not yet open`
            : subject.professor === "Professor not yet appointed"
              ? `Enter ${subject.plaque} ${subject.name}`
              : `Enter ${subject.plaque} ${subject.name}, taught by ${subject.professor}`
        }
      >
        <svg viewBox="0 0 120 200" className="door-art" aria-hidden="true">
          <path
            className="door-frame"
            d="M6 196 V58 Q6 10 60 4 Q114 10 114 58 V196 Z"
          />
          <path
            className="door-panel"
            d="M16 196 V60 Q16 18 60 12 Q104 18 104 60 V196 Z"
          />
          <line className="door-plank" x1="60" y1="14" x2="60" y2="196" />
          <CrestInline crest={subject.crest} />
          <rect className="door-plaque" x="38" y="150" width="44" height="26" rx="4" />
          <text className="door-plaque-text" x="60" y="168" textAnchor="middle">
            {subject.plaque}
          </text>
          <circle className="door-handle" cx="88" cy="128" r="5" />
          <circle className="door-handle" cx="32" cy="128" r="5" />
        </svg>{" "}
        <h2 className="door-name">{subject.name}</h2>
      </Link>
      <p className="door-status">
        {closed ? "Opens soon" : subject.professor}
      </p>
    </li>
  );
}
