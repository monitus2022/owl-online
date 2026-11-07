import { useId } from "react";
import type { ProfessorVariant } from "../data/subjects";

// The professor's silhouette: a rim-lit bust in a roundel. No face, so no
// invented likeness — the accent light comes from the subject theme and the
// shape varies per department. While an answer streams, the halo pulses
// ("thinking"); the global reduced-motion rule stops the pulse.

const BUST_PATH =
  "M10 64 C12 48 20 42 27 41 C30 40 32 37 32 32 C32 37 34 40 37 41 " +
  "C44 42 52 48 54 64 Z";

function VariantParts({ variant }: { variant: ProfessorVariant }) {
  switch (variant) {
    case "crane":
      // High, close-cropped collar and a wand held behind the shoulder.
      return (
        <g>
          <path d="M26 40 L29 33 L32 39 L35 33 L38 40 Z" />
          <line
            className="sil-wand"
            x1="47"
            y1="16"
            x2="52"
            y2="38"
            strokeLinecap="round"
          />
          <circle className="sil-wand-tip" cx="46.5" cy="14.5" r="2" />
        </g>
      );
    case "witch-hat":
      return (
        <g>
          <polygon points="33,2 22,22 44,22" />
          <path d="M18 24 Q33 29 48 24" strokeWidth="3" fill="none" className="sil-band" />
        </g>
      );
    case "wide-hat":
      return (
        <g>
          <rect x="25" y="8" width="14" height="12" rx="4" />
          <ellipse cx="32" cy="21" rx="19" ry="4" />
        </g>
      );
    case "flask":
      // A round-bottom flask held up at the shoulder.
      return (
        <g>
          <rect x="42" y="26" width="4" height="9" rx="1.5" />
          <circle cx="44" cy="41" r="7" />
          <circle className="sil-bubble" cx="44" cy="42" r="1.5" />
        </g>
      );
    case "scarf":
      // A greenhouse scarf with a trailing end.
      return (
        <g>
          <path
            className="sil-band"
            d="M20 40 Q32 46 44 40 Q46 46 42 52 Q38 46 34 48"
            strokeWidth="5"
            fill="none"
            strokeLinecap="round"
          />
        </g>
      );
  }
}

export function Silhouette({
  variant,
  thinking = false,
}: {
  variant: ProfessorVariant;
  thinking?: boolean;
}) {
  // Gradient and clip ids must be unique per rendered instance.
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const rimId = `sil-rim-${uid}`;
  const clipId = `sil-clip-${uid}`;

  return (
    <span className={thinking ? "silhouette sil-thinking" : "silhouette"}>
      <svg viewBox="0 0 64 64" aria-hidden="true">
        <defs>
          <linearGradient id={rimId} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.45" />
            <stop offset="55%" stopColor="var(--accent)" stopOpacity="0" />
          </linearGradient>
          <clipPath id={clipId}>
            <circle cx="32" cy="32" r="29" />
          </clipPath>
        </defs>
        <circle className="sil-bg" cx="32" cy="32" r="29" />
        <g clipPath={`url(#${clipId})`} className="sil-figure">
          <path d={BUST_PATH} />
          <circle cx="32" cy="22" r="9.5" />
          <VariantParts variant={variant} />
          <path d={BUST_PATH} className="sil-rim" style={{ fill: `url(#${rimId})` }} />
          <circle
            cx="32"
            cy="22"
            r="9.5"
            className="sil-rim"
            style={{ fill: `url(#${rimId})` }}
          />
        </g>
        <circle className="sil-halo" cx="32" cy="32" r="30.5" />
      </svg>
    </span>
  );
}
