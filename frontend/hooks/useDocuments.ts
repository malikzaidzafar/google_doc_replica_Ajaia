"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, errorMessage } from "@/lib/api";
import type { Created, DocLists, DocSummary, User } from "@/lib/types";
import { uploadProblem } from "@/lib/upload";

/** The signed-in user's document lists plus create / import / delete. */
export function useDocuments(me: User | null, onSignedOut: () => void) {
  const router = useRouter();
  const [docs, setDocs] = useState<DocLists | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const fail = useCallback(
    (e: unknown) => (e instanceof ApiError && e.kind === "auth" ? onSignedOut() : setError(errorMessage(e))),
    [onSignedOut],
  );

  const load = useCallback(() => {
    api<DocLists>("/documents").then(setDocs).catch(fail);
  }, [fail]);

  useEffect(() => {
    if (me) load();
  }, [me, load]);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  const create = () =>
    run(async () => {
      const { id } = await api<Created>("/documents", { method: "POST", json: {} });
      router.push(`/docs/${id}`);
    });

  function importFile(file: File) {
    const problem = uploadProblem(file);
    if (problem) return setError(problem);
    void run(async () => {
      const form = new FormData();
      form.append("file", file);
      const { id } = await api<Created>("/documents/import", { method: "POST", body: form });
      router.push(`/docs/${id}`);
    });
  }

  function remove(doc: DocSummary) {
    if (!window.confirm(`Delete "${doc.title}"? This can't be undone.`)) return;
    void run(async () => {
      await api<void>(`/documents/${doc.id}`, { method: "DELETE" });
      load();
    });
  }

  return { docs: me ? docs : null, error, busy, create, importFile, remove };
}
