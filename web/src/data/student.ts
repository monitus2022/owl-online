// The student's display name: collected once at the welcome, kept in this
// browser, and sent with every chat request so the professors can address the
// student. It is never persisted by the API and never stored with a chat
// record. The validation matches the server's `student_name` field
// (app/api/schemas.py): letters, spaces, apostrophes, hyphens and full stops,
// up to 40 characters, starting with a letter, with no control characters.
//
// `useSyncExternalStore` is used instead of context so the footer, the welcome
// and the chat panel all read the same value without a provider, and a change
// in one tab reaches the others through the storage event.

import { useSyncExternalStore } from "react";

const KEY = "owl.student.name";
const MAX_LENGTH = 40;
const ALLOWED = /^[\p{L} .'-]+$/u;
const FIRST_LETTER = /^\p{L}/u;

const listeners = new Set<() => void>();

// Undefined means "not read yet"; null means "no name in this browser". The
// small cache keeps the snapshot stable and lets the name survive a visit even
// if the store rejects the write (private mode, a full quota).
let cache: string | null | undefined;

export type StudentNameResult =
  | { ok: true; name: string }
  | { ok: false; error: string };

// One place for the rules, so the form and the stored value cannot disagree.
export function parseStudentName(raw: string): StudentNameResult {
  if (/[\u0000-\u001f\u007f]/.test(raw)) {
    return { ok: false, error: "The name should be one line of plain text." };
  }
  const name = raw.replace(/\s+/g, " ").trim();
  if (!name) {
    return { ok: false, error: "The ledger needs a name before you can enter." };
  }
  if (name.length > MAX_LENGTH) {
    return { ok: false, error: "Keep it to 40 characters or fewer." };
  }
  if (!FIRST_LETTER.test(name)) {
    return { ok: false, error: "The name should start with a letter." };
  }
  if (!ALLOWED.test(name)) {
    return {
      ok: false,
      error: "Letters, spaces, apostrophes, hyphens and full stops only.",
    };
  }
  return { ok: true, name };
}

function parseStored(raw: string | null): string | null {
  if (!raw) return null;
  const parsed = parseStudentName(raw);
  return parsed.ok ? parsed.name : null;
}

function read(): string | null {
  if (cache !== undefined) return cache;
  try {
    cache = parseStored(window.localStorage.getItem(KEY));
  } catch {
    // A blocked store means no name this visit; the welcome still works.
    cache = null;
  }
  return cache;
}

function emit(): void {
  for (const listener of listeners) listener();
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  const onStorage = (event: StorageEvent) => {
    if (event.key === KEY || event.key === null) {
      cache = parseStored(event.newValue);
      listener();
    }
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

export function getStudentName(): string | null {
  return read();
}

export function setStudentName(name: string): void {
  const parsed = parseStudentName(name);
  if (!parsed.ok) return;
  cache = parsed.name;
  try {
    window.localStorage.setItem(KEY, parsed.name);
  } catch {
    // A blocked or full store still keeps the name for this visit.
  }
  emit();
}

export function clearStudentName(): void {
  cache = null;
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    // Nothing to clean up in a blocked store.
  }
  emit();
}

export function useStudentName(): string | null {
  return useSyncExternalStore(subscribe, getStudentName, () => null);
}
