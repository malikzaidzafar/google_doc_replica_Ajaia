"use client";

import { useEffect } from "react";
import type { Editor } from "@tiptap/react";
import { api, ApiError, errorMessage, withWakeRetry } from "@/lib/api";
import { clearDraft, readDraft } from "@/lib/draft";
import type { Doc } from "@/lib/types";
import { schedule } from "./docSave";
import { applyServerDoc, isDirty, KEEP_TEXT_HINT, stopEditing, type SyncCtx } from "./docSync";

const POLL_MS = 4000;

function offerDraft(ctx: SyncCtx, d: Doc): void {
  const draft = readDraft(ctx.id);
  if (!draft) return;
  if (d.role === "viewer" || (draft.content === d.content && draft.title === d.title)) clearDraft(ctx.id);
  else ctx.setDraft(draft);
}

/** Apply a server snapshot: first load, remote updates, and role changes. */
function receive(ctx: SyncCtx, d: Doc, first: boolean): void {
  const r = ctx.r.current;
  ctx.setDoc(d);
  const idle = !isDirty(r) && !r.saving;
  if (first) {
    applyServerDoc(ctx, d);
    r.loaded = true;
    offerDraft(ctx, d);
  } else if (d.version > r.version && idle && (r.block === null || r.block === "role")) {
    applyServerDoc(ctx, d);
  }

  if (d.role === "viewer") {
    if (r.block === null) {
      r.block = "role";
      if (!first) {
        const msg = "The owner changed your access to view only.";
        ctx.setNotice({ tone: "warning", message: idle ? msg : `${msg} ${KEEP_TEXT_HINT}` });
      }
    }
    if (r.block === "role") {
      r.editor?.setEditable(false);
      ctx.setStatus("readonly");
    }
  } else if (r.block === "role") {
    // Upgraded back to editor (or a 403 was temporary): resume editing and saving.
    r.block = null;
    r.editor?.setEditable(true);
    ctx.setNotice(null);
    ctx.setStatus(isDirty(r) ? "unsaved" : "saved");
    if (isDirty(r)) schedule(ctx);
  } else if (first) {
    r.editor?.setEditable(true);
    ctx.setStatus("saved");
  }
}

/** Loads the doc (waiting for a sleeping server if needed), then polls every few seconds. */
export function useDocPolling(ctx: SyncCtx, editor: Editor | null): void {
  useEffect(() => {
    if (!editor) return;
    const r = ctx.r.current; // r.editor is set by useDocEditor before this effect runs
    let stopped = false;
    const url = `/documents/${ctx.id}`;

    withWakeRetry(() => api<Doc>(url), () => !stopped && ctx.setStatus("waking"))
      .then((d) => !stopped && receive(ctx, d, true))
      .catch((e: unknown) => {
        if (!stopped) ctx.setFatal(errorMessage(e));
        stopped = true;
      });

    const timer = setInterval(() => {
      if (stopped || !r.loaded) return;
      api<Doc>(url)
        .then((d) => !stopped && receive(ctx, d, false))
        .catch((e: unknown) => {
          const gone = e instanceof ApiError && (e.kind === "notFound" || e.kind === "auth");
          if (stopped || !gone) return; // transient failure: the next poll tries again
          stopped = true;
          stopEditing(ctx, errorMessage(e));
        });
    }, POLL_MS);

    return () => {
      stopped = true;
      clearInterval(timer);
      clearTimeout(r.timer);
    };
  }, [ctx, editor]);
}
