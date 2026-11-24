// Test doubles: browser storage, a scripted fetch, a fake TipTap editor and a recording SyncCtx.
import type { Editor } from "@tiptap/react";
import type { Draft } from "@/lib/draft";
import type { Doc } from "@/lib/types";
import { newRefs, type Notice, type SyncCtx, type SyncRefs, type SyncStatus } from "@/hooks/docSync";

export class MemoryStorage {
  data = new Map<string, string>();
  fail: Error | null = null; // set to make every call throw (quota, disabled storage)
  getItem(k: string) { if (this.fail) throw this.fail; return this.data.get(k) ?? null; }
  setItem(k: string, v: string) { if (this.fail) throw this.fail; this.data.set(k, v); }
  removeItem(k: string) { if (this.fail) throw this.fail; this.data.delete(k); }
}

export function installBrowser(userId: string | null = "1"): MemoryStorage {
  const storage = new MemoryStorage();
  if (userId) storage.setItem("docshare.userId", userId);
  Object.assign(globalThis, { window: globalThis, localStorage: storage });
  return storage;
}

export interface Call { method: string; url: string; body: Record<string, unknown> | null }
type Reply = Response | Error | Promise<Response>;

/** Replaces fetch; each call takes the next reply from the queue (or the fallback). */
export function scriptFetch(replies: Reply[], fallback?: () => Reply): Call[] {
  const calls: Call[] = [];
  globalThis.fetch = async (input, init) => {
    const body = typeof init?.body === "string" ? (JSON.parse(init.body) as Record<string, unknown>) : null;
    calls.push({ method: init?.method ?? "GET", url: String(input), body });
    const reply = replies.length ? replies.shift()! : fallback?.();
    if (!reply) throw new Error("unexpected fetch");
    if (reply instanceof Error) throw reply;
    return reply;
  };
  return calls;
}

export const json = (status: number, data: unknown) =>
  new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });

export function deferred() {
  let resolve!: (r: Response) => void;
  const promise = new Promise<Response>((res) => (resolve = res));
  return { promise, resolve };
}

export const flush = async (n = 5) => {
  for (let i = 0; i < n; i++) await new Promise((r) => setImmediate(r));
};

export function doc(over: Partial<Doc> = {}): Doc {
  return {
    id: 7, title: "Plan", content: "<p>server</p>", version: 1, updated_at: "2026-11-24T00:00:00+00:00",
    updated_by: "Alice", owner: { id: 1, name: "Alice" }, role: "editor", shares: [], active_users: [], ...over,
  };
}

export interface State {
  doc: Doc | null; title: string; status: SyncStatus; notice: Notice | null;
  conflict: Doc | null; fatal: string | null; draft: Draft | null;
}

export interface FakeEditor { html: string; editable: boolean; onUpdate: () => void }

/** A SyncCtx whose setters write into `state`, plus a fake editor wired to `onUpdate`. */
export function makeCtx(id = "7") {
  const state: State = { doc: null, title: "", status: "loading", notice: null, conflict: null, fatal: null, draft: null };
  const set = <K extends keyof State>(k: K) => (v: State[K] | ((p: State[K]) => State[K])) => {
    state[k] = typeof v === "function" ? (v as (p: State[K]) => State[K])(state[k]) : v;
  };
  const fake: FakeEditor = { html: "", editable: true, onUpdate: () => {} };
  const editor = {
    getHTML: () => fake.html,
    setEditable: (v: boolean) => { fake.editable = v; },
    commands: {
      setContent: (c: string, o?: { emitUpdate?: boolean }) => { fake.html = c; if (o?.emitUpdate !== false) fake.onUpdate(); },
    },
  } as unknown as Editor;
  const r: { current: SyncRefs } = { current: { ...newRefs(), editor } };
  const ctx: SyncCtx = {
    id, r, setDoc: set("doc"), setTitle: set("title"), setStatus: set("status"), setNotice: set("notice"),
    setConflict: set("conflict"), setFatal: set("fatal"), setDraft: set("draft"),
  };
  return { ctx, state, fake, r: r.current };
}
