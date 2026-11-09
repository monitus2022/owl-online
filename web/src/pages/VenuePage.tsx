import { useEffect, useState } from "react";
import type { CSSProperties, KeyboardEvent } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { ArchBackdrop } from "../components/ArchBackdrop";
import { Crest } from "../components/Crest";
import { ChatPanel } from "../components/ChatPanel";
import { ExamPanel } from "../components/ExamPanel";
import { HistoryPanel } from "../components/HistoryPanel";
import { Silhouette } from "../components/Silhouette";
import { fetchSubjects } from "../api/subjects";
import type { SubjectsPayload } from "../api/subjects";
import { getSubject } from "../data/subjects";
import type { Subject } from "../data/subjects";

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
  const [department, setDepartment] = useState<SubjectsPayload | null>(null);
  const [departmentChecked, setDepartmentChecked] = useState(false);

  useEffect(() => {
    let active = true;
    fetchSubjects()
      .then((payload) => {
        if (active) {
          setDepartment(payload);
          setDepartmentChecked(true);
        }
      })
      .catch(() => {
        // Keep the static stand-in when the API is unreachable; chat will
        // report the connection failure on the first question.
        if (active) setDepartmentChecked(true);
      });
    return () => {
      active = false;
    };
  }, []);

  // WAI-ARIA tabs: arrow keys move activation around the ring of tabs,
  // Home/End jump to the ends. The list is short, so activation follows
  // focus (automatic activation) instead of separate selection state.
  function moveTab(event: KeyboardEvent<HTMLDivElement>) {
    const index = TABS.findIndex((entry) => entry.id === tab);
    let next: Tab | null = null;
    if (event.key === "ArrowRight") {
      next = TABS[(index + 1) % TABS.length].id;
    } else if (event.key === "ArrowLeft") {
      next = TABS[(index + TABS.length - 1) % TABS.length].id;
    } else if (event.key === "Home") {
      next = TABS[0].id;
    } else if (event.key === "End") {
      next = TABS[TABS.length - 1].id;
    }
    if (next === null) return;
    event.preventDefault();
    setTab(next);
    document.getElementById(`tab-${next}`)?.focus();
  }

  if (!subject) return <Navigate to="/cloister" replace />;

  const summary = department?.subjects.find(
    (entry) => entry.subject === subject.apiSubject,
  );
  // The static list is the product decision for open/soon. The API supplies
  // the pack and the lesson/persona flags for an open department; an absent
  // pack keeps the room usable on the corpus path. Opening a statically
  // "soon" department is a product change with its own professor copy.
  const isOpen = subject.status === "open";
  // The persona flag is site-wide today, but only the home subject has a card.
  // Keep every other room honest until the per-subject registry (#195/#97) lands.
  // The lesson subject is the fallback while an older API lacks persona_subject.
  const personaSubject = department?.persona_subject || department?.lesson_subject;
  const personaState =
    department === null
      ? subject.personaState
      : department.persona && personaSubject === subject.apiSubject
        ? "live"
        : "rehearsal";
  const room: Subject = {
    ...subject,
    status: isOpen ? "open" : "soon",
    personaState,
  };
  const lesson = Boolean(
    department?.lesson &&
      department.lesson_subject === subject.apiSubject &&
      summary?.status === "published" &&
      isOpen,
  );
  const lessonFallback = Boolean(department?.lesson_fallback ?? true);
  const packMissing =
    department !== null &&
    subject.status === "open" &&
    summary?.status !== "published";

  if (room.status === "soon") {
    return (
      <main className="venue" style={{ "--accent": room.accent } as CSSProperties}>
        <nav className="crumbs" aria-label="Breadcrumb">
          <Link to="/">The gate</Link>
          <span aria-hidden="true"> / </span>
          <Link to="/cloister">The cloister</Link>
          <span aria-hidden="true"> / </span>
          <span>{room.name}</span>
        </nav>
        <h1>{room.name}</h1>
        <ArchBackdrop crest={room.crest} dim />
        <div className="soon-card">
          <Crest crest={room.crest} className="soon-crest" />
          <h2>The classroom is being furnished</h2>
          <p>
            {room.blurb} This department opens when its subject pack is
            validated and its professor takes the post.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main
      className="venue"
      style={{ "--accent": room.accent } as CSSProperties}
    >
      <nav className="crumbs" aria-label="Breadcrumb">
        <Link to="/">The gate</Link>
        <span aria-hidden="true"> / </span>
        <Link to="/cloister">The cloister</Link>
        <span aria-hidden="true"> / </span>
        <span>{room.name}</span>
      </nav>
      <header className="venue-head">
        <Silhouette variant={room.professorVariant} />
        <div>
          <h1>{room.name}</h1>
          <p className="venue-professor">
            {room.professor}
            {room.personaState === "live" ? "" : " — voice in rehearsal"}
          </p>
        </div>
        <Crest crest={room.crest} className="venue-crest" />
      </header>
      <ArchBackdrop crest={room.crest} />
      {packMissing && tab === "chat" && (
        <p className="venue-note" role="status" aria-live="polite">
          The department's reviewed notes are not loaded on the server; answers
          come from the set texts until they are available.
        </p>
      )}
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
        <ChatPanel
          key={room.slug}
          subject={room}
          lesson={lesson}
          lessonFallback={lessonFallback}
          ready={departmentChecked}
        />
      </div>
      <div
        id="panel-exam"
        role="tabpanel"
        aria-labelledby="tab-exam"
        hidden={tab !== "exam"}
      >
        <ExamPanel subject={room} />
      </div>
      <div
        id="panel-papers"
        role="tabpanel"
        aria-labelledby="tab-papers"
        tabIndex={0}
        hidden={tab !== "papers"}
      >
        <HistoryPanel subject={room} active={tab === "papers"} />
      </div>
    </main>
  );
}
