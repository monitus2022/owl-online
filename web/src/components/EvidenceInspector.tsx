import type { EvidenceReport } from "../api/chat";

// Local review aid (#295). Rendered only in a dev build and only when the
// server returns an evidence report (OWL_DEV_EVIDENCE=1). It can show
// copyrighted chunk text, so it must never reach the deployed student UI.
export function EvidenceInspector({ evidence }: { evidence: EvidenceReport }) {
  return (
    <details className="evidence-inspector">
      <summary>Evidence inspector · operator only</summary>
      <dl className="evidence-facts">
        <dt>prompt</dt>
        <dd>
          <code>{evidence.prompt_sha256 || "—"}</code> · {evidence.prompt_chars}{" "}
          chars
        </dd>
        <dt>attempts</dt>
        <dd>
          {evidence.attempts} drafts · {evidence.model_calls} model calls
        </dd>
        <dt>verification</dt>
        <dd>
          {evidence.abstained ? "abstained" : "grounded"}
          {evidence.abstain_reason ? ` · ${evidence.abstain_reason}` : ""}
          {evidence.retry_reason ? ` · retried: ${evidence.retry_reason}` : ""}
        </dd>
        {evidence.scope && (
          <>
            <dt>scope</dt>
            <dd>{evidence.scope}</dd>
          </>
        )}
        {evidence.selected_material_ids.length > 0 && (
          <>
            <dt>materials</dt>
            <dd>
              {evidence.selected_material_ids.map((id) => (
                <code key={id}>{id} </code>
              ))}
            </dd>
          </>
        )}
        {evidence.uncovered_terms.length > 0 && (
          <>
            <dt>uncovered</dt>
            <dd>{evidence.uncovered_terms.join(", ")}</dd>
          </>
        )}
      </dl>
      <ul className="evidence-chunks">
        {evidence.chunks.map((chunk) => (
          <li key={chunk.id}>
            <p className="evidence-chunk-head">
              <code>{chunk.id}</code> · Book {chunk.book}, Chapter{" "}
              {chunk.chapter} · score {chunk.score.toFixed(4)}
            </p>
            <p className="evidence-chunk-text">{chunk.text}</p>
          </li>
        ))}
      </ul>
    </details>
  );
}
