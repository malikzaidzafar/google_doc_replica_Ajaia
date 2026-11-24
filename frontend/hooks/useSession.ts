"use client";

import { useEffect, useState } from "react";
import { api, errorMessage, withWakeRetry } from "@/lib/api";
import { getUserId, setUserId } from "@/lib/session";
import type { User } from "@/lib/types";

/** Seeded demo accounts plus the currently signed-in one (simulated auth). */
export function useSession() {
  const [users, setUsers] = useState<User[] | null>(null);
  const [me, setMe] = useState<User | null>(null);
  const [error, setError] = useState("");
  const [waking, setWaking] = useState(false);

  useEffect(() => {
    let cancelled = false;
    withWakeRetry(() => api<User[]>("/users"), () => !cancelled && setWaking(true))
      .then((list) => {
        if (cancelled) return;
        setUsers(list);
        setMe(list.find((u) => String(u.id) === getUserId()) ?? null);
      })
      .catch((e: unknown) => !cancelled && setError(errorMessage(e)))
      .finally(() => !cancelled && setWaking(false));
    return () => {
      cancelled = true;
    };
  }, []);

  function signIn(user: User) {
    setUserId(user.id);
    setMe(user);
  }

  function signOut() {
    setUserId(null);
    setMe(null);
  }

  return { users, me, error, waking, signIn, signOut };
}
