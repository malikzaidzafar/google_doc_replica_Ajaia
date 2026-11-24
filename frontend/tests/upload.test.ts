// Attack lib/upload.ts: the client pre-check must agree with the server's rules.
import { test } from "node:test";
import assert from "node:assert/strict";
import { uploadProblem } from "@/lib/upload";

const MB2 = 2 * 1024 * 1024;
const file = (name: string, size = 10, type = "") => new File([new Uint8Array(size)], name, { type });

test("accepts supported types in any letter case", () => {
  for (const name of ["notes.txt", "README.MD", "Plan.DOCX", "q3 plan.final.md", "🚀 launch.docx", ".md"]) {
    assert.equal(uploadProblem(file(name)), null, name);
  }
});

test("rejects disguised or extension-less files", () => {
  for (const name of ["a.md.exe", "report.pdf", "README", "md", "docx", "notes.txt ", "notes.", "archive.docx.zip"]) {
    assert.match(uploadProblem(file(name)) ?? "", /isn't supported/, name);
  }
});

test("the MIME type is not trusted: a .txt labelled as PDF is judged by its name only", () => {
  assert.equal(uploadProblem(file("notes.txt", 10, "application/pdf")), null);
  assert.match(uploadProblem(file("notes.pdf", 10, "text/plain")) ?? "", /isn't supported/);
});

test("empty and size boundaries match the server (2 MB allowed, 2 MB + 1 byte rejected)", () => {
  assert.match(uploadProblem(file("empty.txt", 0)) ?? "", /empty/);
  assert.equal(uploadProblem(file("max.txt", MB2)), null);
  assert.match(uploadProblem(file("big.txt", MB2 + 1)) ?? "", /larger than 2 MB/);
});

test("messages are human sentences", () => {
  for (const f of [file("x.pdf"), file("x.txt", 0), file("x.txt", MB2 + 1)]) {
    assert.match(uploadProblem(f) ?? "", /^[A-Z].*\.$/);
  }
});
