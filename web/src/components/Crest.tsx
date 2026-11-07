import type { CrestName } from "../data/subjects";

// Departmental emblems. Pure geometry - shield, flask, butterfly, spark
// star, seedling - drawn in currentColor so the subject accent themes them
// from CSS. Decorative by definition: hidden from the a11y tree by callers.

const STROKE = { fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round" } as const;

function Motif({ crest }: { crest: CrestName }) {
  switch (crest) {
    case "shield":
      return (
        <g>
          <path d="M24 9 L37 14 V25 Q37 35 24 40 Q11 35 11 25 V14 Z" {...STROKE} />
          <line x1="17" y1="32" x2="30" y2="17" {...STROKE} strokeWidth={2.4} />
          <circle cx="30.5" cy="16.5" r="1.8" fill="currentColor" stroke="none" />
        </g>
      );
    case "flask":
      return (
        <g>
          <path d="M21 12 H27 M22.5 12 V21 L15.5 31 Q13 35 16 37.5 Q18.5 40 24 40 Q29.5 40 32 37.5 Q35 35 32.5 31 L25.5 21 V12" {...STROKE} />
          <path d="M17.6 30 Q24 33.5 30.4 30 L32 32.4 Q29.5 38 24 38 Q18.5 38 16 32.4 Z" fill="currentColor" opacity="0.4" stroke="none" />
          <circle cx="22" cy="34.5" r="1.2" fill="currentColor" stroke="none" />
        </g>
      );
    case "butterfly":
      return (
        <g>
          <line x1="24" y1="17" x2="24" y2="35" {...STROKE} strokeWidth={2.4} />
          <path d="M23 20 Q11 8 8.5 17 Q7 25 22 27 Z" {...STROKE} />
          <path d="M25 20 Q37 8 39.5 17 Q41 25 26 27 Z" {...STROKE} />
          <path d="M23 28 Q12 30 13 36 Q14 40 23 33 Z" {...STROKE} />
          <path d="M25 28 Q36 30 35 36 Q34 40 25 33 Z" {...STROKE} />
          <path d="M22 16 Q20 12 17 11 M26 16 Q28 12 31 11" {...STROKE} strokeWidth={1.4} />
        </g>
      );
    case "star":
      return (
        <g>
          <path d="M24 8 L28 20 L40 24 L28 28 L24 40 L20 28 L8 24 L20 20 Z" {...STROKE} />
          <circle cx="24" cy="24" r="2.2" fill="currentColor" stroke="none" opacity="0.85" />
          <path d="M35 11 l1 2.4 2.4 1 -2.4 1 -1 2.4 -1 -2.4 -2.4 -1 2.4 -1 Z" fill="currentColor" stroke="none" opacity="0.7" />
        </g>
      );
    case "sprout":
      return (
        <g>
          <path d="M24 40 V22" {...STROKE} strokeWidth={2.4} />
          <path d="M24 27 Q13 27 10 17 Q21 15 24 25 Z" {...STROKE} />
          <path d="M24 33 Q35 32 38 22 Q27 20 24 31 Z" {...STROKE} />
          <path d="M24 22 Q24 13 30 9" {...STROKE} />
          <circle cx="30.6" cy="8.4" r="1.6" fill="currentColor" stroke="none" />
        </g>
      );
  }
}

export function Crest({ crest, className }: { crest: CrestName; className?: string }) {
  return (
    <svg viewBox="0 0 48 48" className={className ? `crest ${className}` : "crest"} aria-hidden="true">
      <circle className="crest-ring" cx="24" cy="24" r="22" />
      <Motif crest={crest} />
    </svg>
  );
}

// The same emblem as a group, for embedding inside another SVG (the doors).
export function CrestInline({ crest }: { crest: CrestName }) {
  return (
    <g className="crest-inline" transform="translate(36 20)">
      <circle className="crest-plate" cx="24" cy="24" r="21" />
      <circle cx="24" cy="24" r="21" fill="none" stroke="currentColor" strokeOpacity="0.55" strokeWidth="2" />
      <Motif crest={crest} />
    </g>
  );
}
