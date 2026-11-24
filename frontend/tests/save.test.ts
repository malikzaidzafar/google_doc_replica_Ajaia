// Attack the autosave state machine (hooks/docSave.ts) on the happy-but-busy paths.
import { test } from "node:test";
import assert from "node:assert/strict";
import { changeTitle, markDirty, save } from "@/hooks/docSave";
import { deferred, flush, installBrowser, json, makeCtx, scriptFetch } from "./helpers";

installBrowser("1");

export function loaded(version = 1) {
  const h = makeCtx();
  Object.assign(h.r, { loaded: true, version, title: "Plan" });
  h.fake.html = "<p>a</p>";
  h.fake.onUpdate = () => markDirty(h.ctx);
  return h;
}

test("rapid edits: one PUT in flight, edits made meanwhile go out next with the NEW base version", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const h = loaded(1);
  const first = deferred();
  const calls = scriptFetch([first.promise, json(200, { version: 3 })]);
  for (let i = 0; i < 5; i++) { h.fake.html = `<p>${i}</p>`; markDirty(h.ctx); }
  t.mock.timers.tick(1000); await flush();
  assert.equal(calls.length, 1, "five quick edits = one save");
  assert.deepEqual(calls[0].body, { title: "Plan", content: "<p>4</p>", base_version: 1 });

  h.fake.html = "<p>during</p>"; markDirty(h.ctx);
  t.mock.timers.tick(1000); await flush();
  assert.equal(calls.length, 1, "never two PUTs at once");
  first.resolve(json(200, { version: 2 })); await flush();
  assert.equal(h.state.status, "unsaved", "newer edits are still pending");
  t.mock.timers.tick(1000); await flush();
  assert.equal(calls.length, 2);
  assert.deepEqual(calls[1].body, { title: "Plan", content: "<p>during</p>", base_version: 2 });
  assert.equal(h.state.status, "saved");
  assert.equal(h.r.version, 3);
});

test("title-only edits are saved, and a blank title is sent as the fallback", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const h = loaded(4);
  const calls = scriptFetch([json(200, { version: 5 })]);
  changeTitle(h.ctx, "   ");
  t.mock.timers.tick(1000); await flush();
  assert.deepEqual(calls[0].body, { title: "Untitled document", content: "<p>a</p>", base_version: 4 });
  assert.equal(h.state.status, "saved");
});

test("edits before the doc loads, and remote content being applied, are not saved", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const h = makeCtx();
  const calls = scriptFetch([]);
  markDirty(h.ctx);
  h.r.loaded = true;
  h.r.applyingRemote = true;
  markDirty(h.ctx);
  t.mock.timers.tick(5000); await flush();
  assert.equal(calls.length, 0);
  assert.equal(h.r.edits, 0);
});

test("save is a no-op when nothing changed", async () => {
  const h = loaded();
  const calls = scriptFetch([]);
  await save(h.ctx);
  assert.equal(calls.length, 0);
});

test("an exception while reading the editor doesn't wedge autosave forever", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const h = loaded(1);
  const editor = h.r.editor as unknown as { getHTML: () => string };
  const real = editor.getHTML;
  editor.getHTML = () => { throw new Error("view destroyed"); };
  scriptFetch([json(200, { version: 2 })]);
  markDirty(h.ctx);
  await save(h.ctx).catch(() => {});
  assert.equal(h.r.saving, false, "saving flag must be released");
  editor.getHTML = real;
  await save(h.ctx);
  assert.equal(h.state.status, "saved");
});
