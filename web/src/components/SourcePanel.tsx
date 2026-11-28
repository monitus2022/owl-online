import { useId, useRef, useState } from "react";
import { getMaterial } from "../api/materials";
import type { MaterialDetail } from "../api/materials";
import { sourceCopy } from "../copy";
import { SUBJECTS } from "../data/subjects";
import {
  bookLabel,
  rawSourceGroups,
  sourceChips,
  stripChunkRefs,
} from "../data/sources";

// The sources row and the reviewed-note panel behind a material source.
//
// Materials are original pack prose and can be shown publicly. Book
// citations stay locators (book, chapter, chunk id); the API route never
// returns the corpus quote or chunk text. The exact ids remain under the
// collapsed "Source details" disclosure.

// A material id is subject-prefixed. Derive the subject so a cross-subject
// referral can open its own note instead of the venue's pack.
function materialSubject(materialId: string, fallback: string): string {
  return (
    SUBJECTS.find((subject) => materialId.startsWith(`${subject.apiSubject}-`))
      ?.apiSubject ?? fallback
  );
}

export function SourcePanel({
  subject,
  materials,
  citations,
  typedCitations,
}: {
  subject: string;
  materials?: string[];
  citations?: string[];
  typedCitations?: string[];
}) {
  const input = { materials, citations, typedCitations };
  const sources = sourceChips(input);
  const rawGroups = rawSourceGroups(input);
  const [open, setOpen] = useState<string | null>(null);
  const [detail, setDetail] = useState<MaterialDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const cache = useRef(new Map<string, MaterialDetail>());
  const request = useRef(0);
  const panelId = useId();

  const openSource = sources.find((source) => source.materialId === open);
  const panelLabel = sourceCopy.noteTitle(openSource?.label ?? null);

  if (sources.length === 0 && rawGroups.length === 0) return null;

  async function load(materialId: string) {
    setFailed(false);
    const cached = cache.current.get(materialId);
    if (cached) {
      setDetail(cached);
      setLoading(false);
      return;
    }
    setDetail(null);
    setLoading(true);
    const sequence = request.current + 1;
    request.current = sequence;
    try {
      const loaded = await getMaterial(
        materialSubject(materialId, subject),
        materialId,
      );
      if (sequence !== request.current) return;
      cache.current.set(materialId, loaded);
      setDetail(loaded);
    } catch {
      if (sequence !== request.current) return;
      setFailed(true);
    } finally {
      if (sequence === request.current) setLoading(false);
    }
  }

  function toggle(materialId: string) {
    // Any previous request is stale now, including one whose material is
    // already cached when the student switches chips mid-fetch.
    request.current += 1;
    if (open === materialId) {
      setOpen(null);
      setLoading(false);
      setFailed(false);
      return;
    }
    setOpen(materialId);
    void load(materialId);
  }

  return (
    <>
      <div className="citation-group">
        <span className="citation-label">{sourceCopy.rowLabel}</span>
        <ul className="citation-chips">
          {sources.map((source) => {
            if (!source.materialId) {
              return <li key={source.key}>{source.label}</li>;
            }
            const materialId = source.materialId;
            const expanded = open === materialId;
            return (
              <li key={source.key}>
                <button
                  type="button"
                  className="source-button"
                  aria-expanded={expanded}
                  aria-controls={expanded ? panelId : undefined}
                  onClick={() => toggle(materialId)}
                >
                  {source.label}
                  <span aria-hidden="true">{expanded ? "▾" : "▸"}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </div>
      {open && (
        <section
          className="material-note"
          id={panelId}
          aria-label={panelLabel}
        >
          {loading && (
            <p className="material-status" role="status">
              {sourceCopy.loading}
            </p>
          )}
          {failed && (
            <>
              <p className="material-status material-error" role="alert">
                {sourceCopy.failed}
              </p>
              <button
                type="button"
                className="btn-quiet material-retry"
                onClick={() => void load(open)}
              >
                Try again
              </button>
            </>
          )}
          {detail && detail.material_id === open && !loading && !failed && (
            <>
              <p className="material-title">{detail.concept_title}</p>
              <p className="material-meta">
                {sourceCopy.meta(detail.topic_title, detail.pack_version)}
              </p>
              <p className="material-text">
                {stripChunkRefs(
                  detail.text,
                  detail.source_refs.map((ref) => ref.chunk_id),
                )}
              </p>
              {detail.source_refs.length > 0 && (
                <p className="material-refs">
                  {sourceCopy.refsPrefix}{" "}
                  {detail.source_refs.map((ref, index) => (
                    <span key={ref.chunk_id}>
                      {index > 0 && " · "}
                      {bookLabel(ref.book, ref.chapter)}{" "}
                      <code>{ref.chunk_id}</code>
                    </span>
                  ))}
                </p>
              )}
              <p className="visually-hidden" role="status">
                {sourceCopy.loaded}
              </p>
            </>
          )}
        </section>
      )}
      {rawGroups.length > 0 && (
        <details className="citation-details">
          <summary>{sourceCopy.details}</summary>
          {rawGroups.map((group) => (
            <div className="citation-group" key={group.label}>
              <span className="citation-label">{group.label}</span>
              <ul className="citation-chips">
                {group.ids.map((id) => (
                  <li key={id}>
                    <code>{id}</code>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </details>
      )}
    </>
  );
}
