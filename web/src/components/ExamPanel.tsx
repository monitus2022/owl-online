import { useEffect, useState } from "react";
import type {
  AnswerMap,
  AttemptView,
  ExamPaper,
  GradeResult,
} from "../api/exams";
import { ExamApiError, examClient } from "../api/exams";
import { resultsStore } from "../api/results";
import type { StoredAttempt } from "../api/results";
import type { Subject } from "../data/subjects";
import { BandSeal } from "./BandSeal";
import { ResultsCard } from "./ResultsCard";

// Exam mode against the served bank. The server samples the paper, keeps the
// MCQ key, and grades after submission; records stay device-local until auth
// (#35), so the provisional wording must stay while that is true.

type Phase = "idle" | "answering" | "grading" | "graded";

function messageFor(error: unknown): string {
  if (error instanceof ExamApiError) {
    if (error.status === 429) {
      return "You have used today's attempt allowance. Try again tomorrow.";
    }
    if (error.status === 503) {
      return "The examiners are not available right now. Try again later.";
    }
    if (error.status === 400) {
      return error.message;
    }
  }
  return "The exam room could not reach the examiners. Try again.";
}

export function ExamPanel({ subject }: { subject: Subject }) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [paper, setPaper] = useState<ExamPaper | null>(null);
  const [attempt, setAttempt] = useState<AttemptView | null>(null);
  const [answers, setAnswers] = useState<AnswerMap>({});
  const [result, setResult] = useState<GradeResult | null>(null);
  const [best, setBest] = useState<StoredAttempt | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    resultsStore.best(subject.slug).then(setBest);
  }, [subject.slug, phase]);

  async function startPaper() {
    setError(null);
    try {
      const papers = await examClient.listPapers(subject.apiSubject);
      const chosen = papers[0];
      if (!chosen) {
        setError("This department has no papers yet.");
        return;
      }
      const started = await examClient.startAttempt(chosen.paperId);
      setPaper(chosen);
      setAttempt(started);
      setAnswers({});
      setResult(null);
      setPhase("answering");
    } catch (error) {
      setError(messageFor(error));
    }
  }

  async function submitPaper() {
    if (!attempt) return;
    setPhase("grading");
    setError(null);
    try {
      const graded = await examClient.grade(attempt, answers);
      if (graded.total !== null && graded.band !== null) {
        await resultsStore.save({
          id: graded.attemptId,
          subject: subject.slug,
          paperId: graded.paperId,
          total: graded.total,
          max: graded.maxMarks,
          band: graded.band,
          gradedAt: graded.gradedAt,
        });
      }
      setResult(graded);
      setPhase("graded");
    } catch (error) {
      setError(messageFor(error));
      setPhase("answering");
    }
  }

  if (phase === "idle") {
    return (
      <section className="exam" aria-label="Exam room">
        <div className="notice">
          Practice paper from the published DADA bank. The result is provisional
          and is not an official O.W.L. record.
        </div>
        <ResultsCard best={best} />
        {error && <p className="exam-error">{error}</p>}
        <button className="btn-primary" onClick={startPaper}>
          Take a paper
        </button>
      </section>
    );
  }

  if (phase === "grading") {
    return (
      <section className="exam" aria-label="Exam room">
        <div className="notice">
          The examiners are marking. Objective answers are scored on the server;
          the short answers are judged once against the stored rubric.
        </div>
        <p className="grading-note">This usually takes a few seconds.</p>
      </section>
    );
  }

  if (phase === "graded" && result && paper && attempt) {
    const gradesById = new Map(
      result.questions.map((grade) => [grade.itemId, grade]),
    );
    return (
      <section className="exam" aria-label="Exam room">
        {error && <p className="exam-error">{error}</p>}
        <div className="result-head">
          {result.band ? (
            <BandSeal
              band={result.band}
              percentage={
                result.maxMarks === 0
                  ? 0
                  : (result.total ?? 0) / result.maxMarks
              }
            />
          ) : (
            <div className="notice">
              Some answers need examiner review. There is no final band yet.
            </div>
          )}
          <div>
            <h3>Paper returned</h3>
            <p className="result-total">
              {result.total === null
                ? "Awaiting review"
                : `${result.total} / ${result.maxMarks} marks`}
            </p>
            <div className="notice">
              Practice result. Marks and bands are deterministic; the model
              answer and feedback are shown after submission.
            </div>
          </div>
        </div>
        <ol className="mark-scheme">
          {attempt.questions.map((question, index) => {
            const grade = gradesById.get(question.id);
            if (!grade) return null;
            const marks = grade.marksAwarded;
            const markClass =
              marks === null
                ? "mark-row-marks mark-part"
                : marks === grade.maxMarks
                  ? "mark-row-marks mark-full"
                  : marks > 0
                    ? "mark-row-marks mark-part"
                    : "mark-row-marks mark-none";
            return (
              <li key={question.id} className="mark-row">
                <span className="mark-row-index">{index + 1}</span>
                <span className="mark-row-prompt">{question.prompt}</span>
                <span className={markClass}>
                  {marks === null ? "review" : `${marks}/${grade.maxMarks}`}
                </span>
                {grade.needsReview && (
                  <span className="mark-row-answer">
                    Needs examiner review.
                  </span>
                )}
                {grade.feedback && (
                  <span className="mark-row-answer">{grade.feedback}</span>
                )}
                {grade.modelAnswer && (
                  <span className="mark-row-answer">
                    Model: {grade.modelAnswer}
                  </span>
                )}
                {grade.criteria.length > 0 && (
                  <span className="mark-row-answer">
                    {grade.criteria
                      .map(
                        (criterion) =>
                          `${criterion.criterionId} ${criterion.awarded}/${criterion.maxMarks}`,
                      )
                      .join(" · ")}
                  </span>
                )}
              </li>
            );
          })}
        </ol>
        <ResultsCard best={best} />
        <div className="exam-actions">
          <button className="btn-primary" onClick={startPaper}>
            Another paper
          </button>
          <button className="btn-quiet" onClick={() => setPhase("idle")}>
            Back to the room
          </button>
        </div>
      </section>
    );
  }

  if (!paper || !attempt) {
    return (
      <section className="exam" aria-label="Exam room">
        <p className="exam-error">The paper could not be loaded.</p>
      </section>
    );
  }

  return (
    <section className="exam" aria-label="Exam room">
      {error && <p className="exam-error">{error}</p>}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void submitPaper();
        }}
      >
        <h3 className="paper-title">{paper.title}</h3>
        <p className="paper-meta">
          {attempt.questions.length} questions · {attempt.marks} marks ·
          suggested {paper.durationMinutes} minutes; the student sets the pace
        </p>
        {attempt.questions.map((question, index) => (
          <fieldset key={question.id} className="question">
            <legend>
              {index + 1}. {question.prompt}
              <span className="question-marks">[{question.marks} marks]</span>
            </legend>
            {question.kind === "mcq" ? (
              <div className="options">
                {question.options.map((option) => (
                  <label key={option.id} className="option">
                    <input
                      type="radio"
                      name={question.id}
                      value={option.id}
                      checked={answers[question.id] === option.id}
                      onChange={() =>
                        setAnswers((current) => ({
                          ...current,
                          [question.id]: option.id,
                        }))
                      }
                    />
                    <span>{option.text}</span>
                  </label>
                ))}
              </div>
            ) : (
              <textarea
                rows={2}
                maxLength={2000}
                value={answers[question.id] ?? ""}
                onChange={(event) =>
                  setAnswers((current) => ({
                    ...current,
                    [question.id]: event.target.value,
                  }))
                }
                aria-label={`Answer to question ${index + 1}`}
              />
            )}
          </fieldset>
        ))}
        <div className="exam-actions">
          <button className="btn-primary" type="submit">
            Send to the examiners
          </button>
          <button
            className="btn-quiet"
            type="button"
            onClick={() => setPhase("idle")}
          >
            Abandon paper
          </button>
        </div>
      </form>
    </section>
  );
}
