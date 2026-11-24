"use client";

import { useEffect } from "react";
import { writeDraft } from "@/lib/draft";
import { isDirty, type SyncCtx } from "./docSync";

/** Back up unsaved edits locally and ask the browser to confirm before closing the tab. */
export function useUnloadGuard(ctx: SyncCtx): void {
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      const r = ctx.r.current;
      if (!r.editor || !isDirty(r)) return;
      writeDraft(ctx.id, { title: r.title, content: r.editor.getHTML(), savedAt: new Date().toISOString(), baseVersion: r.version });
      e.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [ctx]);
}
