// Attack lib/draft.ts: the local backup must never crash the editor or leak across docs/users.
import { test } from "node:test";
import assert from "node:assert/strict";
import { clearDraft, readDraft, writeDraft, type Draft } from "@/lib/draft";
import { installBrowser } from "./helpers";

const draft = (over: Partial<Draft> = {}): Draft => ({
  title: "T", content: "<p>mine</p>", savedAt: "2026-11-24T00:00:00Z", baseVersion: 3, ...over,
});

test("round-trips per document and per user", () => {
  const storage = installBrowser("1");
  writeDraft("7", draft());
  assert.deepEqual(readDraft("7"), draft());
  assert.equal(readDraft("8"), null, "another document must not see it");
  storage.setItem("docshare.userId", "2");
  assert.equal(readDraft("7"), null, "another user must not see it");
  storage.setItem("docshare.userId", "1");
  clearDraft("7");
  assert.equal(readDraft("7"), null);
});

test("storage that throws (quota, disabled, SecurityError) is swallowed", () => {
  const storage = installBrowser("1");
  for (const name of ["QuotaExceededError", "SecurityError", "Error"]) {
    storage.fail = Object.assign(new Error("denied"), { name });
    assert.doesNotThrow(() => writeDraft("7", draft()));
    assert.equal(readDraft("7"), null);
    assert.doesNotThrow(() => clearDraft("7"));
  }
});

test("a huge draft that overflows storage doesn't throw", () => {
  const storage = installBrowser("1");
  storage.setItem = () => { throw Object.assign(new Error("full"), { name: "QuotaExceededError" }); };
  assert.doesNotThrow(() => writeDraft("7", draft({ content: "x".repeat(6_000_000) })));
});

test("corrupted or tampered storage is ignored, never returned with the wrong types", () => {
  const storage = installBrowser("1");
  const key = "docshare.draft.1.7";
  const junk = [
    "{not json", "null", "42", '"string"', "[]", "{}",
    '{"title":null,"content":"<p>x</p>","savedAt":"x","baseVersion":1}',
    '{"title":"T","content":5,"savedAt":"x","baseVersion":1}',
    '{"title":"T","content":"<p>x</p>","savedAt":"x","baseVersion":"1"}',
    '{"title":"T","content":"<p>x</p>","savedAt":"x"}',
  ];
  for (const raw of junk) {
    storage.setItem(key, raw);
    assert.equal(readDraft("7"), null, raw);
  }
});
