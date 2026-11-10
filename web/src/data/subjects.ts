// The subject taxonomy as the frontend sees it. One entry per department of
// Ashcombe Academy, matching the five founders in docs/persona.md and the
// pilot order in docs/workplan.md. The backend contract is GET /v1/subjects:
// it owns availability, version, lesson and persona flags, while this file
// keeps the presentation metadata (professor, accent, crest, blurb) and the
// fallback status for an unreachable API. The venue pages must not invent
// facts about departments that are not open.

export type SubjectStatus = "open" | "soon";

// One silhouette per professor, drawn in components/Silhouette.tsx. The
// variants are bust shapes only; the professor names come from the reviewed
// persona cards and the status page keeps the open/soon decision honest.
export type ProfessorVariant = "crane" | "witch-hat" | "flask" | "wide-hat" | "scarf";

// Department emblems drawn in components/Crest.tsx. The motifs are objects
// and creatures from each field (shield, flask, butterfly, spark star,
// seedling), not invented heraldry: they decorate, they teach nothing.
export type CrestName = "shield" | "flask" | "butterfly" | "star" | "sprout";

// Whether the department's professor voice is live. The API `persona` flag in
// GET /v1/subjects is authoritative; this field is only the fallback when the
// API is unreachable.
export type PersonaState = "live" | "rehearsal";

export interface Subject {
  slug: string;
  /** Canonical API subject key; differs from the URL slug for DADA. */
  apiSubject: string;
  name: string;
  /** Short name for the crest plaque on the door. */
  plaque: string;
  /** The department's professor, from the reviewed persona card. */
  professor: string;
  /** Accent colour for the venue theme. Keep the five distinguishable. */
  accent: string;
  professorVariant: ProfessorVariant;
  crest: CrestName;
  personaState: PersonaState;
  status: SubjectStatus;
  blurb: string;
}

export const SUBJECTS: Subject[] = [
  {
    slug: "defence-against-the-dark-arts",
    apiSubject: "dada",
    name: "Defence Against the Dark Arts",
    plaque: "DADA",
    professor: "Professor Alistair Crane",
    accent: "#7b93ff",
    professorVariant: "crane",
    crest: "shield",
    personaState: "live",
    status: "open",
    blurb: "Counter-jinxes, dark creatures and defensive theory.",
  },
  {
    slug: "potions",
    apiSubject: "potions",
    name: "Potions",
    plaque: "POT",
    professor: "Professor Edith Vale",
    accent: "#3fc9b0",
    professorVariant: "flask",
    crest: "flask",
    personaState: "live",
    status: "open",
    blurb: "Brewing, antidotes and the standard cautions.",
  },
  {
    slug: "transfiguration",
    apiSubject: "transfiguration",
    name: "Transfiguration",
    plaque: "TRA",
    professor: "Professor Marcus Hale",
    accent: "#b58cff",
    professorVariant: "witch-hat",
    crest: "butterfly",
    personaState: "live",
    status: "open",
    blurb: "Switches, anomalies and the laws of Gamp.",
  },
  {
    slug: "charms",
    apiSubject: "charms",
    name: "Charms",
    plaque: "CHA",
    professor: "Professor Priya Raman",
    accent: "#e8c46a",
    professorVariant: "wide-hat",
    crest: "star",
    personaState: "live",
    status: "open",
    blurb: "Everyday charms and precise wandwork.",
  },
  {
    slug: "herbology",
    apiSubject: "herbology",
    name: "Herbology",
    plaque: "HER",
    professor: "Professor Nell Ashby",
    accent: "#7ed06a",
    professorVariant: "scarf",
    crest: "sprout",
    personaState: "live",
    status: "open",
    blurb: "Magical plants and greenhouse practice.",
  },
];

export function getSubject(slug: string | undefined): Subject | undefined {
  return SUBJECTS.find((subject) => subject.slug === slug);
}

// Curated starter prompts (#162). The strings are the tested interface:
// a wording change updates tests/test_presets.py in the same change.
// The off state never offers the identity or exam prompts; both are
// persona-dependent and would fall through to the corpus or policy path.
export function startersFor(subject: Subject): string[] {
  const base = [`What is ${subject.name}?`, "Give me a practice question."];
  if (subject.personaState !== "live") {
    return base;
  }
  const prompts = ["Who are you?", ...base];
  if (subject.apiSubject === "dada") {
    prompts.push("What will be on the exam?");
  }
  return prompts;
}
