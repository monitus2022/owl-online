// Exam client. The interface mirrors the planned contract in docs/api.md
// (GET /v1/exams/{paper_id} returns questions with no answers; grading is a
// separate call that returns per-question marks and a deterministic band).
// MockExamClient fills that shape locally until the exam bank (#38, #42)
// lands, so swapping in an HttpExamClient later is a wiring change, not a
// rewrite. Mock marks are a demonstration: the UI must present them as such.

export type Band = "O" | "E" | "A" | "P" | "D" | "T";

export const BAND_LABELS: Record<Band, string> = {
  O: "Outstanding",
  E: "Exceeds Expectations",
  A: "Acceptable",
  P: "Poor",
  D: "Dreadful",
  T: "Troll",
};

export interface McqQuestion {
  id: string;
  kind: "mcq";
  prompt: string;
  options: string[];
  marks: number;
}

export interface ShortQuestion {
  id: string;
  kind: "short";
  prompt: string;
  marks: number;
}

export type PaperQuestion = McqQuestion | ShortQuestion;

export interface Paper {
  id: string;
  subject: string;
  title: string;
  questions: PaperQuestion[];
}

export interface QuestionGrade {
  questionId: string;
  marksAwarded: number;
  maxMarks: number;
  modelAnswer: string;
  note?: string;
}

export interface GradeResult {
  paperId: string;
  questionGrades: QuestionGrade[];
  total: number;
  max: number;
  band: Band;
  gradedAt: string;
  /** True while a local stand-in did the grading instead of the server. */
  mock: boolean;
}

export type AnswerMap = Record<string, string>;

export interface ExamClient {
  getPaper(subjectSlug: string): Promise<Paper>;
  grade(paper: Paper, answers: AnswerMap): Promise<GradeResult>;
}

interface BankEntry {
  question: PaperQuestion;
  /** For mcq: the index of the correct option. */
  answerIndex?: number;
  /** For short: accepted spellings, normalised before comparison. */
  accepted?: string[];
}

// A small original practice bank for the DADA demo paper. When the real
// bank ships, questions come from validated subject packs with evidence
// snapshots; nothing here is presented as an official paper.
const DADA_BANK: BankEntry[] = [
  {
    question: {
      id: "mcq-boggart",
      kind: "mcq",
      prompt: "Which charm is used to repel a boggart?",
      options: ["Expecto Patronum", "Riddikulus", "Protego", "Serpensortia"],
      marks: 5,
    },
    answerIndex: 1,
  },
  {
    question: {
      id: "mcq-shield",
      kind: "mcq",
      prompt: "Which spell raises a shield against most jinxes and hexes?",
      options: ["Protego", "Reparo", "Relashio", "Petrificus Totalus"],
      marks: 5,
    },
    answerIndex: 0,
  },
  {
    question: {
      id: "mcq-unforgivable",
      kind: "mcq",
      prompt: "Which of these is NOT one of the three Unforgivable Curses?",
      options: [
        "The Cruciatus Curse",
        "The Imperius Curse",
        "Sectumsempra",
        "The Killing Curse",
      ],
      marks: 5,
    },
    answerIndex: 2,
  },
  {
    question: {
      id: "mcq-dementor",
      kind: "mcq",
      prompt: "What do dementors feed on?",
      options: [
        "Human happiness and positive feelings",
        "Ink and parchment",
        "The warmth of fires",
        "Silence",
      ],
      marks: 5,
    },
    answerIndex: 0,
  },
  {
    question: {
      id: "mcq-light",
      kind: "mcq",
      prompt: "Which charm lights the tip of a wand?",
      options: ["Nox", "Lumos", "Alohomora", "Aparecium"],
      marks: 5,
    },
    answerIndex: 1,
  },
  {
    question: {
      id: "mcq-counter",
      kind: "mcq",
      prompt: "A spell cast to undo the effect of a jinx is called a:",
      options: ["counter-spell of a hex only", "counter-jinx", "curse-break", "ward"],
      marks: 5,
    },
    answerIndex: 1,
  },
  {
    question: {
      id: "short-riddikulus",
      kind: "short",
      prompt: "Name the charm that turns a boggart's shape aside.",
      marks: 10,
    },
    accepted: ["riddikulus"],
  },
  {
    question: {
      id: "short-patronus",
      kind: "short",
      prompt: "Which conjured guardian is driven by a powerful happy memory?",
      marks: 10,
    },
    accepted: ["patronus", "a patronus", "the patronus charm", "expecto patronum"],
  },
  {
    question: {
      id: "short-fear",
      kind: "short",
      prompt: "A boggart takes the shape of what?",
      marks: 10,
    },
    accepted: ["your worst fear", "worst fear", "a person's worst fear", "fear"],
  },
  {
    question: {
      id: "short-imperius",
      kind: "short",
      prompt: "Which Unforgivable Curse compels another person to obey?",
      marks: 10,
    },
    accepted: ["imperio", "the imperius curse", "imperius"],
  },
  {
    question: {
      id: "short-avada",
      kind: "short",
      prompt: "Give the incantation of the Killing Curse.",
      marks: 10,
    },
    accepted: ["avada kedavra"],
  },
  {
    question: {
      id: "short-protego",
      kind: "short",
      prompt: "Which one-word incantation calls up a shielding spell?",
      marks: 10,
    },
    accepted: ["protego"],
  },
];

export function bandFor(percentage: number): Band {
  if (percentage >= 0.9) return "O";
  if (percentage >= 0.8) return "E";
  if (percentage >= 0.7) return "A";
  if (percentage >= 0.5) return "P";
  if (percentage >= 0.3) return "D";
  return "T";
}

function normalise(value: string): string {
  return value.trim().toLowerCase().replace(/[^a-z0-9 ]+/g, "");
}

function sample<T>(items: T[], count: number): T[] {
  const pool = [...items];
  const picked: T[] = [];
  while (picked.length < count && pool.length > 0) {
    const index = Math.floor(Math.random() * pool.length);
    picked.push(pool.splice(index, 1)[0]);
  }
  return picked;
}

export class MockExamClient implements ExamClient {
  async getPaper(subjectSlug: string): Promise<Paper> {
    if (subjectSlug !== "defence-against-the-dark-arts") {
      throw new Error("No papers exist for this department yet.");
    }
    // The blueprint: 10 questions, mcq plus short answer, sampled per attempt.
    const mcqs = sample(
      DADA_BANK.filter((entry) => entry.question.kind === "mcq"),
      6,
    );
    const shorts = sample(
      DADA_BANK.filter((entry) => entry.question.kind === "short"),
      4,
    );
    return {
      id: `mock-${Date.now()}`,
      subject: subjectSlug,
      title: "Defence Against the Dark Arts — practice paper (demo)",
      questions: [...mcqs, ...shorts].map((entry) => entry.question),
    };
  }

  async grade(paper: Paper, answers: AnswerMap): Promise<GradeResult> {
    const entries = new Map(DADA_BANK.map((entry) => [entry.question.id, entry]));
    const questionGrades: QuestionGrade[] = paper.questions.map((question) => {
      const entry = entries.get(question.id);
      const given = answers[question.id] ?? "";
      let marksAwarded = 0;
      let modelAnswer = "";
      if (entry && question.kind === "mcq" && entry.answerIndex !== undefined) {
        modelAnswer = question.options[entry.answerIndex];
        marksAwarded = given === String(entry.answerIndex) ? question.marks : 0;
      } else if (entry && question.kind === "short" && entry.accepted) {
        modelAnswer = entry.accepted[0];
        marksAwarded = entry.accepted.some((value) => normalise(value) === normalise(given))
          ? question.marks
          : 0;
      }
      return {
        questionId: question.id,
        marksAwarded,
        maxMarks: question.marks,
        modelAnswer,
      };
    });
    // Stand in for the one batch grading call the real grader will make.
    await new Promise((resolve) => setTimeout(resolve, 900));
    const total = questionGrades.reduce((sum, grade) => sum + grade.marksAwarded, 0);
    const max = questionGrades.reduce((sum, grade) => sum + grade.maxMarks, 0);
    return {
      paperId: paper.id,
      questionGrades,
      total,
      max,
      band: bandFor(max === 0 ? 0 : total / max),
      gradedAt: new Date().toISOString(),
      mock: true,
    };
  }
}

export const examClient: ExamClient = new MockExamClient();
