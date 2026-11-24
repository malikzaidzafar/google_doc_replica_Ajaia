"use client";

import { useEffect, useRef, useState } from "react";
import { useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { clearDraft, type Draft } from "@/lib/draft";
import type { Doc, Share } from "@/lib/types";
import { flush, keepMine, loadTheirs, restoreDraft } from "./docActions";
import { changeTitle, markDirty } from "./docSave";
import { newRefs, type Notice, type SyncCtx, type SyncRefs, type SyncStatus } from "./docSync";
import { useDocPolling } from "./useDocPolling";
import { useUnloadGuard } from "./useUnloadGuard";

/** Everything the document screen needs: the TipTap editor plus load/poll/autosave/conflict state. */
export function useDocEditor(id: string) {
  const [doc, setDoc] = useState<Doc | null>(null);
  const [title, setTitle] = useState("");
  const [status, setStatus] = useState<SyncStatus>("loading");
  const [notice, setNotice] = useState<Notice | null>(null);
  const [conflict, setConflict] = useState<Doc | null>(null);
  const [fatal, setFatal] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const r = useRef<SyncRefs>(newRefs());
  const [ctx] = useState<SyncCtx>(() => ({
    id, r, setDoc, setTitle, setStatus, setNotice, setConflict, setFatal, setDraft,
  }));

  const editor = useEditor({
    extensions: [StarterKit],
    editable: false, // enabled once we know the user's role
    immediatelyRender: false, // avoid SSR hydration mismatches
    editorProps: { attributes: { class: "doc-page", "aria-label": "Document body" } },
    onUpdate: () => markDirty(ctx),
  });

  useEffect(() => {
    r.current.editor = editor; // declared before useDocPolling so it runs first
  }, [editor]);
  useDocPolling(ctx, editor);
  useUnloadGuard(ctx);

  return {
    editor,
    doc,
    title,
    status,
    notice,
    conflict,
    fatal,
    draft,
    canEdit: doc !== null && doc.role !== "viewer" && status !== "stopped" && status !== "readonly",
    changeTitle: (value: string) => changeTitle(ctx, value),
    loadTheirs: () => conflict && loadTheirs(ctx, conflict),
    keepMine: () => conflict && keepMine(ctx, conflict),
    restoreDraft: () => draft && restoreDraft(ctx, draft),
    discardDraft: () => {
      clearDraft(id);
      setDraft(null);
    },
    flush: () => flush(ctx),
    setShares: (shares: Share[]) => setDoc((d) => (d ? { ...d, shares } : d)),
  };
}

export type DocEditorState = ReturnType<typeof useDocEditor>;
