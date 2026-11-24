// Attack conflict resolution, draft restore and flush-before-leaving (hooks/docActions.ts).
import { test } from "node:test";
import assert from "node:assert/strict";
import { flush as leave, keepMine, loadTheirs, restoreDraft } from "@/hooks/docActions";
import { markDirty } from "@/hooks/docSave";
import { readDraft, writeDraft } from "@/lib/draft";
import { doc, flush, installBrowser, json, makeCtx, scriptFetch } from "./helpers";

installBrowser("1");

function inConflict() {
  const h = makeCtx();
  Object.assign(h.r, { loaded: true, version: 1, title: "Plan", edits: 3, savedEdits: 1, block: "conflict" });
  h.fake.html = "<p>mine</p>";
  h.fake.onUpdate = () => markDirty(h.ctx);
  return { ...h, latest: doc({ version: 5, title: "Their title", content: "<p>theirs</p>" }) };
}

test("load theirs: replaces content and title, clears dirty state and the local backup", () => {
  const h = inConflict();
  writeDraft("7", { title: "Plan", content: "<p>mine</p>", savedAt: "x", baseVersion: 1 });
  loadTheirs(h.ctx, h.latest);
  assert.equal(h.fake.html, "<p>theirs</p>");
  assert.equal(h.state.title, "Their title");
  assert.equal(h.r.version, 5);
  assert.equal(h.r.edits, h.r.savedEdits, "no longer dirty");
  assert.equal(h.r.block, null);
  assert.equal(h.state.conflict, null);
  assert.equal(h.state.status, "saved");
  assert.equal(readDraft("7"), null);
});

test("keep mine: rebases onto the conflict's version and overwrites with local content", async () => {
  const h = inConflict();
  const calls = scriptFetch([json(200, { version: 6 })]);
  keepMine(h.ctx, h.latest);
  await flush();
  assert.deepEqual(calls[0].body, { title: "Plan", content: "<p>mine</p>", base_version: 5 });
  assert.equal(h.state.status, "saved");
  assert.equal(h.state.conflict, null);
});

test("restoring an old backup never silently overwrites newer server content", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const h = makeCtx();
  Object.assign(h.r, { loaded: true, version: 9, title: "Plan" });
  h.fake.onUpdate = () => markDirty(h.ctx);
  const calls = scriptFetch([json(409, { detail: { message: "Bob saved a newer version while you were editing.", document: doc({ version: 9 }) } })]);
  restoreDraft(h.ctx, { title: "Plan", content: "<p>from crash</p>", savedAt: "x", baseVersion: 4 });
  t.mock.timers.tick(1000); await flush();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].body?.base_version, 4, "save must be based on the version the backup was made from");
  assert.equal(h.state.status, "conflict", "user decides, nothing is overwritten");
});

test("restoring a backup of the current version saves normally", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const h = makeCtx();
  Object.assign(h.r, { loaded: true, version: 4, title: "Plan" });
  h.fake.onUpdate = () => markDirty(h.ctx);
  const calls = scriptFetch([json(200, { version: 5 })]);
  restoreDraft(h.ctx, { title: "Restored", content: "<p>from crash</p>", savedAt: "x", baseVersion: 4 });
  t.mock.timers.tick(1000); await flush();
  assert.deepEqual(calls[0].body, { title: "Restored", content: "<p>from crash</p>", base_version: 4 });
  assert.equal(h.state.draft, null);
  assert.equal(h.state.status, "saved");
});

test("leaving the page: safe after a successful save, unsafe while the network is down", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const ok = makeCtx();
  Object.assign(ok.r, { loaded: true, version: 1, edits: 1 });
  scriptFetch([json(200, { version: 2 })]);
  assert.equal(await leave(ok.ctx), true);

  const down = makeCtx();
  Object.assign(down.r, { loaded: true, version: 1, edits: 1 });
  scriptFetch([new TypeError("offline")]);
  assert.equal(await leave(down.ctx), false, "must not navigate away and lose edits");
  assert.ok(readDraft("7"), "a local backup exists");
});
