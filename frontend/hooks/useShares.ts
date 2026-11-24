"use client";

import { useState } from "react";
import { api, errorMessage } from "@/lib/api";
import type { Share, ShareRole, SharesResponse } from "@/lib/types";

/** Owner actions in the share dialog: add someone, change their role, remove them. */
export function useShares(docId: number, onChange: (shares: Share[]) => void) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run(request: () => Promise<SharesResponse>): Promise<boolean> {
    setBusy(true);
    setError("");
    try {
      onChange((await request()).shares);
      return true;
    } catch (e) {
      setError(errorMessage(e));
      return false;
    } finally {
      setBusy(false);
    }
  }

  const share = (email: string, role: ShareRole) =>
    run(() => api<SharesResponse>(`/documents/${docId}/shares`, { method: "POST", json: { email, role } }));

  const remove = (userId: number) =>
    run(() => api<SharesResponse>(`/documents/${docId}/shares/${userId}`, { method: "DELETE" }));

  return { busy, error, share, remove };
}
