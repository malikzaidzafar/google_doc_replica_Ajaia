import type { Dispatch, RefObject, SetStateAction } from "react";
import type { Editor } from "@tiptap/react";
import type { Draft } from "@/lib/draft";
import type { Doc } from "@/lib/types";

/*
 * Concurrency model (optimistic, no live merging; see ARCHITECTURE.md):
 * every save sends the version its edits are based on. If someone saved in between, the server
 * answers 409 and we show a banner; local edits stay in the editor until the user chooses.
 * Polling applies newer server versions only while the user has no unsaved edits.
 */

export type SyncStatus =
  | "loading" | "waking" | "saved" | "unsaved" | "saving" | "offline" | "conflict" | "readonly" | "stopped";

/** Why autosave is paused: viewer role, unresolved conflict, or access/doc gone for good. */
export type BlockReason = "role" | "conflict" | "gone" | null;

export interface Notice {
  tone: "error" | "warning";
  message: string;
}

/** Mutable bookkeeping kept in a ref so timers and editor callbacks always see current values. */
export interface SyncRefs {
  editor: Editor | null;
  loaded: boolean;
  version: number; // server version the editor content is based on
  edits: number; // bumped on every local change
  savedEdits: number; // value of `edits` covered by the last successful save
  saving: boolean;
  block: BlockReason;
  applyingRemote: boolean;
  title: string;
  timer?: ReturnType<typeof setTimeout>;
  retryDelay: number;
}

type Setter<T> = Dispatch<SetStateAction<T>>;

export interface SyncCtx {
  id: string;
  r: RefObject<SyncRefs>;
  setDoc: Setter<Doc | null>;
  setTitle: Setter<string>;
  setStatus: Setter<SyncStatus>;
  setNotice: Setter<Notice | null>;
  setConflict: Setter<Doc | null>;
  setFatal: Setter<string | null>;
  setDraft: Setter<Draft | null>;
}

export const RETRY_START_MS = 2000;
export const KEEP_TEXT_HINT = "Your unsaved text is still on screen; copy it if you need it.";

export const newRefs = (): SyncRefs => ({
  editor: null, loaded: false, version: 0, edits: 0, savedEdits: 0, saving: false,
  block: null, applyingRemote: false, title: "", retryDelay: RETRY_START_MS,
});

export const isDirty = (r: SyncRefs): boolean => r.edits !== r.savedEdits;

/** Replace local content with a server version without counting it as a local edit. */
export function applyServerDoc(ctx: SyncCtx, d: Doc): void {
  const r = ctx.r.current;
  r.applyingRemote = true;
  r.editor?.commands.setContent(d.content, { emitUpdate: false });
  r.applyingRemote = false;
  r.version = d.version;
  r.title = d.title;
  r.savedEdits = r.edits;
  ctx.setTitle(d.title);
}

/** Access lost, doc deleted or signed out: stop saving for good, keep the text visible. */
export function stopEditing(ctx: SyncCtx, message: string): void {
  const r = ctx.r.current;
  const text = isDirty(r) ? `${message} ${KEEP_TEXT_HINT}` : message;
  r.block = "gone";
  clearTimeout(r.timer);
  r.editor?.setEditable(false);
  ctx.setNotice({ tone: "error", message: text });
  ctx.setStatus("stopped");
}
