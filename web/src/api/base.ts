// The API origin. Empty means same origin (the API can also serve this build).
// On Cloudflare Pages, set VITE_OWL_API_BASE in the project's environment.
export function apiBase(): string {
  return (import.meta.env.VITE_OWL_API_BASE ?? "").replace(/\/$/, "");
}
