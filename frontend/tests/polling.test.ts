// Attack the load + poll loop (hooks/useDocPolling.ts) with stale, hostile and failing responses.
import { afterEach, test, type TestContext } from "node:test";
import assert from "node:assert/strict";
import type { Editor } from "@tiptap/react";
import { useDocPolling } from "@/hooks/useDocPolling";
import { markDirty } from "@/hooks/docSave";
import { runCleanups } from "./fake-react.mjs";
import { doc, flush, installBrowser, json, makeCtx, scriptFetch } from "./helpers";

installBrowser("1");
afterEach(() => runCleanups());

// Named like a hook because it calls one (fake React runs the effect immediately).
function usePollingHarness(t: TestContext, replies: (Response | Error)[]) {
  t.mock.timers.enable({ apis: ["setTimeout", "setInterval", "Date"] });
  const h = makeCtx();
  h.fake.onUpdate = () => markDirty(h.ctx);
  const calls = scriptFetch(replies, () => json(200, doc()));
  useDocPolling(h.ctx, h.r.editor as Editor);
  return { ...h, calls };
}

test("first load applies the server doc and enables editing", async (t) => {
  const h = usePollingHarness(t, [json(200, doc({ version: 3, content: "<p>v3</p>" }))]);
  await flush();
  assert.equal(h.fake.html, "<p>v3</p>");
  assert.equal(h.r.version, 3);
  assert.equal(h.state.status, "saved");
  assert.equal(h.fake.editable, true);
});

test("remote updates apply only when idle and newer; stale responses are ignored", async (t) => {
  const h = usePollingHarness(t, [json(200, doc({ version: 3 })), json(200, doc({ version: 2, content: "<p>stale</p>" }))]);
  await flush();
  t.mock.timers.tick(4000); await flush();
  assert.notEqual(h.fake.html, "<p>stale</p>", "older version must never overwrite");
  t.mock.timers.tick(3500); await flush();
  h.fake.html = "<p>my unsaved edit</p>";
  markDirty(h.ctx); // debounced save would fire at +1000 ms; the poll lands at +500 ms
  scriptFetch([json(200, doc({ version: 4, content: "<p>remote</p>" }))]);
  t.mock.timers.tick(500); await flush();
  assert.equal(h.fake.html, "<p>my unsaved edit</p>", "never clobber local edits");
});

test("viewers are read-only and still receive live updates", async (t) => {
  const h = usePollingHarness(t, [json(200, doc({ role: "viewer", version: 1 })), json(200, doc({ role: "viewer", version: 2, content: "<p>new</p>" }))]);
  await flush();
  assert.equal(h.state.status, "readonly");
  assert.equal(h.fake.editable, false);
  t.mock.timers.tick(4000); await flush();
  assert.equal(h.fake.html, "<p>new</p>");
});

test("access removed mid-session: stop editing and stop polling", async (t) => {
  const h = usePollingHarness(t, [json(200, doc()), json(404, { detail: "We couldn't find that document." })]);
  await flush();
  t.mock.timers.tick(4000); await flush();
  assert.equal(h.state.status, "stopped");
  const before = h.calls.length;
  t.mock.timers.tick(40_000); await flush();
  assert.equal(h.calls.length, before, "no polling after access is gone");
});

test("transient poll failures don't stop or stack polling: one request per interval", async (t) => {
  const h = usePollingHarness(t, [json(200, doc()), new TypeError("offline"), json(500, {}), json(200, doc({ version: 2 }))]);
  await flush();
  for (let i = 1; i <= 3; i++) {
    t.mock.timers.tick(4000); await flush();
    assert.equal(h.calls.length, 1 + i);
  }
  assert.equal(h.r.version, 2);
});

test("sleeping server: shows 'waking', keeps retrying, then loads", async (t) => {
  const h = usePollingHarness(t, [json(503, {}), new TypeError("x"), json(200, doc({ version: 7 }))]);
  await flush();
  assert.equal(h.state.status, "waking");
  t.mock.timers.tick(1000); await flush();
  t.mock.timers.tick(2000); await flush();
  assert.equal(h.r.version, 7);
  assert.equal(h.state.fatal, null);
});
