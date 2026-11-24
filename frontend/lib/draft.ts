// Best-effort local backup of unsaved edits, so a crash or closed tab doesn't lose work.
import { getUserId } from "./session";

export interface Draft {
  title: string;
  content: string;
  savedAt: string;
  baseVersion: number; // server version the unsaved edits were made on top of
}

const key = (docId: string) => `docshare.draft.${getUserId() ?? "anon"}.${docId}`;

function isDraft(v: unknown): v is Draft {
  if (typeof v !== "object" || v === null) return false;
  const d = v as Record<string, unknown>;
  return typeof d.title === "string" && typeof d.content === "string" &&
    typeof d.savedAt === "string" && Number.isInteger(d.baseVersion);
}

export function writeDraft(docId: string, draft: Draft): void {
  try {
    localStorage.setItem(key(docId), JSON.stringify(draft));
  } catch {
    // Storage full or disabled: the backup is optional, the server save still runs.
  }
}

export function readDraft(docId: string): Draft | null {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(key(docId)) ?? "null");
    return isDraft(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function clearDraft(docId: string): void {
  try {
    localStorage.removeItem(key(docId));
  } catch {
    // Nothing to clean up if storage is unavailable.
  }
}
