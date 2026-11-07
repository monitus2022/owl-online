// The subject taxonomy as the frontend sees it. One entry per department of
// Ashcombe Academy, matching the five founders in docs/persona.md and the
// pilot order in docs/workplan.md. The backend contract for this list is the
// planned GET /v1/subjects; until it lands, this file is the data source and
// the venue pages must not invent facts about departments that are not open.

export type SubjectStatus = "open" | "soon";

// One silhouette per professor, drawn in components/Silhouette.tsx. The
// variants are bust shapes only — an unnamed department gets a shape but no
// invented identity; the status page is what keeps it honest.
export type ProfessorVariant = "crane" | "witch-hat" | "flask" | "wide-hat" | "scarf";

export interface Subject {
  slug: string;
  name: string;
  /** Short name for the crest plaque on the door. */
  plaque: string;
  /** The department's professor, once one exists in the persona layer. */
  professor: string;
  /** Accent colour for the venue theme. Keep the five distinguishable. */
  accent: string;
  professorVariant: ProfessorVariant;
  status: SubjectStatus;
  blurb: string;
}

export const SUBJECTS: Subject[] = [
  {
    slug: "defence-against-the-dark-arts",
    name: "Defence Against the Dark Arts",
    plaque: "DADA",
    professor: "Professor Alistair Crane",
    accent: "#7b93ff",
    professorVariant: "crane",
    status: "open",
    blurb: "Counter-jinxes, dark creatures and defensive theory.",
  },
  {
    slug: "potions",
    name: "Potions",
    plaque: "POT",
    professor: "Department not yet open",
    accent: "#3fc9b0",
    professorVariant: "flask",
    status: "soon",
    blurb: "Brewing, antidotes and the standard cautions.",
  },
  {
    slug: "transfiguration",
    name: "Transfiguration",
    plaque: "TRA",
    professor: "Department not yet open",
    accent: "#b58cff",
    professorVariant: "witch-hat",
    status: "soon",
    blurb: "Switches, anomalies and the laws of Gamp.",
  },
  {
    slug: "charms",
    name: "Charms",
    plaque: "CHA",
    professor: "Department not yet open",
    accent: "#e8c46a",
    professorVariant: "wide-hat",
    status: "soon",
    blurb: "Everyday charms and precise wandwork.",
  },
  {
    slug: "herbology",
    name: "Herbology",
    plaque: "HER",
    professor: "Department not yet open",
    accent: "#7ed06a",
    professorVariant: "scarf",
    status: "soon",
    blurb: "Magical plants and greenhouse practice.",
  },
];

export function getSubject(slug: string | undefined): Subject | undefined {
  return SUBJECTS.find((subject) => subject.slug === slug);
}
