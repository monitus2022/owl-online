import { apiBase } from "./base";

// GET /v1/materials/{subject}/{material_id}: the reviewed pack note behind a
// lesson source. The route returns the authored material text and book
// locators, never the corpus quote or chunk text.

export interface MaterialSourceRef {
  chunk_id: string;
  book: number;
  chapter: number;
}

export interface MaterialDetail {
  material_id: string;
  subject: string;
  topic: string;
  topic_title: string;
  concept: string;
  concept_title: string;
  text: string;
  pack_version: string;
  source_refs: MaterialSourceRef[];
}

export class MaterialError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "MaterialError";
  }
}

export async function getMaterial(
  subject: string,
  materialId: string,
): Promise<MaterialDetail> {
  let response: Response;
  try {
    response = await fetch(
      `${apiBase()}/v1/materials/${encodeURIComponent(subject)}/${encodeURIComponent(materialId)}`,
      { credentials: "include" },
    );
  } catch {
    throw new MaterialError("Could not reach the Academy.");
  }
  if (!response.ok) {
    throw new MaterialError("The reviewed note could not be opened.");
  }
  const payload = (await response.json()) as MaterialDetail;
  return {
    ...payload,
    source_refs: Array.isArray(payload.source_refs) ? payload.source_refs : [],
  };
}
