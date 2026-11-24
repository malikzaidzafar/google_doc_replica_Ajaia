// Attack autosave with every failure the server or network can produce.
import { test } from "node:test";
import assert from "node:assert/strict";
import { markDirty } from "@/hooks/docSave";
import { KEEP_TEXT_HINT } from "@/hooks/docSync";
import { doc, flush, installBrowser, json, makeCtx, scriptFetch } from "./helpers";

installBrowser("1");

function editing(reply: Response | Error) {
  const h = makeCtx();
  Object.assign(h.r, { loaded: true, version: 1, title: "Plan" });
  h.fake.html = "<p>mine</p>";
  const calls = scriptFetch([reply], () => json(200, { version: 99 }));
  return { ...h, calls };
}

async function typeAndWait(h: ReturnType<typeof editing>, tick: (ms: number) => void, ms = 1000) {
  markDirty(h.ctx);
  tick(ms);
  await flush();
}

test("409: blocks autosave, shows the newer doc, keeps local text, no more PUTs", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const latest = doc({ version: 2, content: "<p>theirs</p>", updated_by: "Bob" });
  const h = editing(json(409, { detail: { message: "Bob saved a newer version while you were editing.", document: latest } }));
  await typeAndWait(h, (ms) => t.mock.timers.tick(ms));
  assert.equal(h.state.status, "conflict");
  assert.deepEqual(h.state.conflict, latest);
  for (let i = 0; i < 5; i++) await typeAndWait(h, (ms) => t.mock.timers.tick(ms), 60_000);
  assert.equal(h.calls.length, 1, "no PUTs until the user resolves the conflict");
  assert.equal(h.fake.html, "<p>mine</p>", "local text untouched");
});

test("409 without a document can't be resolved: stop editing but keep the text", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const h = editing(json(409, { detail: "conflict" }));
  await typeAndWait(h, (ms) => t.mock.timers.tick(ms));
  assert.equal(h.state.status, "stopped");
  assert.equal(h.fake.html, "<p>mine</p>");
});

for (const [status, expected] of [[403, "readonly"], [404, "stopped"], [401, "stopped"]] as const) {
  test(`${status}: autosave blocked, editor read-only, unsaved text kept with a hint`, async (t) => {
    t.mock.timers.enable({ apis: ["setTimeout"] });
    const h = editing(json(status, { detail: "A readable reason." }));
    await typeAndWait(h, (ms) => t.mock.timers.tick(ms));
    assert.equal(h.state.status, expected);
    assert.equal(h.fake.editable, false);
    assert.ok(h.state.notice?.message.includes(KEEP_TEXT_HINT));
    await typeAndWait(h, (ms) => t.mock.timers.tick(ms), 60_000);
    assert.equal(h.calls.length, 1);
    assert.equal(h.fake.html, "<p>mine</p>");
  });
}

test("network/5xx: retries with growing backoff and finally saves the latest text", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const h = editing(new TypeError("Failed to fetch"));
  const calls = scriptFetch([new TypeError("x"), json(503, {}), new TypeError("x"), json(200, { version: 2 })]);
  await typeAndWait(h, (ms) => t.mock.timers.tick(ms));
  assert.equal(h.state.status, "offline");
  const gaps = [2000, 4000, 8000];
  for (const [i, gap] of gaps.entries()) {
    t.mock.timers.tick(gap - 1); await flush();
    assert.equal(calls.length, i + 1, `no retry before ${gap} ms`);
    if (i === 1) h.fake.html = "<p>typed while offline</p>";
    t.mock.timers.tick(1); await flush();
    assert.equal(calls.length, i + 2, `retry at ${gap} ms`);
  }
  assert.equal(calls.at(-1)?.body?.content, "<p>typed while offline</p>");
  assert.equal(h.state.status, "saved");
});

test("413/422: tell the user, but never loop retrying the same doomed save", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  for (const status of [413, 422]) {
    const h = editing(json(status, { detail: "That document is too large to save." }));
    await typeAndWait(h, (ms) => t.mock.timers.tick(ms));
    t.mock.timers.tick(120_000); await flush();
    assert.equal(h.calls.length, 1, `${status} must not retry on its own`);
    assert.equal(h.state.status, "unsaved");
    assert.equal(h.state.notice?.tone, "error");
  }
});
