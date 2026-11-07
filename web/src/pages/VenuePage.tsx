import { useState } from "react";
import type { CSSProperties, KeyboardEvent } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { ArchBackdrop } from "../components/ArchBackdrop";
import { Crest } from "../components/Crest";
import { ChatPanel } from "../components/ChatPanel";
import { ExamPanel } from "../components/ExamPanel";
import { HistoryPanel } from "../components/HistoryPanel";
import { Silhouette } from "../components/Silhouette";
import { getSubject } from "../data/subjects";

// The study venue. The subject accent is injected as a CSS variable for the
// whole page, so every control, focus ring and seal picks up the department
// colour from the subject data alone.

type Tab = "chat" | "exam" | "papers";

const TABS: { id: Tab; label: string }[] = [
  { id: "chat", label: "Ask the professor" },
  { id: "exam", label: "Exam room" },
  { id: "papers", label: "Your papers" },
];

export function VenuePage() {
  const { slug } = useParams();
  const subject = getSubject(slug);
  const [tab, setTab] = useState<Tab>("chat");

  // WAI-ARIA tabs: arrow keys move activation around the ring of tabs.
  function moveTab(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    const index = TABS.findIndex((entry) => entry.id === tab);
    const step = event.key === "ArrowRight" ? 1 : TABS.length - 1;
    const next = TABS[(index + step) % TABS.length];
    setTab(next.id);
    document.getElementById(`tab-${next.id}`)?.focus();
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
          <Crest crest={subject.crest} className="soon-crest" />
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
        {TABS.map((entry) => (
          <button
            key={entry.id}
            id={`tab-${entry.id}`}
            role="tab"
            aria-selected={tab === entry.id}
            aria-controls={`panel-${entry.id}`}
            tabIndex={tab === entry.id ? 0 : -1}
            className={tab === entry.id ? "tab tab-on" : "tab"}
            onClick={() => setTab(entry.id)}
          >
            {entry.label}
          </button>
        ))}
      </div>
      {/* All panels stay mounted so the transcript, an in-flight paper and a
          streaming answer survive tab switches; hidden only hides them. The
          history panel refetches when it becomes active. */}
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
      <div
        id="panel-papers"
        role="tabpanel"
        aria-labelledby="tab-papers"
        hidden={tab !== "papers"}
      >
        <HistoryPanel subject={subject} active={tab === "papers"} />
      </div>
    </main>
  );
}
