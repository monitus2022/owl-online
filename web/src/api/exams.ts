import { apiBase } from "./base";

// Client for the served exam bank (#193). The server samples the paper, keeps
// the MCQ key, and grades after submission; the browser never sees the key
// before the grade response. Records are session-scoped on the server, and
// auth (#35) will move them across devices.

export type Band = "O" | "E" | "A" | "P" | "D" | "T";

export const BAND_LABELS: Record<Band, string> = {
  O: "Outstanding",
  E: "Exceeds Expectations",
  A: "Acceptable",
  P: "Poor",
  D: "Dreadful",
  T: "Troll",
};

export interface ServedOption {
  id: string;
  text: string;
}

export interface McqQuestion {
  id: string;
  kind: "mcq";
  prompt: string;
  options: ServedOption[];
  marks: number;
}

export interface ShortQuestion {
  id: string;
  kind: "short";
  prompt: string;
  marks: number;
}

export type PaperQuestion = McqQuestion | ShortQuestion;

export interface ExamPaper {
  paperId: string;
  subject: string;
  version: string;
  title: string;
  questionCount: number;
  mcqCount: number;
  shortAnswerCount: number;
  marks: number;
  durationMinutes: number;
}

export interface AttemptView {
  attemptId: string;
  paperId: string;
  subject: string;
  version: string;
  createdAt: string;
  marks: number;
  questions: PaperQuestion[];
}

export interface CriterionGrade {
  criterionId: string;
  awarded: number;
  maxMarks: number;
  reason: string;
}

export interface QuestionGrade {
  itemId: string;
  kind: "mcq" | "short";
  marksAwarded: number | null;
  maxMarks: number;
  correct: boolean | null;
  correctOptionId: string | null;
  modelAnswer: string | null;
  feedback: string;
  criteria: CriterionGrade[];
  evidenceIds: string[];
  needsReview: boolean;
}

export interface GradeResult {
  attemptId: string;
  paperId: string;
  total: number | null;
  maxMarks: number;
  band: Band | null;
  needsReview: boolean;
  gradedAt: string;
  questions: QuestionGrade[];
}

export type AnswerMap = Record<string, string>;

export interface ExamClient {
  listPapers(subject?: string): Promise<ExamPaper[]>;
  startAttempt(paperId: string): Promise<AttemptView>;
  getAttempt(attemptId: string): Promise<AttemptView>;
  grade(attempt: AttemptView, answers: AnswerMap): Promise<GradeResult>;
}

export class ExamApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ExamApiError";
  }
}

interface ApiOption {
  option_id: string;
  text: string;
}

interface ApiQuestion {
  item_id: string;
  kind: "mcq" | "short_answer";
  prompt: string;
  marks: number;
  options?: ApiOption[];
}

interface ApiAttempt {
  attempt_id: string;
  paper_id: string;
  subject: string;
  version: string;
  created_at: string;
  marks: number;
  questions: ApiQuestion[];
}

interface ApiPaper {
  paper_id: string;
  subject: string;
  version: string;
  title: string;
  question_count: number;
  mcq_count: number;
  short_answer_count: number;
  marks: number;
  duration_minutes: number;
}

interface ApiCriterion {
  criterion_id: string;
  awarded: number;
  max_marks: number;
  reason: string;
}

interface ApiQuestionGrade {
  item_id: string;
  kind: "mcq" | "short_answer";
  marks_awarded: number | null;
  max_marks: number;
  correct: boolean | null;
  correct_option_id: string | null;
  model_answer: string | null;
  feedback: string;
  criteria: ApiCriterion[];
  evidence_ids: string[];
  needs_review: boolean;
}

interface ApiGrade {
  attempt_id: string;
  paper_id: string;
  total: number | null;
  max_marks: number;
  band: Band | null;
  needs_review: boolean;
  graded_at: string;
  questions: ApiQuestionGrade[];
}

function toQuestion(question: ApiQuestion): PaperQuestion {
  if (question.kind === "mcq") {
    return {
      id: question.item_id,
      kind: "mcq",
      prompt: question.prompt,
      marks: question.marks,
      options: (question.options ?? []).map((option) => ({
        id: option.option_id,
        text: option.text,
      })),
    };
  }
  return {
    id: question.item_id,
    kind: "short",
    prompt: question.prompt,
    marks: question.marks,
  };
}

function toAttempt(attempt: ApiAttempt): AttemptView {
  return {
    attemptId: attempt.attempt_id,
    paperId: attempt.paper_id,
    subject: attempt.subject,
    version: attempt.version,
    createdAt: attempt.created_at,
    marks: attempt.marks,
    questions: attempt.questions.map(toQuestion),
  };
}

function toGrade(grade: ApiGrade): GradeResult {
  return {
    attemptId: grade.attempt_id,
    paperId: grade.paper_id,
    total: grade.total,
    maxMarks: grade.max_marks,
    band: grade.band,
    needsReview: grade.needs_review,
    gradedAt: grade.graded_at,
    questions: grade.questions.map((question) => ({
      itemId: question.item_id,
      kind: question.kind === "mcq" ? "mcq" : "short",
      marksAwarded: question.marks_awarded,
      maxMarks: question.max_marks,
      correct: question.correct,
      correctOptionId: question.correct_option_id,
      modelAnswer: question.model_answer,
      feedback: question.feedback,
      criteria: question.criteria.map((criterion) => ({
        criterionId: criterion.criterion_id,
        awarded: criterion.awarded,
        maxMarks: criterion.max_marks,
        reason: criterion.reason,
      })),
      evidenceIds: question.evidence_ids,
      needsReview: question.needs_review,
    })),
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBase()}${path}`, {
      credentials: "include",
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ExamApiError(0, "Could not reach the examiners.");
  }
  if (!response.ok) {
    let detail = "";
    try {
      const body = (await response.json()) as {
        detail?: string;
        error?: string;
      };
      detail = body.detail ?? body.error ?? "";
    } catch {
      // Leave the status-based message.
    }
    throw new ExamApiError(
      response.status,
      detail || `Exam request failed (${response.status}).`,
    );
  }
  return (await response.json()) as T;
}

export class HttpExamClient implements ExamClient {
  async listPapers(subject?: string): Promise<ExamPaper[]> {
    const query = subject ? `?subject=${encodeURIComponent(subject)}` : "";
    const papers = await request<ApiPaper[]>(`/v1/exams${query}`);
    return papers.map((paper) => ({
      paperId: paper.paper_id,
      subject: paper.subject,
      version: paper.version,
      title: paper.title,
      questionCount: paper.question_count,
      mcqCount: paper.mcq_count,
      shortAnswerCount: paper.short_answer_count,
      marks: paper.marks,
      durationMinutes: paper.duration_minutes,
    }));
  }

  async startAttempt(paperId: string): Promise<AttemptView> {
    const attempt = await request<ApiAttempt>(
      `/v1/exams/${encodeURIComponent(paperId)}/attempts`,
      { method: "POST" },
    );
    return toAttempt(attempt);
  }

  async getAttempt(attemptId: string): Promise<AttemptView> {
    const attempt = await request<ApiAttempt>(
      `/v1/attempts/${encodeURIComponent(attemptId)}`,
    );
    return toAttempt(attempt);
  }

  async grade(attempt: AttemptView, answers: AnswerMap): Promise<GradeResult> {
    const answersPayload: Array<
      { item_id: string; option_id: string } | { item_id: string; answer_text: string }
    > = [];
    for (const question of attempt.questions) {
      const value = answers[question.id] ?? "";
      if (question.kind === "mcq") {
        if (value) {
          answersPayload.push({ item_id: question.id, option_id: value });
        }
      } else {
        answersPayload.push({ item_id: question.id, answer_text: value });
      }
    }
    const grade = await request<ApiGrade>(
      `/v1/attempts/${encodeURIComponent(attempt.attemptId)}/grade`,
      {
        method: "POST",
        body: JSON.stringify({ answers: answersPayload }),
      },
    );
    return toGrade(grade);
  }
}

export const examClient: ExamClient = new HttpExamClient();
