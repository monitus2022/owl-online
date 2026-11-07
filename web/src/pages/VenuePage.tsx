import { useState } from "react";
import type { CSSProperties, KeyboardEvent } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { ArchBackdrop } from "../components/ArchBackdrop";
import { Crest } from "../components/Crest";
import { ChatPanel } from "../components/ChatPanel";
import { ExamPanel } from "../components/ExamPanel";
import { Silhouette } from "../components/Silhouette";
import { getSubject } from "../data/subjects";

// The study venue. The subject accent is injected as a CSS variable for the
// whole page, so every control, focus ring and seal picks up the department
// colour from the subject data alone.

type Tab = "chat" | "exam";

export function VenuePage() {
  const { slug } = useParams();
  const subject = getSubject(slug);
  const [tab, setTab] = useState<Tab>("chat");

  // WAI-ARIA tabs: arrow keys move activation between the two tabs.
  function moveTab(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    const next: Tab = tab === "chat" ? "exam" : "chat";
    setTab(next);
    document.getElementById(next === "chat" ? "tab-chat" : "tab-exam")?.focus();
  }

  if (!subject) return <Navigate to="/cloister" replace />;

  if (subject.status === "soon") {
    return (
      <main className="venue" style={{ "--accent": subject.accent } as CSSProperties}>
        <nav className="crumbs" aria-label="Breadcrumb">
          <Link to="/">The gate</Link>
          <span aria-hidden="true"> / </span>
          <Link to="/cloister">The cloister</Link>
          <span aria-hidden="true"> / </span>
          <span>{subject.name}</span>
        </nav>
        <h1>{subject.name}</h1>
        <ArchBackdrop crest={subject.crest} dim />
        <div className="soon-card">
          <h2>The classroom is being furnished</h2>
          <p>
            {subject.blurb} This department opens when its subject pack is
            validated and its professor takes the post.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main
      className="venue"
      style={{ "--accent": subject.accent } as CSSProperties}
    >
      <nav className="crumbs" aria-label="Breadcrumb">
        <Link to="/">The gate</Link>
        <span aria-hidden="true"> / </span>
        <Link to="/cloister">The cloister</Link>
        <span aria-hidden="true"> / </span>
        <span>{subject.name}</span>
      </nav>
      <header className="venue-head">
        <Silhouette variant={subject.professorVariant} />
        <div>
          <h1>{subject.name}</h1>
          <p className="venue-professor">
            {subject.professor}
            {subject.personaState === "live" ? "" : " — voice in rehearsal"}
          </p>
        </div>
        <Crest crest={subject.crest} className="venue-crest" />
      </header>
      <ArchBackdrop crest={subject.crest} />
      <div className="tabs" role="tablist" aria-label="Room" onKeyDown={moveTab}>
        <button
          id="tab-chat"
          role="tab"
          aria-selected={tab === "chat"}
          aria-controls="panel-chat"
          tabIndex={tab === "chat" ? 0 : -1}
          className={tab === "chat" ? "tab tab-on" : "tab"}
          onClick={() => setTab("chat")}
        >
          Ask the professor
        </button>
        <button
          id="tab-exam"
          role="tab"
          aria-selected={tab === "exam"}
          aria-controls="panel-exam"
          tabIndex={tab === "exam" ? 0 : -1}
          className={tab === "exam" ? "tab tab-on" : "tab"}
          onClick={() => setTab("exam")}
        >
          Exam room
        </button>
      </div>
      {/* Both panels stay mounted so the transcript and any in-flight stream
          survive tab switches; the hidden attribute only hides them. */}
      <div
        id="panel-chat"
        role="tabpanel"
        aria-labelledby="tab-chat"
        hidden={tab !== "chat"}
      >
        <ChatPanel subject={subject} />
      </div>
      <div
        id="panel-exam"
        role="tabpanel"
        aria-labelledby="tab-exam"
        hidden={tab !== "exam"}
      >
        <ExamPanel subject={subject} />
      </div>
    </main>
  );
}
