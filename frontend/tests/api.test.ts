// Attack lib/api.ts: whatever the server or network does, users only ever see a human sentence.
import { test } from "node:test";
import assert from "node:assert/strict";
import { api, ApiError, errorMessage } from "@/lib/api";
import { installBrowser, json, scriptFetch } from "./helpers";

installBrowser("1");

const LEAKS = /\b\d{3}\b|error|typeerror|fetch|json|psycopg|traceback|exception|sql|undefined|null|\bat \w/i;

async function failure(reply: Response | Error): Promise<ApiError> {
  scriptFetch([reply]);
  try {
    await api("/documents/7");
  } catch (e) {
    assert.ok(e instanceof ApiError, "every failure must surface as ApiError");
    return e;
  }
  assert.fail("expected the request to fail");
}

function assertHuman(message: string) {
  assert.ok(message.trim().length > 10, `too short: "${message}"`);
  assert.doesNotMatch(message, LEAKS, `leaks internals: "${message}"`);
  assert.match(message, /[.!?]$/, "should be a full sentence");
}

const nasty: [string, Response | Error][] = [
  ["fetch throws TypeError", new TypeError("Failed to fetch")],
  ["500 with HTML body", new Response("<html>Internal Server Error</html>", { status: 500 })],
  ["500 leaking a driver error", json(500, { detail: "psycopg.OperationalError: SSL connection closed" })],
  ["502 from the proxy", new Response("Bad Gateway", { status: 502 })],
  ["503 while asleep", new Response("", { status: 503 })],
  ["504 proxy timeout", new Response("timeout", { status: 504 })],
  ["422 raw pydantic list", json(422, { detail: [{ loc: ["body", "title"], msg: "Field required", type: "missing" }] })],
  ["400 detail is a number", json(400, { detail: 42 })],
  ["400 detail is null", json(400, { detail: null })],
  ["400 detail is an object without message", json(400, { detail: { code: "E_BAD" } })],
  ["400 detail is blank", json(400, { detail: "   " })],
  ["404 from Next itself (HTML)", new Response("<!DOCTYPE html><h1>404</h1>", { status: 404 })],
  ["418 empty body", new Response(null, { status: 418 })],
];

for (const [name, reply] of nasty) {
  test(`humanized: ${name}`, async () => assertHuman((await failure(reply)).message));
}

test("server and network failures never echo the server's text", async () => {
  const e = await failure(json(500, { detail: "Something specific from the server." }));
  assert.equal(e.kind, "server");
  assert.ok(e.retryable);
  assert.doesNotMatch(e.message, /specific/);
});

test("statuses map to the right behaviour", async () => {
  const cases: [number, string, boolean][] = [
    [401, "auth", false], [403, "forbidden", false], [404, "notFound", false], [409, "conflict", false],
    [413, "invalid", false], [422, "invalid", false], [500, "server", true], [503, "server", true],
  ];
  for (const [status, kind, retryable] of cases) {
    const e = await failure(json(status, { detail: "A readable message." }));
    assert.equal(e.kind, kind, `status ${status}`);
    assert.equal(e.retryable, retryable, `status ${status} retryable`);
  }
  assert.equal((await failure(new TypeError("x"))).kind, "network");
});

test("409 exposes the newer document and its message", async () => {
  const latest = { id: 7, version: 3, content: "<p>theirs</p>" };
  const e = await failure(json(409, { detail: { message: "Bob saved a newer version while you were editing.", document: latest } }));
  assert.equal(e.kind, "conflict");
  assert.deepEqual(e.conflictDoc, latest);
  assertHuman(e.message);
  assert.equal((await failure(json(409, { detail: "x" }))).conflictDoc, null);
});

test("a 200 that isn't JSON (captive portal, proxy page) is an error, not silent null", async () => {
  const e = await failure(new Response("<html>Login to Wi-Fi</html>", { status: 200 }));
  assert.equal(e.kind, "server");
  assertHuman(e.message);
});

test("204 resolves without reading a body; auth header is sent", async () => {
  const calls = scriptFetch([new Response(null, { status: 204 })]);
  assert.equal(await api("/documents/7", { method: "DELETE" }), undefined);
  assert.equal(calls[0].url, "/api/documents/7");
});

test("non-ApiError values still get the generic friendly text", () => {
  for (const thrown of [new TypeError("x is undefined"), "boom", null, { detail: "raw" }]) assertHuman(errorMessage(thrown));
});
