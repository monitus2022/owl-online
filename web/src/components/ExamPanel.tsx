import { useEffect, useState } from "react";
import type { AnswerMap, GradeResult, Paper } from "../api/exams";
import { examClient } from "../api/exams";
import { resultsStore } from "../api/results";
import type { StoredAttempt } from "../api/results";
import type { Subject } from "../data/subjects";
import { BandSeal } from "./BandSeal";
import { ResultsCard } from "./ResultsCard";

// Exam mode against the mocked paper contract. Until the exam bank ships
// (#38, #42), papers and marks come from MockExamClient and records from
// localStorage — the banner below must stay as long as that is true.

type Phase = "idle" | "answering" | "grading" | "graded";

export function ExamPanel({ subject }: { subject: Subject }) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [paper, setPaper] = useState<Paper | null>(null);
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
      setPaper(await examClient.getPaper(subject.slug));
      setAnswers({});
      setResult(null);
      setPhase("answering");
    } catch {
      setError("This department has no papers yet.");
    }
  }

  async function submitPaper() {
    if (!paper) return;
    setPhase("grading");
    setError(null);
    try {
      const graded = await examClient.grade(paper, answers);
      await resultsStore.save({
        id: graded.paperId,
        subject: subject.slug,
        paperId: graded.paperId,
        total: graded.total,
        max: graded.max,
        band: graded.band,
        gradedAt: graded.gradedAt,
      });
      setResult(graded);
      setPhase("graded");
    } catch {
      setError("The paper could not be marked. Your answers are kept — send it again or leave the room.");
      setPhase("answering");
    }
  }

  if (phase === "idle") {
    return (
      <section className="exam" aria-label="Exam room">
        <div className="notice notice-mock">
          Demonstration paper. Questions and marks are placeholders until the
          validated exam bank and the grading service ship — this result is
          not a record of any official paper.
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
        <div className="notice notice-mock">
          Demonstration marking. These marks are computed on this device by
          the mock client, not by the exam bank’s graders.
        </div>
        <p className="grading-note">
          The examiners are marking. Objective answers are matched against the
          key; short answers are compared with the accepted spellings.
        </p>
      </section>
    );
  }

  if (phase === "graded" && result && paper) {
    const gradesById = new Map(
      result.questionGrades.map((grade) => [grade.questionId, grade]),
    );
    return (
      <section className="exam" aria-label="Exam room">
        <div className="result-head">
          <BandSeal
            band={result.band}
            percentage={result.max === 0 ? 0 : result.total / result.max}
          />
          <div>
            <h3>Paper returned</h3>
            <p className="result-total">
              {result.total} / {result.max} marks
            </p>
            <div className="notice notice-mock">
              Mock grading — the real bands come from the server grader and
              will be deterministic and auditable.
            </div>
          </div>
        </div>
        <ol className="mark-scheme">
          {paper.questions.map((question, index) => {
            const grade = gradesById.get(question.id);
            if (!grade) return null;
            return (
              <li key={question.id} className="mark-row">
                <span className="mark-row-index">{index + 1}</span>
                <span className="mark-row-prompt">{question.prompt}</span>
                <span
                  className={
                    grade.marksAwarded === grade.maxMarks
                      ? "mark-row-marks mark-full"
                      : grade.marksAwarded > 0
                        ? "mark-row-marks mark-part"
                        : "mark-row-marks mark-none"
                  }
                >
                  {grade.marksAwarded}/{grade.maxMarks}
                </span>
                {grade.marksAwarded < grade.maxMarks && (
                  <span className="mark-row-answer">Model: {grade.modelAnswer}</span>
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

  return (
    <section className="exam" aria-label="Exam room">
      {error && <p className="exam-error">{error}</p>}
      {paper && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void submitPaper();
          }}
        >
          <h3 className="paper-title">{paper.title}</h3>
          <p className="paper-meta">
            {paper.questions.length} questions ·{" "}
            {paper.questions.reduce((sum, question) => sum + question.marks, 0)}{" "}
            marks · no clock, the student sets the pace
          </p>
            {paper.questions.map((question, index) => (
              <fieldset key={question.id} className="question">
                <legend>
                  {index + 1}. {question.prompt}
                  <span className="question-marks">[{question.marks} marks]</span>
                </legend>
                {question.kind === "mcq" ? (
                  <div className="options">
                    {question.options.map((option, optionIndex) => (
                      <label key={option} className="option">
                        <input
                          type="radio"
                          name={question.id}
                          value={String(optionIndex)}
                          checked={answers[question.id] === String(optionIndex)}
                          onChange={() =>
                            setAnswers((current) => ({
                              ...current,
                              [question.id]: String(optionIndex),
                            }))
                          }
                        />
                        <span>{option}</span>
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
      )}
    </section>
  );
}
