// User-triggered sync actions: resolve a conflict, restore a local backup, save before leaving.
import { clearDraft, type Draft } from "@/lib/draft";
import type { Doc } from "@/lib/types";
import { changeTitle, save } from "./docSave";
import { applyServerDoc, isDirty, type SyncCtx } from "./docSync";

export function loadTheirs(ctx: SyncCtx, latest: Doc): void {
  ctx.r.current.block = null;
  applyServerDoc(ctx, latest);
  ctx.setDoc(latest);
  ctx.setConflict(null);
  ctx.setStatus("saved");
  clearDraft(ctx.id);
}

export function keepMine(ctx: SyncCtx, latest: Doc): void {
  const r = ctx.r.current;
  r.block = null;
  r.version = latest.version; // rebase onto the newest version, then overwrite it
  ctx.setConflict(null);
  void save(ctx);
}

export function restoreDraft(ctx: SyncCtx, draft: Draft): void {
  // Base the save on the backup's version: if others saved since, the server answers 409 and the
  // user chooses, instead of their newer work being overwritten silently.
  ctx.r.current.version = draft.baseVersion;
  ctx.r.current.editor?.commands.setContent(draft.content); // emits an update -> autosave
  changeTitle(ctx, draft.title);
  ctx.setDraft(null);
}

/** Save pending edits now. True when it's safe to leave the page. */
export async function flush(ctx: SyncCtx): Promise<boolean> {
  const r = ctx.r.current;
  clearTimeout(r.timer);
  await save(ctx);
  return !isDirty(r) || r.block !== null; // blocked edits are kept in the local draft backup
}
