// Simulated auth: the signed-in seeded user's id lives in localStorage and is sent as X-User-Id.

const KEY = "docshare.userId";

export function getUserId(): string | null {
  return typeof window === "undefined" ? null : localStorage.getItem(KEY);
}

export function setUserId(id: number | null): void {
  if (id === null) localStorage.removeItem(KEY);
  else localStorage.setItem(KEY, String(id));
}
