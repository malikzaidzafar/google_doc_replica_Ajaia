import type { Doc } from "./types";
import { getUserId } from "./session";

export type ErrorKind = "network" | "auth" | "forbidden" | "notFound" | "conflict" | "invalid" | "server";

// The only place that turns failed responses into text users see (CLAUDE.md "Error messages").
const FRIENDLY: Record<ErrorKind, string> = {
  network: "Can't reach the server. Check your connection; we'll keep retrying.",
  auth: "Your session has ended. Please sign in again.",
  forbidden: "You don't have permission to do that.",
  notFound: "This document doesn't exist, or it hasn't been shared with you.",
  conflict: "Someone else saved a newer version while you were editing.",
  invalid: "That didn't work. Please check what you entered and try again.",
  server: "Something went wrong on our side. Your changes are still on this page; please try again.",
};

const isRecord = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);

function kindOf(status: number): ErrorKind {
  if (status === 0) return "network";
  if (status === 401) return "auth";
  if (status === 403) return "forbidden";
  if (status === 404) return "notFound";
  if (status === 409) return "conflict";
  return status >= 500 ? "server" : "invalid";
}

function friendlyMessage(kind: ErrorKind, body: unknown): string {
  if (kind === "network" || kind === "server") return FRIENDLY[kind]; // never surface server internals
  const detail = isRecord(body) ? body.detail : undefined;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (isRecord(detail) && typeof detail.message === "string") return detail.message;
  return FRIENDLY[kind]; // e.g. a raw validation list: don't show it
}

export class ApiError extends Error {
  readonly kind: ErrorKind;

  constructor(readonly status: number, readonly body: unknown) {
    super(friendlyMessage(kindOf(status), body));
    this.kind = kindOf(status);
  }

  get retryable(): boolean {
    return this.kind === "network" || this.kind === "server";
  }

  /** The newer document the server sends back with a 409. */
  get conflictDoc(): Doc | null {
    const detail = isRecord(this.body) ? this.body.detail : null;
    return isRecord(detail) && isRecord(detail.document) ? (detail.document as unknown as Doc) : null;
  }
}

export const errorMessage = (e: unknown): string => (e instanceof ApiError ? e.message : FRIENDLY.server);

interface Options {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  json?: unknown;
  body?: FormData;
}

/** fetch wrapper: auth header, JSON in/out, and humanized ApiErrors. */
export async function api<T>(path: string, { method = "GET", json, body }: Options = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const uid = getUserId();
  if (uid) headers["X-User-Id"] = uid;
  let payload: BodyInit | undefined = body;
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(json);
  }
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { method, headers, body: payload, cache: "no-store" });
  } catch {
    throw new ApiError(0, null);
  }
  if (res.status === 204) return undefined as T;
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok || data === null) throw new ApiError(res.ok ? 502 : res.status, data); // 2xx non-JSON = bad gateway
  return data as T;
}

/** Retry while the (free-tier, sleeping) API wakes up. Calls onWaiting once a retry is needed. */
export async function withWakeRetry<T>(fn: () => Promise<T>, onWaiting: () => void, maxMs = 90_000): Promise<T> {
  const start = Date.now();
  for (let delay = 1000; ; delay = Math.min(delay * 2, 8000)) {
    try {
      return await fn();
    } catch (e) {
      if (!(e instanceof ApiError) || !e.retryable || Date.now() - start > maxMs) throw e;
      onWaiting();
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }
}
