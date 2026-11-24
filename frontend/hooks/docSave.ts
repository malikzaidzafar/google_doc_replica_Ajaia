import { api, ApiError, errorMessage } from "@/lib/api";
import { clearDraft, writeDraft } from "@/lib/draft";
import type { Saved } from "@/lib/types";
import { isDirty, KEEP_TEXT_HINT, RETRY_START_MS, stopEditing, type SyncCtx } from "./docSync";

const SAVE_DELAY_MS = 1000;
const RETRY_MAX_MS = 30_000;

export function schedule(ctx: SyncCtx, delay = SAVE_DELAY_MS): void {
  const r = ctx.r.current;
  clearTimeout(r.timer);
  r.timer = setTimeout(() => void save(ctx), delay);
}

export function markDirty(ctx: SyncCtx): void {
  const r = ctx.r.current;
  if (r.applyingRemote || !r.loaded) return;
  r.edits += 1;
  if (r.block !== null) return; // keep the conflict/read-only status; edits stay local
  ctx.setStatus("unsaved");
  schedule(ctx);
}

export function changeTitle(ctx: SyncCtx, value: string): void {
  ctx.r.current.title = value;
  ctx.setTitle(value);
  markDirty(ctx);
}

/** Save once. Never runs two saves at once; edits made meanwhile are picked up by the next save. */
export async function save(ctx: SyncCtx): Promise<void> {
  const r = ctx.r.current;
  if (!r.editor || r.saving || r.block !== null || !isDirty(r)) return;
  r.saving = true;
  const editsAtStart = r.edits;
  ctx.setStatus("saving");
  let retryIn: number | null = null;
  try {
    const title = r.title.trim() || "Untitled document";
    const content = r.editor.getHTML(); // inside try: a throw must not leave `saving` stuck
    writeDraft(ctx.id, { title, content, savedAt: new Date().toISOString(), baseVersion: r.version });
    const res = await api<Saved>(`/documents/${ctx.id}`, {
      method: "PUT",
      json: { title, content, base_version: r.version },
    });
    r.version = res.version;
    r.savedEdits = editsAtStart;
    r.retryDelay = RETRY_START_MS;
    ctx.setNotice(null);
    ctx.setStatus(isDirty(r) ? "unsaved" : "saved");
    if (!isDirty(r)) clearDraft(ctx.id);
  } catch (e) {
    retryIn = onSaveError(ctx, e);
  } finally {
    r.saving = false;
    if (r.block === null && isDirty(r)) {
      if (retryIn !== null) schedule(ctx, retryIn);
      else if (r.edits !== editsAtStart) schedule(ctx); // typed while this save was in flight
    }
  }
}

/** Returns a retry delay for transient failures, or null when retrying won't help. */
function onSaveError(ctx: SyncCtx, e: unknown): number | null {
  const r = ctx.r.current;
  const kind = e instanceof ApiError ? e.kind : "server";
  if (kind === "conflict" && e instanceof ApiError && e.conflictDoc) {
    r.block = "conflict";
    ctx.setConflict(e.conflictDoc);
    ctx.setStatus("conflict");
  } else if (kind === "forbidden") {
    r.block = "role";
    r.editor?.setEditable(false);
    ctx.setNotice({ tone: "warning", message: `${errorMessage(e)} ${KEEP_TEXT_HINT}` });
    ctx.setStatus("readonly");
  } else if (kind === "notFound" || kind === "auth" || kind === "conflict") {
    stopEditing(ctx, errorMessage(e));
  } else if (kind === "network" || kind === "server") {
    const delay = r.retryDelay;
    r.retryDelay = Math.min(delay * 2, RETRY_MAX_MS);
    ctx.setNotice({ tone: "warning", message: errorMessage(e) });
    ctx.setStatus("offline");
    return delay;
  } else {
    ctx.setNotice({ tone: "error", message: errorMessage(e) }); // e.g. too large: fix and keep typing
    ctx.setStatus("unsaved");
  }
  return null;
}
