import { useId, useRef, useState } from "react";
import { getMaterial } from "../api/materials";
import type { MaterialDetail, MaterialSourceRef } from "../api/materials";
import { rawSourceGroups, sourceChips } from "../data/sources";

// The sources row and the reviewed-note panel behind a material source.
//
// Materials are original pack prose and can be shown publicly. Book
// citations stay locators (book, chapter, chunk id); the API route never
// returns the corpus quote or chunk text. The exact ids remain under the
// collapsed "Source details" disclosure.

function bookLocators(refs: MaterialSourceRef[]): string[] {
  const seen = new Set<string>();
  const locators: string[] = [];
  for (const ref of refs) {
    const key = `${ref.book}:${ref.chapter}`;
    if (seen.has(key)) continue;
    seen.add(key);
    locators.push(`Book ${ref.book}, Chapter ${ref.chapter}`);
  }
  return locators;
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

  if (sources.length === 0 && rawGroups.length === 0) return null;

  async function toggle(materialId: string) {
    if (open === materialId) {
      request.current += 1;
      setOpen(null);
      setLoading(false);
      setFailed(false);
      return;
    }
    setOpen(materialId);
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
      const loaded = await getMaterial(subject, materialId);
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

  return (
    <>
      <div className="citation-group">
        <span className="citation-label">Sources</span>
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
                  onClick={() => void toggle(materialId)}
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
        <section className="material-note" id={panelId} aria-label="Reviewed note">
          {loading && (
            <p className="material-status" role="status">
              Fetching the reviewed note…
            </p>
          )}
          {failed && (
            <p className="material-status material-error" role="alert">
              The reviewed note could not be opened.
            </p>
          )}
          {detail && detail.material_id === open && !loading && !failed && (
            <>
              <p className="material-title">{detail.concept_title}</p>
              <p className="material-meta">
                {detail.topic_title} · reviewed note · pack {detail.pack_version}
              </p>
              <p className="material-text">{detail.text}</p>
              {detail.source_refs.length > 0 && (
                <p className="material-refs">
                  Sources: {bookLocators(detail.source_refs).join(" · ")}
                </p>
              )}
            </>
          )}
        </section>
      )}
      {rawGroups.length > 0 && (
        <details className="citation-details">
          <summary>Source details</summary>
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
