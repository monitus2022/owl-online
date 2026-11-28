import { useEffect, useRef, useState } from "react";
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
// MCQ key, and grades after submission; records are session-scoped on the
// server, and accounts (#35) will move them across devices.

type Phase = "idle" | "answering" | "grading" | "graded";

function messageFor(error: unknown): string {
  if (error instanceof ExamApiError) {
    if (error.status === 404) {
      return "This paper or session is no longer available. Start a new paper.";
    }
    if (error.status === 429) {
      return "You have used today's attempt allowance. Try again tomorrow.";
    }
    if (error.status === 503) {
      return "The examiners are not at their desk right now. Try again later.";
    }
    if (error.status === 400) {
      return error.message;
    }
  }
  return "The exam room could not reach the examiners. Try again.";
}

// The rubric ids are internal shape, not student-facing words.
const CRITERION_LABELS: Record<string, string> = {
  correctness: "Facts and accuracy",
  completeness: "Coverage and explanation",
};

function criterionLabel(id: string): string {
  return CRITERION_LABELS[id] ?? id.replace(/[_-]+/g, " ");
}

// The pinned judge writes its short comment in the third person. This is a
// presentation-only rewrite for the returned parchment; it never changes a mark.
function inStudentVoice(text: string): string {
  return text
    .replace(/\bThe student's\b/g, "Your")
    .replace(/\bthe student's\b/g, "your")
    .replace(/\bThe student\b/g, "You")
    .replace(/\bthe student\b/g, "you")
    .replace(/\bThe candidate's\b/g, "Your")
    .replace(/\bthe candidate's\b/g, "your")
    .replace(/\bThe candidate\b/g, "You")
    .replace(/\bthe candidate\b/g, "you")
    .replace(/\bThe response's\b/g, "Your response's")
    .replace(/\bthe response's\b/g, "your response's")
    .replace(/\bThe response\b/g, "Your response")
    .replace(/\bthe response\b/g, "your response")
    .replace(/\bThe answer\b/g, "Your answer")
    .replace(/\bthe answer\b/g, "your answer");
}

export function ExamPanel({
  subject,
  active,
}: {
  subject: Subject;
  active: boolean;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [paper, setPaper] = useState<ExamPaper | null>(null);
  const [attempt, setAttempt] = useState<AttemptView | null>(null);
  const [answers, setAnswers] = useState<AnswerMap>({});
  const [result, setResult] = useState<GradeResult | null>(null);
  const [best, setBest] = useState<StoredAttempt | null>(null);
  const [bestFailed, setBestFailed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmSubmit, setConfirmSubmit] = useState(false);
  const submitRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!active) return;
    let live = true;
    setBestFailed(false);
    resultsStore
      .best(subject.apiSubject)
      .then((value) => {
        if (live) setBest(value);
      })
      .catch(() => {
        if (live) {
          setBest(null);
          setBestFailed(true);
        }
      });
    return () => {
      live = false;
    };
  }, [subject.apiSubject, phase, active]);

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
      setConfirmSubmit(false);
      setPhase("answering");
    } catch (error) {
      setError(messageFor(error));
    }
  }

  const answered = attempt
    ? attempt.questions.filter(
        (question) => (answers[question.id] ?? "").trim() !== "",
      ).length
    : 0;
  const blankCount = attempt ? attempt.questions.length - answered : 0;

  function handleSubmit() {
    if (!attempt) return;
    if (blankCount > 0 && !confirmSubmit) {
      setConfirmSubmit(true);
      return;
    }
    void submitPaper();
  }

  async function abandonPaper() {
    const current = attempt;
    setAttempt(null);
    setAnswers({});
    setResult(null);
    setConfirmSubmit(false);
    setError(null);
    setPhase("idle");
    if (!current) return;
    try {
      await examClient.abandon(current.attemptId);
    } catch {
      setError(
        "The paper could not be discarded. Clear all papers in Your papers deletes it.",
      );
    }
  }

  async function submitPaper() {
    if (!attempt) return;
    setConfirmSubmit(false);
    setPhase("grading");
    setError(null);
    try {
      const graded = await examClient.grade(attempt, answers);
      if (graded.total !== null && graded.band !== null) {
        await resultsStore.save({
          id: graded.attemptId,
          subject: subject.apiSubject,
          paperId: graded.paperId,
          total: graded.total,
          max: graded.maxMarks,
          band: graded.band,
          gradedAt: graded.gradedAt,
          needsReview: graded.needsReview,
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
          A practice paper from the {subject.name} department. There is no clock
          and no expiry: take as long as you need. The result is provisional and
          is not an official O.W.L. record.
        </div>
        <ResultsCard best={best} failed={bestFailed} />
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
          The professor is at the desk with your parchment. The quick questions
          are checked straight away; the written answers are read against the
          department's marking notes.
        </div>
        <p className="grading-note">
          The professor will return your parchment in a few seconds.
        </p>
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
              The professor has set some answers aside for a second reading.
              There is no final band yet.
            </div>
          )}
          <div>
            <h3>Paper returned</h3>
            <p className="result-total">
              {result.total === null
                ? "Awaiting the professor's second reading"
                : `${result.total} / ${result.maxMarks} marks`}
            </p>
            <div className="notice">
              Practice result. The marks and band are the department's; the
              expected answer and the professor's note are returned with your
              parchment.
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
                  {marks === null ? "pending" : `${marks}/${grade.maxMarks}`}
                </span>
                {grade.needsReview && (
                  <span className="mark-row-answer">
                    The professor has set this answer aside for a second reading.
                  </span>
                )}
                {grade.kind === "short" && grade.feedback && (
                  <span className="mark-row-answer">
                    The professor's note: {inStudentVoice(grade.feedback)}
                  </span>
                )}
                {grade.kind === "mcq" && grade.feedback && (
                  <span className="mark-row-answer">{grade.feedback}</span>
                )}
                {grade.modelAnswer && (
                  <span className="mark-row-answer">
                    {grade.kind === "mcq"
                      ? "The correct answer"
                      : "The expected answer"}
                    : {grade.modelAnswer}
                  </span>
                )}
                {grade.criteria.map((criterion) => (
                  <span
                    key={criterion.criterionId}
                    className="mark-row-answer"
                  >
                    {criterionLabel(criterion.criterionId)}{" "}
                    {criterion.awarded}/{criterion.maxMarks}
                    {criterion.reason
                      ? ` — ${inStudentVoice(criterion.reason)}`
                      : ""}
                  </span>
                ))}
              </li>
            );
          })}
        </ol>
        <ResultsCard best={best} failed={bestFailed} />
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
          handleSubmit();
        }}
      >
        <h3 className="paper-title">{paper.title}</h3>
        <p className="paper-meta">
          {attempt.questions.length} questions · {attempt.marks} marks ·{" "}
          {paper.timed
            ? `suggested ${paper.durationMinutes} minutes`
            : "untimed practice; the student sets the pace"}
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
                      onChange={() => {
                        setConfirmSubmit(false);
                        setAnswers((current) => ({
                          ...current,
                          [question.id]: option.id,
                        }));
                      }}
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
                onChange={(event) => {
                  setConfirmSubmit(false);
                  setAnswers((current) => ({
                    ...current,
                    [question.id]: event.target.value,
                  }));
                }}
                aria-label={`Answer to question ${index + 1}`}
              />
            )}
          </fieldset>
        ))}
        <p className="exam-progress" aria-live="polite">
          {answered} of {attempt.questions.length} answered
        </p>
        {confirmSubmit && (
          <p className="exam-confirm" role="alert">
            {blankCount} question{blankCount === 1 ? "" : "s"} left blank. Send
            the paper anyway?
          </p>
        )}
        <div className="exam-actions">
          <button className="btn-primary" type="submit" ref={submitRef}>
            {confirmSubmit ? "Send anyway" : "Send to the examiners"}
          </button>
          {confirmSubmit && (
            <button
              className="btn-quiet"
              type="button"
              onClick={() => {
                setConfirmSubmit(false);
                submitRef.current?.focus();
              }}
            >
              Keep working
            </button>
          )}
          <button
            className="btn-quiet"
            type="button"
            onClick={() => void abandonPaper()}
          >
            Abandon paper
          </button>
        </div>
      </form>
    </section>
  );
}
