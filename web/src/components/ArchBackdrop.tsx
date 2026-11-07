import type { CrestName } from "../data/subjects";
import { Crest } from "./Crest";

// The classroom band: a stylised colonnade drawn in SVG, themed entirely by
// the subject accent through CSS. The department crest floats as a watermark
// at the right. Decorative; hidden from the accessibility tree.
export function ArchBackdrop({ crest, dim = false }: { crest: CrestName; dim?: boolean }) {
  const arches = Array.from({ length: 8 }, (_, i) => {
    const x = i * 120 + 20;
    return (
      <g key={i}>
        <path
          className="arcade-arch"
          d={`M${x} 178 V96 Q${x + 40} 52 ${x + 80} 96 V178 Z`}
        />
        <ellipse className="arcade-glow" cx={x + 40} cy={150} rx={30} ry={24} />
      </g>
    );
  });
  return (
    <div className={dim ? "backdrop backdrop-dim" : "backdrop"}>
      <svg className="arcade" viewBox="0 0 960 180" preserveAspectRatio="xMidYMax slice" aria-hidden="true">
        {arches}
        <line className="arcade-floor" x1="0" y1="178" x2="960" y2="178" />
      </svg>
      <Crest crest={crest} className="backdrop-crest" />
    </div>
  );
}
